"""LLM provider registry — config picks the adapter, not code.

Use cases never import an adapter directly; they depend on the ``LLMProvider``
port and receive the selected adapter via DI (``app/api/deps.py``).
"""

from app.core.config import Settings
from app.domain.providers.llm import LLMProvider
from app.infrastructure.providers.llm.fake import FakeLLMProvider


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Return the LLM adapter selected by ``settings.LLM_PROVIDER``."""
    name = settings.LLM_PROVIDER
    if name == "fake":
        return FakeLLMProvider()
    if name == "litellm":
        raise ValueError("litellm LLM adapter lands in issue #3")
    raise ValueError(f"Unknown LLM provider: {name}")
