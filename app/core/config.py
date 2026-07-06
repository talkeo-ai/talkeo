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

    # Per-feature model overrides (translate / explain / improve). Each falls back
    # to LLM_MODEL when unset — same shape as AGENT_LLM_MODEL. Only the *model
    # name* varies per feature; the endpoint stays the single LiteLLM gateway
    # (ADR-008), which routes by model name to the provider behind it. Example:
    # IMPROVE_LLM_MODEL=openai/gpt-oss-120b while the rest run the default model.
    TRANSLATE_LLM_MODEL: str | None = None
    EXPLAIN_LLM_MODEL: str | None = None
    IMPROVE_LLM_MODEL: str | None = None

    # LiveKit TTS adapter (#4). `TTS_ENGINE` picks the LiveKit plugin behind the
    # `livekit` adapter; swapping it is config-only. Voice/model are optional —
    # `None` lets the plugin use its own default. Keys are required (validated in
    # the registry) only for the selected engine. `TTS_TIMEOUT` bounds the
    # standalone synthesize call. Output is raw PCM (s16le, 24 kHz, mono) —
    # the fixed `TTSProvider` wire format, not configurable per request.
    TTS_ENGINE: Literal["openai", "elevenlabs"] = "openai"
    TTS_VOICE: str | None = None
    TTS_MODEL: str | None = None
    TTS_TIMEOUT: float = 30.0
    OPENAI_API_KEY: str | None = None
    ELEVENLABS_API_KEY: str | None = None

    # Voice agent (LiveKit Agents worker, #15) — settings are named by surface so
    # the agent can run different engines/models than the api's /speak. The agent
    # is the sole STT consumer (#7 was dropped), so `AGENT_STT_*` stand alone with
    # no fallback. Keys are shared with TTS (`OPENAI_API_KEY` / `ELEVENLABS_API_KEY`).
    AGENT_STT_ENGINE: Literal["openai", "elevenlabs"] = "openai"
    AGENT_STT_MODEL: str | None = None
    AGENT_STT_LANGUAGE: str | None = None

    # `AGENT_TTS_ENGINE` lets the agent pick a cheaper/different TTS engine than
    # /speak; it falls back to `TTS_ENGINE` when unset. `AGENT_LLM_MODEL` falls
    # back to `LLM_MODEL` — the agent reaches the SAME LiteLLM gateway as the api
    # (ADR-008) via LiveKit's native `openai.LLM`, so both run off one gateway.
    # LiveKit room credentials are required only to run the worker (validated at
    # agent boot, not here — the api service runs in prod without them).
    AGENT_TTS_ENGINE: Literal["openai", "elevenlabs"] | None = None
    AGENT_LLM_MODEL: str | None = None
    LIVEKIT_URL: str | None = None
    LIVEKIT_API_KEY: str | None = None
    LIVEKIT_API_SECRET: str | None = None

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
