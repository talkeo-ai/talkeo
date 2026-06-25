"""Fake LLM provider.

Implements ``LLMProvider`` with no external dependency. Two jobs: prove the
port is implementable, and give self-hosted/dev users a no-keys mode
(``LLM_PROVIDER=fake``). ``stream_chat`` echoes the last user message as
word-by-word deltas; ``complete`` returns a canned, valid vocab-card JSON so the
structured ``/explain`` endpoint renders a real card in dev (mac#4 can build its
UI against it with no keys).
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
        # Pull the term out of the "Term: <term>\n\nSentence: ..." user message
        # so the dev card echoes the real input; fall back to a placeholder.
        content = _last_user(messages)
        term = "example"
        if content.startswith("Term: "):
            term = content[len("Term: ") :].split("\n", 1)[0].strip() or term
        # Card-shaped JSON (a literal, not the ExplainCard type — keeps the fake
        # generic and decoupled from the application model).
        return json.dumps(
            {
                "term": term,
                "category": "noun",
                "meanings": [f"fake meaning of {term}"],
                "examples": [
                    {"source": f"A **{term}** in a sentence.", "target": "Un ejemplo."}
                ],
                "insight": {"type": "pattern", "text": f"Nota de ejemplo sobre {term}."},
            }
        )
