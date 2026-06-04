"""FastAPI dependency providers.

Routers depend on the provider *ports* and receive the configured adapter via
`Depends` — they never import an adapter or name a provider. Each dependency
wraps the corresponding registry, which selects the adapter from `Settings`.
"""

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.domain.providers.llm import LLMProvider
from app.domain.providers.stt import STTProvider
from app.domain.providers.tts import TTSProvider
from app.infrastructure.providers.llm.registry import (
    get_llm_provider as _build_llm_provider,
)
from app.infrastructure.providers.stt.registry import (
    get_stt_provider as _build_stt_provider,
)
from app.infrastructure.providers.tts.registry import (
    get_tts_provider as _build_tts_provider,
)

__all__ = [
    "Settings",
    "get_settings",
    "get_llm_provider",
    "get_tts_provider",
    "get_stt_provider",
]


def get_llm_provider(settings: Settings = Depends(get_settings)) -> LLMProvider:
    return _build_llm_provider(settings)


def get_tts_provider(settings: Settings = Depends(get_settings)) -> TTSProvider:
    return _build_tts_provider(settings)


def get_stt_provider(settings: Settings = Depends(get_settings)) -> STTProvider:
    return _build_stt_provider(settings)
