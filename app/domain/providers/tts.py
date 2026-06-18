"""Text-to-speech provider port.

Yields chunks of **raw PCM audio bytes** (streaming-first), so playback can
start as soon as the first chunk lands (issue #22). The adapter (issue #4)
hides the engine: LiveKit's ``synthesize()`` emits ``rtc.AudioFrame`` objects,
which the adapter unwraps into raw PCM — those framework types never cross this
port.

Wire contract (the format every engine is forced to emit): signed 16-bit
little-endian PCM, 24 kHz, mono. It is fixed, not negotiable per request, so the
`/speak` endpoint advertises it once via response headers and the clients
(AVAudioEngine / NAudio) configure playback before the first chunk arrives.
"""

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

# Raw PCM wire contract — see module docstring. Imported by the adapter (to
# document what it emits) and by the endpoint (to set the response headers).
PCM_SAMPLE_RATE = 24000
PCM_NUM_CHANNELS = 1
PCM_SAMPLE_WIDTH_BITS = 16


@runtime_checkable
class TTSProvider(Protocol):
    """Port. Turns text into a stream of raw PCM audio bytes."""

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
    ) -> AsyncIterator[bytes]:
        """Synthesize ``text`` to raw PCM audio (s16le, 24 kHz, mono).

        ``voice`` is optional; when ``None`` the adapter uses its configured
        default.
        """
        ...
