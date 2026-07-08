"""LLM provider registry — config picks the adapter, not code.

Use cases never import an adapter directly; they depend on the ``LLMProvider``
port and receive the selected adapter via DI (``app/api/deps.py``).

There is one adapter pointed at the single LiteLLM gateway (ADR-008). Running a
feature on a different model is a per-call ``model=`` override (resolved from the
``*_LLM_MODEL`` settings in the service), not a different provider — the gateway
routes by model name to the provider behind it.
"""

from app.core.config import Settings
from app.domain.providers.llm import LLMProvider
from app.infrastructure.providers.llm.fake import FakeLLMProvider
from app.infrastructure.providers.llm.litellm import LiteLLMProvider


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Return the LLM adapter selected by ``settings.LLM_PROVIDER``."""
    name = settings.LLM_PROVIDER
    if name == "fake":
        return FakeLLMProvider()
    if name == "litellm":
        if not settings.LITELLM_BASE_URL:
            raise ValueError(
                "LITELLM_BASE_URL is required when LLM_PROVIDER=litellm"
            )
        return LiteLLMProvider(settings)
    raise ValueError(f"Unknown LLM provider: {name}")
