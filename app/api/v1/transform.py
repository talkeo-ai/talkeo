"""Text-transformation endpoints (translate / explain / improve).

Thin API layer (ADR-001): parse the request, validate, delegate to
``TransformService``, and frame the resulting delta stream as SSE. No business
logic lives here. The service is transport-agnostic, so the domain→transport
error translation happens at this boundary: a ``ProviderError`` raised mid-stream
becomes a ``StreamError`` and the SSE helper emits a clean ``event: error`` frame
(#2 contract).

Request-validation errors (e.g. empty text) are returned as a pre-stream HTTP
``400`` — caught before the 200 stream is committed — so the client never has to
recover a bad request from inside the stream.
"""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import get_llm_provider
from app.api.sse import StreamError, sse_response
from app.application.transform_service import TransformService
from app.domain.providers.errors import ProviderError
from app.domain.providers.llm import LLMProvider

router = APIRouter(prefix="/transform", tags=["transform"])


class TranslateRequest(BaseModel):
    text: str
    target_lang: str
    source_lang: str | None = None


async def _as_sse(source: AsyncIterator[str]) -> AsyncIterator[str]:
    """Bridge a service delta stream to the SSE layer: a domain ``ProviderError``
    becomes a ``StreamError`` so the helper emits a clean ``event: error`` frame
    with its ``code``/``message`` instead of the masked generic failure."""
    try:
        async for delta in source:
            yield delta
    except ProviderError as exc:
        raise StreamError(exc.code, exc.message) from exc


@router.post("/translate")
async def translate(
    req: TranslateRequest,
    llm: LLMProvider = Depends(get_llm_provider),
):
    if not req.text or not req.text.strip():
        return JSONResponse(
            {"code": "bad_request", "message": "text is required"},
            status_code=400,
        )

    service = TransformService(llm)
    return sse_response(
        _as_sse(
            service.translate(
                req.text,
                source_lang=req.source_lang,
                target_lang=req.target_lang,
            )
        )
    )
