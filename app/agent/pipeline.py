"""Voice agent pipeline — wires a LiveKit ``AgentSession`` from ``Settings``.

The agent runs the realtime STT → LLM → TTS loop inside an ``AgentSession``
(ADR-008). The LLM plugin points at the **same LiteLLM gateway** the api uses
(``openai.LLM(base_url=...)``) — shared gateway, not a shared adapter object,
because the session consumes LiveKit *plugins*, not our domain ports. The TTS
plugin is the very one the one-shot adapter builds (``build_tts_plugin``), so
speech is integrated once and reused across surfaces.

Each plugin is injectable so tests build a session with no network or keys, and
``*_PROVIDER=fake`` selects keyless fakes so ``console``/``dev`` boot without
credentials.
"""

from __future__ import annotations

from livekit.agents import AgentSession
from livekit.agents import llm as lk_llm
from livekit.agents import stt as lk_stt
from livekit.agents import tts as lk_tts
from livekit.agents import vad as lk_vad

from app.agent.fakes import FakeLLM, FakeSTT, FakeTTS, FakeVAD
from app.core.config import Settings
from app.infrastructure.providers.tts.livekit import build_tts_plugin


def build_session(
    settings: Settings,
    *,
    vad: lk_vad.VAD | None = None,
    stt: lk_stt.STT | None = None,
    llm: lk_llm.LLM | None = None,
    tts: lk_tts.TTS | None = None,
) -> AgentSession:
    """Build (not start) the agent's ``AgentSession`` from ``settings``.

    Pass any plugin to override what config would build — tests inject fakes;
    the worker prewarms and injects the Silero VAD. Anything left ``None`` is
    built from config, with ``*_PROVIDER=fake`` selecting keyless fakes.
    """
    return AgentSession(
        vad=vad or _build_vad(settings),
        stt=stt or _build_stt(settings),
        llm=llm or _build_llm(settings),
        tts=tts or _build_tts(settings),
    )


def _build_llm(settings: Settings) -> lk_llm.LLM:
    """LiveKit ``openai.LLM`` pointed at the LiteLLM gateway (ADR-008)."""
    if settings.LLM_PROVIDER == "fake":
        return FakeLLM()

    model = settings.AGENT_LLM_MODEL or settings.LLM_MODEL
    if not settings.LITELLM_BASE_URL:
        raise ValueError("LITELLM_BASE_URL is required to run the voice agent LLM")
    if not model:
        raise ValueError("AGENT_LLM_MODEL or LLM_MODEL is required to run the voice agent")

    from livekit.plugins import openai

    return openai.LLM(
        base_url=settings.LITELLM_BASE_URL,
        api_key=settings.LITELLM_API_KEY or "sk-noauth",
        model=model,
    )


def _build_stt(settings: Settings) -> lk_stt.STT:
    """LiveKit STT plugin for in-session recognition; engine picked by config."""
    if settings.STT_PROVIDER == "fake":
        return FakeSTT()

    if settings.AGENT_STT_ENGINE == "openai":
        from livekit.plugins import openai

        kwargs: dict[str, str] = {"api_key": settings.OPENAI_API_KEY or ""}
        if settings.AGENT_STT_MODEL:
            kwargs["model"] = settings.AGENT_STT_MODEL
        if settings.AGENT_STT_LANGUAGE:
            kwargs["language"] = settings.AGENT_STT_LANGUAGE
        return openai.STT(**kwargs)

    if settings.AGENT_STT_ENGINE == "elevenlabs":
        from livekit.plugins import elevenlabs

        kwargs = {"api_key": settings.ELEVENLABS_API_KEY or ""}
        if settings.AGENT_STT_MODEL:
            kwargs["model_id"] = settings.AGENT_STT_MODEL
        if settings.AGENT_STT_LANGUAGE:
            kwargs["language_code"] = settings.AGENT_STT_LANGUAGE
        return elevenlabs.STT(**kwargs)

    raise ValueError(f"unknown STT engine: {settings.AGENT_STT_ENGINE!r}")


def _build_tts(settings: Settings) -> lk_tts.TTS:
    """Same builder the one-shot adapter uses (#4), but the agent picks its own
    engine: AGENT_TTS_ENGINE, falling back to TTS_ENGINE."""
    if settings.TTS_PROVIDER == "fake":
        return FakeTTS()
    engine = settings.AGENT_TTS_ENGINE or settings.TTS_ENGINE
    return build_tts_plugin(settings, engine=engine)


def _build_vad(settings: Settings) -> lk_vad.VAD:
    """Silero VAD, or a keyless fake when STT is faked (skips the model load)."""
    if settings.STT_PROVIDER == "fake":
        return FakeVAD()

    from livekit.plugins import silero

    return silero.VAD.load()
