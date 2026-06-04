"""Text-to-speech provider port.

Yields chunks of **encoded audio bytes** (streaming-first). The adapter
(issue #4) hides the engine: LiveKit's ``synthesize()`` emits ``rtc.AudioFrame``
objects, which the adapter assembles into an encoded stream — those framework
types never cross this port.
"""

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class TTSProvider(Protocol):
    """Port. Turns text into a stream of encoded audio bytes."""

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        audio_format: str | None = None,
    ) -> AsyncIterator[bytes]:
        """Synthesize ``text`` to audio.

        ``voice`` and ``audio_format`` are optional; when ``None`` the adapter
        uses its configured defaults.
        """
        ...
