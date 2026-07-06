"""Fake LLM provider.

Implements ``LLMProvider`` with no external dependency. Two jobs: prove the
port is implementable, and give self-hosted/dev users a no-keys mode
(``LLM_PROVIDER=fake``). ``stream_chat`` echoes the last user message as
word-by-word deltas; ``complete`` returns canned, valid structured JSON so the
``/explain`` and ``/improve`` endpoints render real data in dev (mac#4 and mac#5
can build their UI against it with no keys). It tells the two apart by the shape
of the user message: explain sends ``Term: ...``, improve sends the raw text.
"""

import json
from collections.abc import AsyncIterator

from app.domain.providers.messages import Message


def _last_user(messages: list[Message]) -> str:
    return next((m.content for m in reversed(messages) if m.role == "user"), "")


class FakeLLMProvider:
    """Deterministic stand-in for a real LLM. No network, no keys."""

    async def stream_chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        reply = f"fake reply to: {_last_user(messages)}".strip()
        for word in reply.split(" "):
            yield word + " "

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> str:
        content = _last_user(messages)
        # explain sends "Term: <term>\n\nSentence: ..."; anything else is the raw
        # text from improve. Both return card-/result-shaped JSON literals (not the
        # application models) to keep the fake decoupled from the app layer.
        if content.startswith("Term: "):
            term = content[len("Term: ") :].split("\n", 1)[0].strip() or "example"
            return json.dumps(
                {
                    "term": term,
                    "category": "noun",
                    "meanings": [f"fake meaning of {term}"],
                    "examples": [
                        {
                            "source": f"A **{term}** in a sentence.",
                            "target": "Un ejemplo.",
                        }
                    ],
                    "insight": {
                        "type": "pattern",
                        "text": f"Nota de ejemplo sobre {term}.",
                    },
                }
            )
        # improve: echo the text back as already-natural (empty changes). A real
        # rewrite needs a real model; the fake gives a valid, deterministic result
        # so the endpoint and the "already natural" UI state work with no keys.
        return json.dumps({"improved": content, "changes": []})
