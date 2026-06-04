"""TTS provider registry — config picks the adapter, not code."""

from app.core.config import Settings
from app.domain.providers.tts import TTSProvider
from app.infrastructure.providers.tts.fake import FakeTTSProvider


def get_tts_provider(settings: Settings) -> TTSProvider:
    """Return the TTS adapter selected by ``settings.TTS_PROVIDER``."""
    name = settings.TTS_PROVIDER
    if name == "fake":
        return FakeTTSProvider()
    if name == "livekit":
        raise ValueError("livekit TTS adapter lands in issue #4")
    raise ValueError(f"Unknown TTS provider: {name}")
