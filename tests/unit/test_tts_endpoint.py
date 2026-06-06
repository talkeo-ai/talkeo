from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_tts_provider
from app.domain.providers.errors import TTSError
from app.infrastructure.providers.tts.fake import FakeTTSProvider
from app.main import app


class _RaisingTTS:
    """Provider stub whose stream raises a TTSError on first iteration."""

    def __init__(self, code: str) -> None:
        self._code = code

    async def synthesize(self, text, *, voice=None, audio_format=None) -> AsyncIterator[bytes]:
        raise TTSError(self._code, f"{self._code} failed")
        yield b""  # pragma: no cover — marks this an async generator


def _client(provider):
    app.dependency_overrides[get_tts_provider] = lambda: provider
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_speak_returns_wav():
    resp = _client(FakeTTSProvider()).post("/api/v1/tts/speak", json={"text": "hi"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"
    assert resp.content  # non-empty body


def test_speak_bad_request_maps_to_400():
    resp = _client(_RaisingTTS("bad_request")).post(
        "/api/v1/tts/speak", json={"text": "hi"}
    )
    assert resp.status_code == 400
    assert resp.json() == {"code": "bad_request", "message": "bad_request failed"}


def test_speak_provider_error_maps_to_502():
    resp = _client(_RaisingTTS("provider_error")).post(
        "/api/v1/tts/speak", json={"text": "hi"}
    )
    assert resp.status_code == 502
    assert resp.json()["code"] == "provider_error"
