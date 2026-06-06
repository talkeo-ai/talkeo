from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    APP_NAME: str = "talkeo"
    ENV: Literal["development", "staging", "production", "test"] = "development"
    LOG_LEVEL: str = "INFO"

    # Provider selection. `fake` runs with no keys (dev / self-hosted), and is
    # forbidden in real environments by the validator below. Real adapters land
    # in #3 (litellm) and #4/B.1 (livekit).
    LLM_PROVIDER: Literal["fake", "litellm"] = "fake"
    TTS_PROVIDER: Literal["fake", "livekit"] = "fake"
    STT_PROVIDER: Literal["fake", "livekit"] = "fake"

    # LiteLLM gateway (used by the litellm adapter in #3). Documented in
    # .env.example; no real default — the fake adapter needs none.
    LITELLM_BASE_URL: str | None = None
    LITELLM_API_KEY: str | None = None
    LLM_MODEL: str | None = None

    # LiteLLM client timeouts in seconds, env-overridable. `connect` bounds the
    # TCP handshake to the gateway; `read` bounds waiting on the gateway / model
    # stream. Used by the litellm adapter (#3).
    LLM_CONNECT_TIMEOUT: float = 5.0
    LLM_READ_TIMEOUT: float = 60.0

    # LiveKit TTS adapter (#4). `TTS_ENGINE` picks the LiveKit plugin behind the
    # `livekit` adapter; swapping it is config-only. Voice/model are optional —
    # `None` lets the plugin use its own default. Keys are required (validated in
    # the registry) only for the selected engine. `TTS_TIMEOUT` bounds the
    # standalone synthesize call. Only `wav` output is supported today.
    TTS_ENGINE: Literal["openai", "elevenlabs"] = "openai"
    TTS_VOICE: str | None = None
    TTS_MODEL: str | None = None
    TTS_AUDIO_FORMAT: str = "wav"
    TTS_TIMEOUT: float = 30.0
    OPENAI_API_KEY: str | None = None
    ELEVENLABS_API_KEY: str | None = None

    # Reserved for Phase B+. Unused in Phase A.
    DB_URL: str | None = None

    @model_validator(mode="after")
    def _forbid_fake_in_real_envs(self) -> "Settings":
        """Fail fast at startup if a fake provider would run in staging/prod.

        The `fake` default keeps dev zero-config, but a fake silently serving a
        real deployment is a production hazard. Require an explicit real
        provider once ENV leaves development/test.
        """
        if self.ENV in ("staging", "production"):
            fakes = [
                name
                for name, value in (
                    ("LLM_PROVIDER", self.LLM_PROVIDER),
                    ("TTS_PROVIDER", self.TTS_PROVIDER),
                    ("STT_PROVIDER", self.STT_PROVIDER),
                )
                if value == "fake"
            ]
            if fakes:
                raise ValueError(
                    f"fake provider not allowed when ENV={self.ENV}: "
                    + ", ".join(fakes)
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
