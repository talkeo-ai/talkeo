"""Shared pytest fixtures.

The one job here is hermeticity: keep the unit suite independent of whatever
`.env` happens to sit in the working tree.
"""

import pytest

from app.core import config


@pytest.fixture(autouse=True)
def _hermetic_settings(monkeypatch):
    """Isolate every test from the developer's local ``.env``.

    ``Settings`` defaults to reading ``.env`` (``SettingsConfigDict(env_file=...)``),
    so a real local file leaks into unit tests: it flips which provider the
    registry selects and can even fail validation outright (e.g. an unrecognised
    ``TTS_PROVIDER`` value), turning the suite red on any machine that has one.
    Force pydantic to skip the env file for the whole suite so tests depend only
    on the values they pass explicitly. Tests that need particular settings still
    construct ``Settings(...)`` with their own overrides; those that build a
    ``TransformService`` or hit the app get a clean, default ``Settings`` instead
    of the ambient one.
    """
    monkeypatch.setitem(config.Settings.model_config, "env_file", None)
    # get_settings() is lru_cached; drop any value built before the patch and
    # after teardown so no test inherits another's (or the real .env's) settings.
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()
