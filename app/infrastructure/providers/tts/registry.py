"""TTS provider registry — config picks the adapter, not code."""

from app.core.config import Settings
from app.domain.providers.tts import TTSProvider
from app.infrastructure.providers.tts.fake import FakeTTSProvider
from app.infrastructure.providers.tts.livekit import LiveKitTTSProvider


def get_tts_provider(settings: Settings) -> TTSProvider:
    """Return the TTS adapter selected by ``settings.TTS_PROVIDER``."""
    name = settings.TTS_PROVIDER
    if name == "fake":
        return FakeTTSProvider()
    if name == "livekit":
        # Fail loud at construction if the selected engine's key is missing,
        # rather than at first request.
        if settings.TTS_ENGINE == "openai" and not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when TTS_ENGINE=openai")
        if settings.TTS_ENGINE == "elevenlabs" and not settings.ELEVENLABS_API_KEY:
            raise ValueError("ELEVENLABS_API_KEY is required when TTS_ENGINE=elevenlabs")
        return LiveKitTTSProvider(settings)
    raise ValueError(f"Unknown TTS provider: {name}")
