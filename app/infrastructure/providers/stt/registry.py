"""STT provider registry — config picks the adapter, not code.

Design-only: only ``fake`` is wired. The real LiveKit adapter lands in
Phase B.1 (realtime voice).
"""

from app.core.config import Settings
from app.domain.providers.stt import STTProvider
from app.infrastructure.providers.stt.fake import FakeSTTProvider


def get_stt_provider(settings: Settings) -> STTProvider:
    """Return the STT adapter selected by ``settings.STT_PROVIDER``."""
    name = settings.STT_PROVIDER
    if name == "fake":
        return FakeSTTProvider()
    if name == "livekit":
        raise ValueError("livekit STT adapter lands in Phase B.1")
    raise ValueError(f"Unknown STT provider: {name}")
