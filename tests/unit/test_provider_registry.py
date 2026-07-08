import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.domain.providers.llm import LLMProvider
from app.domain.providers.stt import STTProvider
from app.domain.providers.tts import TTSProvider
from app.infrastructure.providers.llm.litellm import LiteLLMProvider
from app.infrastructure.providers.llm.registry import get_llm_provider
from app.infrastructure.providers.tts.fish import FishTTSProvider
from app.infrastructure.providers.tts.livekit import LiveKitTTSProvider
from app.infrastructure.providers.stt.registry import get_stt_provider
from app.infrastructure.providers.tts.registry import get_tts_provider


def _settings(**overrides) -> Settings:
    # ENV=test so the prod-safety validator never blocks fake providers here.
    # _env_file=None keeps these tests hermetic — a developer's local .env (which
    # may carry real keys, e.g. OPENAI_API_KEY) must not change which branch the
    # registry takes, or assertions about a missing key would flip by environment.
    return Settings(ENV="test", _env_file=None, **overrides)


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


def test_registry_selects_livekit_tts():
    provider = get_tts_provider(
        _settings(
            TTS_PROVIDER="livekit",
            TTS_ENGINE="openai",
            OPENAI_API_KEY="sk-test",
        )
    )
    assert isinstance(provider, LiveKitTTSProvider)
    assert isinstance(provider, TTSProvider)


def test_livekit_tts_requires_api_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
        get_tts_provider(_settings(TTS_PROVIDER="livekit", TTS_ENGINE="openai"))


@pytest.mark.parametrize(
    "engine,key_name,key_value",
    [
        ("elevenlabs", "ELEVENLABS_API_KEY", "el-test"),
        ("cartesia", "CARTESIA_API_KEY", "cart-test"),
        ("deepgram", "DEEPGRAM_API_KEY", "dg-test"),
    ],
)
def test_registry_selects_livekit_tts_engines(engine, key_name, key_value):
    provider = get_tts_provider(
        _settings(TTS_PROVIDER="livekit", TTS_ENGINE=engine, **{key_name: key_value})
    )
    assert isinstance(provider, LiveKitTTSProvider)
    assert isinstance(provider, TTSProvider)


@pytest.mark.parametrize(
    "engine,key_name",
    [
        ("elevenlabs", "ELEVENLABS_API_KEY"),
        ("cartesia", "CARTESIA_API_KEY"),
        ("deepgram", "DEEPGRAM_API_KEY"),
    ],
)
def test_livekit_tts_engine_requires_its_key(engine, key_name):
    with pytest.raises(ValueError, match=f"{key_name} is required"):
        get_tts_provider(_settings(TTS_PROVIDER="livekit", TTS_ENGINE=engine))


def test_registry_selects_fish_tts():
    provider = get_tts_provider(_settings(TTS_PROVIDER="fish", FISH_API_KEY="fish-test"))
    assert isinstance(provider, FishTTSProvider)
    assert isinstance(provider, TTSProvider)


def test_fish_tts_requires_api_key():
    with pytest.raises(ValueError, match="FISH_API_KEY is required"):
        get_tts_provider(_settings(TTS_PROVIDER="fish"))


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
    # _env_file=None for hermeticity — a developer's local .env may set a real
    # provider, which would otherwise mask the development default asserted here.
    settings = Settings(ENV="development", _env_file=None)
    assert settings.LLM_PROVIDER == "fake"
