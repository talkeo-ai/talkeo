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

from app.api.deps import Settings, get_llm_provider, get_settings
from app.api.sse import StreamError, sse_response
from app.application.cards import ExplainCard
from app.application.improvements import ImproveResult
from app.application.transform_service import TransformService
from app.domain.providers.errors import ProviderError
from app.domain.providers.llm import LLMProvider

router = APIRouter(prefix="/transform", tags=["transform"])

# Map a domain error code onto an HTTP status, for the JSON (non-SSE) routes.
# `bad_request` is the only client-caused one; the rest are upstream/engine.
_STATUS = {
    "bad_request": 400,
    "rate_limit": 429,
    "timeout": 504,
    "auth": 502,
    "provider_error": 502,
    "config": 502,
}


class TranslateRequest(BaseModel):
    text: str
    target_lang: str
    source_lang: str | None = None


class ExplainRequest(BaseModel):
    term: str
    sentence: str
    target_lang: str
    source_lang: str | None = None


class ImproveRequest(BaseModel):
    # ``text`` is the English being improved; ``target_lang`` is the learner's
    # language, used only for the teaching text (each change's why / examples).
    text: str
    target_lang: str


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
    settings: Settings = Depends(get_settings),
):
    if not req.text or not req.text.strip():
        return JSONResponse(
            {"code": "bad_request", "message": "text is required"},
            status_code=400,
        )

    service = TransformService(llm, settings)
    return sse_response(
        _as_sse(
            service.translate(
                req.text,
                source_lang=req.source_lang,
                target_lang=req.target_lang,
            )
        )
    )


@router.post("/explain", response_model=ExplainCard)
async def explain(
    req: ExplainRequest,
    llm: LLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings),
):
    if not req.term or not req.term.strip():
        return JSONResponse(
            {"code": "bad_request", "message": "term is required"},
            status_code=400,
        )
    if not req.sentence or not req.sentence.strip():
        return JSONResponse(
            {"code": "bad_request", "message": "sentence is required"},
            status_code=400,
        )

    # explain returns a short structured card, not prose, so this route responds
    # with JSON (not SSE). The status is sent after the model call, so a provider
    # failure maps to a clean status here rather than an in-band error frame.
    service = TransformService(llm, settings)
    try:
        return await service.explain(
            req.term,
            req.sentence,
            source_lang=req.source_lang,
            target_lang=req.target_lang,
        )
    except ProviderError as exc:
        return JSONResponse(
            {"code": exc.code, "message": exc.message},
            status_code=_STATUS.get(exc.code, 502),
        )


@router.post("/improve", response_model=ImproveResult)
async def improve(
    req: ImproveRequest,
    llm: LLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings),
):
    if not req.text or not req.text.strip():
        return JSONResponse(
            {"code": "bad_request", "message": "text is required"},
            status_code=400,
        )

    # Like explain, improve returns a short structured result (the rewrite plus
    # its changes), so this route responds with JSON, not SSE. An empty
    # ``changes`` list ("already natural") is a normal 200 response.
    service = TransformService(llm, settings)
    try:
        return await service.improve(req.text, target_lang=req.target_lang)
    except ProviderError as exc:
        return JSONResponse(
            {"code": exc.code, "message": exc.message},
            status_code=_STATUS.get(exc.code, 502),
        )
