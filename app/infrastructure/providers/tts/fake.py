"""Fake TTS provider.

Implements ``TTSProvider`` with no external dependency. Emits a couple of
placeholder byte chunks instead of real audio — enough to prove the streaming
contract and to run a TTS endpoint in dev without provider keys.
"""

from collections.abc import AsyncIterator


class FakeTTSProvider:
    """Deterministic stand-in for a real TTS engine. No network, no keys."""

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        audio_format: str | None = None,
    ) -> AsyncIterator[bytes]:
        payload = f"fake audio for: {text}".encode()
        # Two chunks, so consumers exercise the streaming path.
        mid = len(payload) // 2
        yield payload[:mid]
        yield payload[mid:]
