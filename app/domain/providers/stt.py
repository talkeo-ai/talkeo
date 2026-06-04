"""Speech-to-text provider port.

Design-only in this issue: the contract is fixed now so #3/#4 and the registry
have a stable shape, but no real adapter ships until **Phase B.1** (realtime
voice). ``Transcript`` starts minimal; confidence, segments, and language land
with the LiveKit STT adapter.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Transcript:
    """The result of transcribing an audio buffer."""

    text: str


@runtime_checkable
class STTProvider(Protocol):
    """Port. Turns an audio buffer into a transcript."""

    async def recognize(
        self,
        audio: bytes,
        *,
        language: str | None = None,
    ) -> Transcript:
        """Transcribe ``audio``. ``language`` is an optional hint."""
        ...
