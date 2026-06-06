"""LiveKit-plugin TTS adapter (standalone synthesize).

Implements ``TTSProvider`` by delegating to a LiveKit Agents TTS plugin used
*standalone* — no ``AgentSession`` / ``Room`` (ADR-008: speech is integrated
once and reused by both this one-shot endpoint and the realtime voice agent).
The engine (``openai`` / ``elevenlabs``) is chosen by config, so swapping it is a
one-line env change; LiveKit types (``rtc.AudioFrame``, ``SynthesizedAudio``)
never cross the port — the port stays ``AsyncIterator[bytes]``.

Every plugin yields raw PCM frames, so we assemble them into a single WAV with
the stdlib-backed ``rtc.AudioFrame.to_wav_bytes()`` — zero extra deps, no ffmpeg.
Both engines run PCM-native (``response_format="pcm"`` / ``encoding="pcm_24000"``)
so the framework never spins up its PyAV decoder. Output is buffered (a short
pronunciation phrase) which also gives the endpoint clean error status codes;
realtime no-buffer streaming is the voice agent's concern (#15).

Retries are disabled (``max_retry=0``); the engine owns retries.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from livekit import rtc
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

# WAV is assembled whole, then handed out in chunks so the streaming port is
# exercised end-to-end (the HTTP layer reassembles for a one-shot response).
_CHUNK = 32 * 1024


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


def _build_tts(settings: Settings, *, voice: str | None) -> lk_tts.TTS:
    """Build the configured LiveKit TTS plugin. Lazy-imported per engine so only
    the selected plugin package is touched. Both engines forced PCM-native."""
    chosen_voice = voice or settings.TTS_VOICE
    if settings.TTS_ENGINE == "openai":
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

    if settings.TTS_ENGINE == "elevenlabs":
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

    raise TTSError("config", f"unknown TTS engine: {settings.TTS_ENGINE!r}")


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
        audio_format: str | None = None,
    ) -> AsyncIterator[bytes]:
        if not text or not text.strip():
            raise TTSError("bad_request", "text is required")

        fmt = audio_format or self._settings.TTS_AUDIO_FORMAT
        if fmt != "wav":
            raise TTSError("bad_request", f"unsupported audio_format: {fmt!r} (only 'wav')")

        tts = self._injected or _build_tts(self._settings, voice=voice)
        own = self._injected is None
        try:
            frames: list[rtc.AudioFrame] = []
            stream = tts.synthesize(
                text,
                conn_options=APIConnectOptions(
                    max_retry=0, timeout=self._settings.TTS_TIMEOUT
                ),
            )
            async with stream:
                async for audio in stream:
                    frames.append(audio.frame)
            if not frames:
                raise TTSError("provider_error", "TTS produced no audio")
            wav = rtc.combine_audio_frames(frames).to_wav_bytes()
        except asyncio.CancelledError:
            # Never wrap cancellation: it is a BaseException so it propagates and
            # tears the task down cleanly. Wrapping it would swallow the cancel.
            raise
        except APIError as exc:
            raise _to_tts_error(exc) from exc
        finally:
            if own:
                await tts.aclose()

        for i in range(0, len(wav), _CHUNK):
            yield wav[i : i + _CHUNK]
