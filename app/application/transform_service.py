"""Text-transformation use cases (application layer, ADR-001).

``TransformService`` orchestrates the text features — translate (#21), and later
explain (#24) and improve (#8) — over the ``LLMProvider`` port. It is transport-
agnostic: it knows nothing about HTTP or SSE (the router owns that). It yields
plain text deltas; a provider failure surfaces as a domain ``ProviderError``
during iteration, which the router maps onto the SSE error frame.

This file is the shared foundation: explain/improve add their own methods here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.application.prompts import render_prompt
from app.domain.providers.llm import LLMProvider
from app.domain.providers.messages import Message


class TransformService:
    """Coordinates text transforms over an injected ``LLMProvider`` port."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def translate(
        self,
        text: str,
        *,
        source_lang: str | None = None,
        target_lang: str,
    ) -> AsyncIterator[str]:
        """Stream a translation of ``text`` into ``target_lang``.

        ``source_lang`` is optional — when absent the model auto-detects it. The
        language values pass straight into the prompt (the model interprets
        ``EN`` / ``es`` / ``English``); no code→name mapping is kept here. A low
        temperature keeps the translation faithful rather than creative.
        """
        prompt = render_prompt(
            "translate",
            source_lang=source_lang or "the detected source language",
            target_lang=target_lang,
        )
        messages = [Message("system", prompt), Message("user", text)]
        async for delta in self._llm.stream_chat(messages, temperature=0.2):
            yield delta
