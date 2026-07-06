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

from pydantic import ValidationError

from app.application.cards import ExplainCard
from app.application.improvements import ImproveResult
from app.application.prompts import render_prompt
from app.core.config import Settings, get_settings
from app.domain.providers.errors import LLMError
from app.domain.providers.llm import LLMProvider
from app.domain.providers.messages import Message


def _strip_json_fences(text: str) -> str:
    """Drop a leading ``json`` / trailing ``` fence if the model wrapped its JSON
    in a markdown code block, leaving the bare object for parsing."""
    t = text.strip()
    if t.startswith("```"):
        t = t[3:]
        if t[:4].lower() == "json":
            t = t[4:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


class TransformService:
    """Coordinates text transforms over an injected ``LLMProvider`` port."""

    def __init__(self, llm: LLMProvider, settings: Settings | None = None) -> None:
        self._llm = llm
        # Settings carry the per-feature model overrides (``*_LLM_MODEL``); only
        # the model name varies per feature, the gateway endpoint is global.
        self._settings = settings or get_settings()

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
        model = self._settings.TRANSLATE_LLM_MODEL or self._settings.LLM_MODEL
        async for delta in self._llm.stream_chat(
            messages, model=model, temperature=0.2
        ):
            yield delta

    async def explain(
        self,
        term: str,
        sentence: str,
        *,
        source_lang: str | None = None,
        target_lang: str,
    ) -> ExplainCard:
        """Return a structured vocabulary card for ``term`` as used in ``sentence``.

        The card (meanings/examples/insight) is written in ``target_lang`` (e.g.
        an English term explained in Spanish for an ES learner). ``term`` and
        ``sentence`` are untrusted input, so they ride in the user message rather
        than the system prompt, the same injection-resistant shape ``translate``
        uses; the instructions (auto-detect when ``source_lang`` is absent) stay
        in the system prompt.

        The model is asked for strict JSON (its JSON mode) and a low temperature;
        the result is validated against ``ExplainCard``. A malformed or
        non-conforming response is surfaced as a provider error (the router maps
        it to 502) rather than reaching the client.
        """
        prompt = render_prompt(
            "explain",
            source_lang=source_lang or "the detected source language",
            target_lang=target_lang,
        )
        content = f"Term: {term}\n\nSentence: {sentence}"
        messages = [Message("system", prompt), Message("user", content)]
        model = self._settings.EXPLAIN_LLM_MODEL or self._settings.LLM_MODEL
        raw = await self._llm.complete(
            messages,
            model=model,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        try:
            return ExplainCard.model_validate_json(_strip_json_fences(raw))
        except ValidationError as exc:
            raise LLMError("provider_error", "explanation was not valid") from exc

    async def improve(
        self,
        text: str,
        *,
        target_lang: str,
    ) -> ImproveResult:
        """Return a native/natural rewrite of ``text`` plus the changes made.

        ``text`` is English (the language being improved); ``target_lang`` is the
        learner's language, used only for the teaching text (each change's ``why``
        and the target side of its examples). ``text`` is untrusted input, so it
        rides in the user message rather than the system prompt, the same
        injection-resistant shape ``translate``/``explain`` use.

        The model is asked for strict JSON (its JSON mode) at a low temperature;
        the result is validated against ``ImproveResult``. An empty ``changes``
        list is a valid result ("already natural"), not an error. A malformed or
        non-conforming response surfaces as a provider error (the router maps it
        to 502) rather than reaching the client.
        """
        prompt = render_prompt("improve", target_lang=target_lang)
        messages = [Message("system", prompt), Message("user", text)]
        model = self._settings.IMPROVE_LLM_MODEL or self._settings.LLM_MODEL
        raw = await self._llm.complete(
            messages,
            model=model,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        try:
            return ImproveResult.model_validate_json(_strip_json_fences(raw))
        except ValidationError as exc:
            raise LLMError("provider_error", "improvement was not valid") from exc
