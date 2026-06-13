import asyncio

import pytest
from livekit.agents import AgentSession

from app.agent.fakes import FakeLLM, FakeSTT, FakeTTS, FakeVAD
from app.agent.pipeline import _build_llm, _build_tts, build_session
from app.core.config import Settings


def _settings(**overrides) -> Settings:
    # _env_file=None keeps the agent tests hermetic — a developer's local .env
    # (real keys / a real gateway) must not change what the builders select.
    return Settings(ENV="test", _env_file=None, **overrides)


def _build(settings, **kwargs) -> AgentSession:
    # AgentSession.__init__ grabs the running loop; in production the worker
    # entrypoint is async, so here we build inside asyncio.run.
    async def run() -> AgentSession:
        return build_session(settings, **kwargs)

    return asyncio.run(run())


# --- wiring ------------------------------------------------------------------


def test_build_session_wires_injected_plugins():
    vad, stt, llm, tts = FakeVAD(), FakeSTT(), FakeLLM(), FakeTTS()
    session = _build(_settings(), vad=vad, stt=stt, llm=llm, tts=tts)
    assert isinstance(session, AgentSession)
    assert session.vad is vad
    assert session.stt is stt
    assert session.llm is llm
    assert session.tts is tts


def test_fake_providers_build_a_keyless_session():
    # *_PROVIDER=fake builds a complete session with no keys / no network and no
    # Silero model load — every plugin is a fake.
    session = _build(
        _settings(LLM_PROVIDER="fake", STT_PROVIDER="fake", TTS_PROVIDER="fake")
    )
    assert isinstance(session.llm, FakeLLM)
    assert isinstance(session.stt, FakeSTT)
    assert isinstance(session.tts, FakeTTS)
    assert isinstance(session.vad, FakeVAD)


# --- LLM gateway wiring ------------------------------------------------------


def test_agent_llm_points_at_gateway_with_model_override():
    # AGENT_LLM_MODEL wins over LLM_MODEL; the plugin is built against the
    # shared LiteLLM gateway (construction does not hit the network).
    llm = _build_llm(
        _settings(
            LLM_PROVIDER="litellm",
            LITELLM_BASE_URL="http://gw",
            LLM_MODEL="api-model",
            AGENT_LLM_MODEL="agent-model",
        )
    )
    assert llm.model == "agent-model"


def test_agent_llm_falls_back_to_llm_model():
    llm = _build_llm(
        _settings(
            LLM_PROVIDER="litellm",
            LITELLM_BASE_URL="http://gw",
            LLM_MODEL="api-model",
        )
    )
    assert llm.model == "api-model"


def test_agent_llm_requires_base_url():
    with pytest.raises(ValueError, match="LITELLM_BASE_URL is required"):
        _build_llm(_settings(LLM_PROVIDER="litellm", LLM_MODEL="m"))


def test_agent_llm_requires_a_model():
    with pytest.raises(ValueError, match="AGENT_LLM_MODEL or LLM_MODEL is required"):
        _build_llm(_settings(LLM_PROVIDER="litellm", LITELLM_BASE_URL="http://gw"))


# --- agent TTS engine is independent of /speak's TTS_ENGINE -------------------


def test_agent_tts_engine_overrides_speak_engine():
    # /speak uses openai; the agent picks elevenlabs (e.g. a cheaper voice).
    tts = _build_tts(
        _settings(
            TTS_PROVIDER="livekit",
            TTS_ENGINE="openai",
            OPENAI_API_KEY="sk-test",
            AGENT_TTS_ENGINE="elevenlabs",
            ELEVENLABS_API_KEY="el-test",
        )
    )
    assert "elevenlabs" in type(tts).__module__


def test_agent_tts_engine_falls_back_to_speak_engine():
    # No AGENT_TTS_ENGINE → the agent reuses /speak's TTS_ENGINE.
    tts = _build_tts(
        _settings(TTS_PROVIDER="livekit", TTS_ENGINE="openai", OPENAI_API_KEY="sk-test")
    )
    assert "openai" in type(tts).__module__
