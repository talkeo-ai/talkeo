"""Keyless fake LiveKit plugins for the voice agent.

``AgentSession`` consumes LiveKit *plugin* objects (``llm.LLM`` / ``stt.STT`` /
``tts.TTS`` / ``vad.VAD``), not our domain ports — so ``FakeLLMProvider`` & co.
cannot drive a session. These fakes let ``build_session`` construct a complete
pipeline with **no API keys and no network**, selected by ``*_PROVIDER=fake``.

Scope (PR1): construct-only. They are valid, instantiable plugin instances so a
session can be *built* and its wiring asserted; the streaming bodies raise if
actually run. The running behaviour (canned audio/transcripts so `console`
boots end-to-end keyless) lands with the worker entrypoint that exercises it.
"""

from __future__ import annotations

from typing import Any, NoReturn

from livekit.agents import llm as lk_llm
from livekit.agents import stt as lk_stt
from livekit.agents import tts as lk_tts
from livekit.agents import vad as lk_vad

_SAMPLE_RATE = 24000
_NUM_CHANNELS = 1


def _not_runnable(kind: str) -> NoReturn:
    raise NotImplementedError(
        f"fake {kind} plugin is construct-only; running it lands with the agent "
        "worker entrypoint (#15)"
    )


class FakeLLM(lk_llm.LLM):
    """A LiveKit ``llm.LLM`` that constructs but does not run."""

    def chat(self, *, chat_ctx: Any = None, **kwargs: Any) -> NoReturn:
        _not_runnable("LLM")


class FakeSTT(lk_stt.STT):
    """A LiveKit ``stt.STT`` that constructs but does not run."""

    def __init__(self) -> None:
        super().__init__(
            capabilities=lk_stt.STTCapabilities(streaming=False, interim_results=False)
        )

    async def _recognize_impl(self, buffer: Any, **kwargs: Any) -> NoReturn:
        _not_runnable("STT")


class FakeTTS(lk_tts.TTS):
    """A LiveKit ``tts.TTS`` that constructs but does not run."""

    def __init__(self) -> None:
        super().__init__(
            capabilities=lk_tts.TTSCapabilities(streaming=False),
            sample_rate=_SAMPLE_RATE,
            num_channels=_NUM_CHANNELS,
        )

    def synthesize(self, text: str, **kwargs: Any) -> NoReturn:
        _not_runnable("TTS")


class FakeVAD(lk_vad.VAD):
    """A LiveKit ``vad.VAD`` that constructs but does not run.

    Used in place of Silero whenever STT is faked, so keyless construction never
    pays the cost of loading the Silero model.
    """

    def __init__(self) -> None:
        super().__init__(capabilities=lk_vad.VADCapabilities(update_interval=0.1))

    def stream(self, **kwargs: Any) -> NoReturn:
        _not_runnable("VAD")
