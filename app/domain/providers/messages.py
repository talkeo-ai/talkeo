"""Chat message value object — the LLM input contract.

Kept deliberately small and provider-neutral. Adapters translate a
``list[Message]`` into whatever shape their engine expects (e.g. the
OpenAI-compatible ``{"role", "content"}`` dicts LiteLLM consumes).
"""

from dataclasses import dataclass
from typing import Literal

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class Message:
    """A single turn in a chat exchange."""

    role: Role
    content: str
