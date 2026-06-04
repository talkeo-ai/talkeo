"""Provider error model.

Adapters translate engine-specific exceptions (LiteLLM, LiveKit, HTTP) into
these domain errors. The ``(code, message)`` shape mirrors
``app.api.sse.StreamError`` so a failing provider maps straight onto the SSE
``error`` frame: ``code`` is a stable machine token the client switches on,
``message`` is human-readable and client-safe (never carries internals).
"""


class ProviderError(Exception):
    """Base for every provider failure (LLM, TTS, STT)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class LLMError(ProviderError):
    """An LLM provider failed."""


class TTSError(ProviderError):
    """A text-to-speech provider failed."""


class STTError(ProviderError):
    """A speech-to-text provider failed."""
