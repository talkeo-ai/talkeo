"""Text-to-speech endpoint — streaming ``listen``.

``POST /api/v1/tts/speak`` synthesizes ``text`` and streams the audio
chunk-by-chunk so playback can start as soon as the first chunk is generated,
regardless of the text length. The body is raw PCM (s16le, 24 kHz, mono — the
``TTSProvider`` wire contract); the format is fixed and advertised via response
headers so clients configure playback up front. A consumer that wants the whole
file just reads the stream to the end.

The provider is injected via the port (``TTSProvider``); the router never names
an engine.

Error contract: the HTTP status is sent before the body, so we **peek the first
chunk** before responding. A failure at/before the first chunk (or empty text)
returns a clean ``{code, message}`` JSON with the right status — the same shape
the SSE endpoints emit (#2). A failure *after* streaming has started can no
longer change the status, so the connection simply closes and the client treats
the truncated stream as an error.
"""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.api.deps import get_tts_provider
from app.domain.providers.errors import TTSError
from app.domain.providers.tts import (
    PCM_NUM_CHANNELS,
    PCM_SAMPLE_RATE,
    PCM_SAMPLE_WIDTH_BITS,
    TTSProvider,
)

router = APIRouter(prefix="/tts", tags=["tts"])

# Map a domain error code onto an HTTP status. `bad_request` is the only
# client-caused one; the rest are upstream/engine failures.
_STATUS = {
    "bad_request": 400,
    "rate_limit": 429,
    "timeout": 504,
    "auth": 502,
    "provider_error": 502,
}

# Wire format advertised to the client before the body streams (the format is
# fixed by the port, not negotiable per request).
_AUDIO_HEADERS = {
    "X-Sample-Rate": str(PCM_SAMPLE_RATE),
    "X-Channels": str(PCM_NUM_CHANNELS),
    "X-Bits-Per-Sample": str(PCM_SAMPLE_WIDTH_BITS),
}


class TTSSpeakRequest(BaseModel):
    text: str
    voice: str | None = None


def _error(exc: TTSError) -> JSONResponse:
    return JSONResponse(
        {"code": exc.code, "message": exc.message},
        status_code=_STATUS.get(exc.code, 502),
    )


async def _body(first: bytes, rest: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    """Re-emit the peeked first chunk, then drain the rest. A ``TTSError`` raised
    mid-stream propagates and closes the connection — the status is already sent."""
    yield first
    async for chunk in rest:
        yield chunk


@router.post("/speak")
async def speak(
    req: TTSSpeakRequest,
    tts: TTSProvider = Depends(get_tts_provider),
):
    # Validate up front: once we return a StreamingResponse the 200 is committed.
    if not req.text or not req.text.strip():
        return _error(TTSError("bad_request", "text is required"))

    agen = tts.synthesize(req.text, voice=req.voice)
    # Peek the first chunk so an immediate failure still gets a clean status.
    # This costs no extra latency — that first chunk is the time-to-first-audio
    # we would wait for anyway.
    try:
        first = await agen.__anext__()
    except StopAsyncIteration:
        return _error(TTSError("provider_error", "TTS produced no audio"))
    except TTSError as exc:
        return _error(exc)

    return StreamingResponse(
        _body(first, agen),
        media_type="audio/pcm",
        headers=_AUDIO_HEADERS,
    )
