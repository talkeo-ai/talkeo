"""LiteLLM-gateway LLM adapter.

Implements ``LLMProvider`` by talking the OpenAI-compatible wire to a LiteLLM
proxy (ADR-008: a single gateway serves the HTTP API and the voice agent
alike). It uses the official ``openai.AsyncOpenAI`` client pointed at
``LITELLM_BASE_URL`` — one client, one wire — so keys, fallbacks, cost, and
reasoning controls live in the proxy, not here. The file is named for its
*destination* (the gateway), not the SDK it speaks.

Streaming is passed through delta-by-delta with no buffering (latency
discipline). Retries are disabled on the client (``max_retries=0``); the proxy
owns retries and fallbacks.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx
import openai
from openai import AsyncOpenAI

from app.core.config import Settings
from app.domain.providers.errors import LLMError
from app.domain.providers.messages import Message

# Ordered most-specific-first: the openai hierarchy nests
# (APITimeoutError ⊂ APIConnectionError ⊂ APIError; RateLimitError /
# AuthenticationError / BadRequestError ⊂ APIStatusError ⊂ APIError), so the
# first isinstance match wins. Messages are fixed and client-safe — never
# ``str(exc)``, which can leak provider internals (see ``errors.py``).
_ERROR_MAP: tuple[tuple[type[openai.APIError], str, str], ...] = (
    (openai.APITimeoutError, "timeout", "LLM request timed out"),
    (openai.APIConnectionError, "provider_error", "cannot reach LLM gateway"),
    (openai.RateLimitError, "rate_limit", "LLM rate limit exceeded"),
    (openai.AuthenticationError, "auth", "LLM authentication failed"),
    (openai.BadRequestError, "bad_request", "invalid LLM request"),
    (openai.APIError, "provider_error", "LLM request failed"),
)


def _to_llm_error(exc: openai.APIError) -> LLMError:
    """Map an openai exception onto a domain ``LLMError`` (table above)."""
    for exc_type, code, message in _ERROR_MAP:
        if isinstance(exc, exc_type):
            return LLMError(code, message)
    return LLMError("provider_error", "LLM request failed")


class LiteLLMProvider:
    """``LLMProvider`` over an OpenAI-compatible LiteLLM gateway (ADR-008)."""

    def __init__(
        self, settings: Settings, *, client: AsyncOpenAI | None = None
    ) -> None:
        self._default_model = settings.LLM_MODEL
        # ``client`` is injectable so tests exercise the adapter without a
        # network or a real SDK round-trip.
        self._client = client or AsyncOpenAI(
            base_url=settings.LITELLM_BASE_URL,
            api_key=settings.LITELLM_API_KEY or "sk-noauth",
            max_retries=0,
            timeout=httpx.Timeout(
                settings.LLM_READ_TIMEOUT,
                connect=settings.LLM_CONNECT_TIMEOUT,
            ),
        )

    async def stream_chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        chosen_model = model or self._default_model
        if not chosen_model:
            raise LLMError("config", "no LLM model configured")

        kwargs: dict[str, Any] = {
            "model": chosen_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        try:
            stream = await self._client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except asyncio.CancelledError:
            # Never wrap cancellation: it is a BaseException so it propagates and
            # tears the task down cleanly. Wrapping it would swallow the cancel.
            raise
        except openai.APIError as exc:
            raise _to_llm_error(exc) from exc
