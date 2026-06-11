"""Text-to-speech endpoint — one-shot ``listen to pronunciation``.

``POST /api/v1/tts/speak`` synthesizes a short phrase and returns it as a WAV
body. The provider is injected via the port (``TTSProvider``); the router never
names an engine. The audio is assembled whole before responding so a failure
returns a clean ``{code, message}`` JSON body with the right status — the same
error shape the SSE endpoints emit (#2), so clients handle one shape everywhere.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app.api.deps import get_tts_provider
from app.domain.providers.errors import TTSError
from app.domain.providers.tts import TTSProvider

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


class TTSSpeakRequest(BaseModel):
    text: str
    voice: str | None = None
    audio_format: str | None = None


@router.post("/speak")
async def speak(
    req: TTSSpeakRequest,
    tts: TTSProvider = Depends(get_tts_provider),
) -> Response:
    try:
        buf = bytearray()
        async for chunk in tts.synthesize(
            req.text, voice=req.voice, audio_format=req.audio_format
        ):
            buf += chunk
    except TTSError as exc:
        return JSONResponse(
            {"code": exc.code, "message": exc.message},
            status_code=_STATUS.get(exc.code, 502),
        )
    return Response(bytes(buf), media_type="audio/wav")
