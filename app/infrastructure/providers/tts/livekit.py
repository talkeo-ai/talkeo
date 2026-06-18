"""LiveKit-plugin TTS adapter (standalone synthesize).

Implements ``TTSProvider`` by delegating to a LiveKit Agents TTS plugin used
*standalone* — no ``AgentSession`` / ``Room`` (ADR-008: speech is integrated
once and reused by both this one-shot endpoint and the realtime voice agent).
The engine (``openai`` / ``elevenlabs``) is chosen by config, so swapping it is a
one-line env change; LiveKit types (``rtc.AudioFrame``, ``SynthesizedAudio``)
never cross the port — the port stays ``AsyncIterator[bytes]``.

Every plugin yields raw PCM frames; we unwrap each frame and yield its bytes as
it arrives — no buffering, so playback starts at the first chunk (#22). Both
engines run PCM-native (``response_format="pcm"`` / ``encoding="pcm_24000"``) so
the framework never spins up its PyAV decoder and the bytes are already the
port's wire format (s16le, 24 kHz, mono — see ``app.domain.providers.tts``).

Retries are disabled (``max_retry=0``); the engine owns retries.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from livekit.agents import (
    APIConnectionError,
    APIError,
    APIConnectOptions,
    APIStatusError,
    APITimeoutError,
)
from livekit.agents import tts as lk_tts

from app.core.config import Settings
from app.domain.providers.errors import TTSError


def _to_tts_error(exc: APIError) -> TTSError:
    """Map a LiveKit plugin exception onto a domain ``TTSError``.

    Ordered most-specific-first: the hierarchy nests (``APITimeoutError`` ⊂
    ``APIConnectionError`` ⊂ ``APIError``; ``APIStatusError`` ⊂ ``APIError``).
    Messages are fixed and client-safe — never ``str(exc)``, which can leak
    engine internals (see ``errors.py``).
    """
    if isinstance(exc, APITimeoutError):
        return TTSError("timeout", "TTS request timed out")
    if isinstance(exc, APIStatusError):
        if exc.status_code in (401, 403):
            return TTSError("auth", "TTS authentication failed")
        if exc.status_code == 429:
            return TTSError("rate_limit", "TTS rate limit exceeded")
        if exc.status_code == 400:
            return TTSError("bad_request", "invalid TTS request")
        return TTSError("provider_error", "TTS request failed")
    if isinstance(exc, APIConnectionError):
        return TTSError("provider_error", "cannot reach TTS engine")
    return TTSError("provider_error", "TTS request failed")


def build_tts_plugin(
    settings: Settings, *, engine: str, voice: str | None = None
) -> lk_tts.TTS:
    """Build a LiveKit TTS plugin for ``engine``. Lazy-imported per engine so only
    the selected plugin package is touched. Both engines forced PCM-native.

    The ``engine`` is the caller's choice, not read from settings here: the
    one-shot adapter passes ``TTS_ENGINE`` for ``/speak``, the voice agent (#15)
    passes ``AGENT_TTS_ENGINE`` — one speech integration, each surface picks its
    own engine (ADR-008)."""
    chosen_voice = voice or settings.TTS_VOICE
    if engine == "openai":
        from livekit.plugins import openai

        kwargs: dict[str, Any] = {
            "api_key": settings.OPENAI_API_KEY,
            "response_format": "pcm",
        }
        if chosen_voice:
            kwargs["voice"] = chosen_voice
        if settings.TTS_MODEL:
            kwargs["model"] = settings.TTS_MODEL
        return openai.TTS(**kwargs)

    if engine == "elevenlabs":
        from livekit.plugins import elevenlabs

        kwargs: dict[str, Any] = {
            "api_key": settings.ELEVENLABS_API_KEY,
            "encoding": "pcm_24000",
        }
        if chosen_voice:
            kwargs["voice_id"] = chosen_voice
        if settings.TTS_MODEL:
            kwargs["model"] = settings.TTS_MODEL
        return elevenlabs.TTS(**kwargs)

    raise TTSError("config", f"unknown TTS engine: {engine!r}")


class LiveKitTTSProvider:
    """``TTSProvider`` over a standalone LiveKit Agents TTS plugin (ADR-008)."""

    def __init__(self, settings: Settings, *, tts: lk_tts.TTS | None = None) -> None:
        self._settings = settings
        # ``tts`` is injectable so tests exercise the adapter without a network,
        # keys, or a real plugin. An injected plugin is owned by the caller and
        # is never built or closed here.
        self._injected = tts

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
    ) -> AsyncIterator[bytes]:
        if not text or not text.strip():
            raise TTSError("bad_request", "text is required")

        tts = self._injected or build_tts_plugin(
            self._settings, engine=self._settings.TTS_ENGINE, voice=voice
        )
        own = self._injected is None
        try:
            stream = tts.synthesize(
                text,
                conn_options=APIConnectOptions(
                    max_retry=0, timeout=self._settings.TTS_TIMEOUT
                ),
            )
            produced = False
            async with stream:
                async for audio in stream:
                    produced = True
                    # ``frame.data`` is a memoryview of int16 samples; its bytes
                    # are already s16le PCM — the port's wire format. Yield as it
                    # arrives so the endpoint can stream chunk-by-chunk.
                    yield bytes(audio.frame.data)
            if not produced:
                raise TTSError("provider_error", "TTS produced no audio")
        except asyncio.CancelledError:
            # Never wrap cancellation: it is a BaseException so it propagates and
            # tears the task down cleanly. Wrapping it would swallow the cancel.
            raise
        except APIError as exc:
            raise _to_tts_error(exc) from exc
        finally:
            if own:
                await tts.aclose()
