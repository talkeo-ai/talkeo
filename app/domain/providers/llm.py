"""LLM provider port.

The port yields **plain text deltas** (``AsyncIterator[str]``), not engine
chunk objects: LiteLLM's ``chunk.choices[0].delta.content`` translation lives
in the adapter (issue #3), never here. The SSE layer owns the end-of-stream
signal, so no terminal sentinel is part of this contract.
"""

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from app.domain.providers.messages import Message


@runtime_checkable
class LLMProvider(Protocol):
    """Port. The domain depends on this — not on any specific provider."""

    async def stream_chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream a chat completion as plain text deltas.

        ``model`` is an optional override; when ``None`` the adapter uses its
        configured default. Provider-specific reasoning controls (effort,
        thinking budget) are added as keyword-only params by the adapters that
        need them — additive and non-breaking (ADR-008).
        """
        ...
