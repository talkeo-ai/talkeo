import pytest
from livekit.agents import Agent, WorkerOptions

from app.agent.leo import _PROMPT_PATH, load_leo
from app.agent.main import require_livekit_creds, worker_options
from app.core.config import Settings


def _settings(**overrides) -> Settings:
    return Settings(ENV="test", _env_file=None, **overrides)


def _prod_settings(**overrides) -> Settings:
    # A production Settings needs real (non-fake) providers to pass the shared
    # validator; the keys themselves aren't validated until the registries run.
    base = dict(
        ENV="production",
        _env_file=None,
        LLM_PROVIDER="litellm",
        TTS_PROVIDER="livekit",
        STT_PROVIDER="livekit",
    )
    base.update(overrides)
    return Settings(**base)


# --- worker wiring (CI-safe: builds config, never calls cli.run_app) ----------


def test_worker_options_builds():
    opts = worker_options(
        _settings(
            LIVEKIT_URL="ws://localhost:7880",
            LIVEKIT_API_KEY="k",
            LIVEKIT_API_SECRET="s",
        )
    )
    assert isinstance(opts, WorkerOptions)
    assert opts.entrypoint_fnc is not None
    assert opts.prewarm_fnc is not None


# --- Leo persona -------------------------------------------------------------


def test_load_leo_returns_agent_with_prompt_from_file():
    agent = load_leo(_settings())
    assert isinstance(agent, Agent)
    assert agent.instructions == _PROMPT_PATH.read_text(encoding="utf-8").strip()
    assert agent.instructions  # non-empty


# --- LiveKit-cred prod safety (agent boot, not the shared validator) ----------


def test_require_creds_raises_in_prod_when_missing():
    with pytest.raises(ValueError, match="LiveKit credentials required"):
        require_livekit_creds(_prod_settings())


def test_require_creds_passes_in_prod_when_present():
    require_livekit_creds(
        _prod_settings(
            LIVEKIT_URL="ws://lk", LIVEKIT_API_KEY="k", LIVEKIT_API_SECRET="s"
        )
    )  # no raise


def test_require_creds_noop_in_dev_without_creds():
    require_livekit_creds(Settings(ENV="development", _env_file=None))  # no raise
