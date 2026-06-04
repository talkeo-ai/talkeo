"""Fake STT provider.

Implements ``STTProvider`` with no external dependency. Design-only like the
port: it returns a placeholder transcript so the registry and contract are
exercisable now, ahead of the real LiveKit adapter in Phase B.1.
"""

from app.domain.providers.stt import Transcript


class FakeSTTProvider:
    """Deterministic stand-in for a real STT engine. No network, no keys."""

    async def recognize(
        self,
        audio: bytes,
        *,
        language: str | None = None,
    ) -> Transcript:
        return Transcript(text=f"fake transcript ({len(audio)} bytes)")
