"""Fake LLM provider.

Implements ``LLMProvider`` with no external dependency. Two jobs: prove the
port is implementable, and give self-hosted/dev users a no-keys mode
(``LLM_PROVIDER=fake``). It echoes the last user message back as word-by-word
deltas so a consumer can exercise streaming end to end.
"""

from collections.abc import AsyncIterator

from app.domain.providers.messages import Message


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
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        reply = f"fake reply to: {last_user}".strip()
        for word in reply.split(" "):
            yield word + " "
