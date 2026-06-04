"""Provider ports — the agnostic contracts the domain depends on.

The domain names no provider and imports no SDK. Adapters in
``app/infrastructure/providers/`` fulfil these ports; a registry selects
which adapter to load from configuration (see ADR-002, ADR-008).
"""

from app.domain.providers.errors import (
    LLMError,
    ProviderError,
    STTError,
    TTSError,
)
from app.domain.providers.llm import LLMProvider
from app.domain.providers.messages import Message, Role
from app.domain.providers.stt import STTProvider, Transcript
from app.domain.providers.tts import TTSProvider

__all__ = [
    "Message",
    "Role",
    "Transcript",
    "LLMProvider",
    "TTSProvider",
    "STTProvider",
    "ProviderError",
    "LLMError",
    "TTSError",
    "STTError",
]
