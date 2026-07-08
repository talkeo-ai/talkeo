"""TTS provider registry — config picks the adapter, not code."""

from app.core.config import Settings
from app.domain.providers.tts import TTSProvider
from app.infrastructure.providers.tts.fake import FakeTTSProvider
from app.infrastructure.providers.tts.fish import FishTTSProvider
from app.infrastructure.providers.tts.livekit import LiveKitTTSProvider

# The env var each LiveKit engine needs, so a missing key fails loud at
# construction (with a clear message) instead of at first request.
_LIVEKIT_ENGINE_KEYS = {
    "openai": "OPENAI_API_KEY",
    "elevenlabs": "ELEVENLABS_API_KEY",
    "cartesia": "CARTESIA_API_KEY",
    "deepgram": "DEEPGRAM_API_KEY",
}


def get_tts_provider(settings: Settings) -> TTSProvider:
    """Return the TTS adapter selected by ``settings.TTS_PROVIDER``."""
    name = settings.TTS_PROVIDER
    if name == "fake":
        return FakeTTSProvider()
    if name == "livekit":
        key_name = _LIVEKIT_ENGINE_KEYS[settings.TTS_ENGINE]
        if not getattr(settings, key_name):
            raise ValueError(
                f"{key_name} is required when TTS_ENGINE={settings.TTS_ENGINE}"
            )
        return LiveKitTTSProvider(settings)
    if name == "fish":
        if not settings.FISH_API_KEY:
            raise ValueError("FISH_API_KEY is required when TTS_PROVIDER=fish")
        return FishTTSProvider(settings)
    raise ValueError(f"Unknown TTS provider: {name}")
