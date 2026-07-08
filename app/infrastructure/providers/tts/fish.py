"""Fish Audio TTS adapter (native HTTP, streaming).

Implements ``TTSProvider`` by calling Fish Audio's one-shot HTTP API directly —
Fish has no LiveKit plugin, and its endpoint already returns raw PCM, so a thin
native adapter is a cleaner fit than the LiveKit path. The engine never crosses
the port: the route sees only ``AsyncIterator[bytes]``.

``POST https://api.fish.audio/v1/tts`` with ``format="pcm"`` and
``sample_rate=24000`` streams raw s16le 24 kHz mono PCM — already the port's
fixed wire format (see ``app.domain.providers.tts``). We stream the response
body chunk-by-chunk so playback can start at the first chunk (#22).

The ``reference_id`` selects a cloned/library voice; omit it (``FISH_VOICE``
unset, no per-request ``voice``) for Fish's default voice. The model is sent as
a header (``s2-pro`` by default).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings
from app.domain.providers.errors import TTSError

_ENDPOINT = "https://api.fish.audio/v1/tts"

# Map an HTTP status onto a domain (code, message) — the same tokens the other
# adapters and the endpoint's `_STATUS` table use. Anything not listed falls
# through to a generic provider error.
_STATUS_ERRORS: dict[int, tuple[str, str]] = {
    400: ("bad_request", "invalid TTS request"),
    401: ("auth", "TTS authentication failed"),
    403: ("auth", "TTS authentication failed"),
    429: ("rate_limit", "TTS rate limit exceeded"),
    504: ("timeout", "TTS request timed out"),
}


def _to_tts_error(status: int) -> TTSError:
    code, message = _STATUS_ERRORS.get(status, ("provider_error", "TTS request failed"))
    return TTSError(code, message)


class FishTTSProvider:
    """``TTSProvider`` over Fish Audio's HTTP API.

    ``client`` is injectable so tests exercise the adapter without a network or
    key (pass an ``httpx.AsyncClient`` backed by a mock transport)."""

    def __init__(
        self, settings: Settings, *, client: httpx.AsyncClient | None = None
    ) -> None:
        self._settings = settings
        self._injected = client

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
    ) -> AsyncIterator[bytes]:
        # Known Fish quirk: a trailing period truncates the audio, so strip it.
        clean = text.strip().rstrip(".").strip()
        if not clean:
            raise TTSError("bad_request", "text is required")

        body: dict[str, object] = {
            "text": clean,
            "format": "pcm",
            "sample_rate": 24000,
            # `balanced` is Fish's low-latency mode: it starts emitting audio
            # sooner (at a hair of quality) — the right trade for streaming-first
            # playback that starts at the first chunk (#22).
            "latency": "balanced",
            # Max chunk size (chars). Fewer, larger server-side chunks give the
            # model more context per chunk → steadier prosody and fewer seams;
            # short /speak snippets usually stay a single chunk anyway.
            "chunk_length": 300,
            # Keep Fish's text normalization on (its default). It expands
            # numbers/dates/currency ("$5" → "five dollars", "25" → "twenty-five")
            # — mispronouncing those is costly for a learning-focused TTS.
            "normalize": True,
        }
        reference_id = voice or self._settings.FISH_VOICE
        if reference_id:
            body["reference_id"] = reference_id

        headers = {
            "Authorization": f"Bearer {self._settings.FISH_API_KEY}",
            "Content-Type": "application/json",
            "model": self._settings.FISH_MODEL,
        }

        client = self._injected or httpx.AsyncClient(
            timeout=self._settings.TTS_TIMEOUT
        )
        own = self._injected is None
        try:
            async with client.stream(
                "POST", _ENDPOINT, json=body, headers=headers
            ) as response:
                if response.status_code != 200:
                    # Drain the (small) error body so the connection can be
                    # reused, then surface a clean domain error before any audio.
                    await response.aread()
                    raise _to_tts_error(response.status_code)
                produced = False
                async for chunk in response.aiter_bytes():
                    if chunk:
                        produced = True
                        yield chunk
                if not produced:
                    raise TTSError("provider_error", "TTS produced no audio")
        except httpx.TimeoutException as exc:
            raise TTSError("timeout", "TTS request timed out") from exc
        except httpx.HTTPError as exc:
            raise TTSError("provider_error", "cannot reach TTS engine") from exc
        finally:
            if own:
                await client.aclose()
