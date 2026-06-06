import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.domain.providers.llm import LLMProvider
from app.domain.providers.stt import STTProvider
from app.domain.providers.tts import TTSProvider
from app.infrastructure.providers.llm.litellm import LiteLLMProvider
from app.infrastructure.providers.llm.registry import get_llm_provider
from app.infrastructure.providers.stt.registry import get_stt_provider
from app.infrastructure.providers.tts.registry import get_tts_provider


def _settings(**overrides) -> Settings:
    # ENV=test so the prod-safety validator never blocks fake providers here.
    return Settings(ENV="test", **overrides)


def test_registry_selects_fake_llm():
    provider = get_llm_provider(_settings(LLM_PROVIDER="fake"))
    assert isinstance(provider, LLMProvider)


def test_registry_selects_fake_tts():
    provider = get_tts_provider(_settings(TTS_PROVIDER="fake"))
    assert isinstance(provider, TTSProvider)


def test_registry_selects_fake_stt():
    provider = get_stt_provider(_settings(STT_PROVIDER="fake"))
    assert isinstance(provider, STTProvider)


def test_registry_selects_litellm():
    provider = get_llm_provider(
        _settings(
            LLM_PROVIDER="litellm",
            LITELLM_BASE_URL="http://gw",
            LLM_MODEL="m",
        )
    )
    assert isinstance(provider, LiteLLMProvider)
    assert isinstance(provider, LLMProvider)


def test_litellm_requires_base_url():
    with pytest.raises(ValueError, match="LITELLM_BASE_URL is required"):
        get_llm_provider(_settings(LLM_PROVIDER="litellm", LITELLM_BASE_URL=None))


def test_livekit_tts_adapter_not_yet_wired():
    with pytest.raises(ValueError, match="issue #4"):
        get_tts_provider(_settings(TTS_PROVIDER="livekit"))


def test_livekit_stt_adapter_not_yet_wired():
    with pytest.raises(ValueError, match="Phase B.1"):
        get_stt_provider(_settings(STT_PROVIDER="livekit"))


def test_fake_forbidden_in_production():
    with pytest.raises(ValidationError, match="fake provider not allowed"):
        Settings(ENV="production", LLM_PROVIDER="fake")


def test_fake_forbidden_in_staging():
    with pytest.raises(ValidationError, match="fake provider not allowed"):
        Settings(ENV="staging", TTS_PROVIDER="fake")


def test_fake_allowed_in_development():
    settings = Settings(ENV="development")
    assert settings.LLM_PROVIDER == "fake"
