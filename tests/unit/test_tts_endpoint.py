from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_tts_provider
from app.domain.providers.errors import TTSError
from app.infrastructure.providers.tts.fake import FakeTTSProvider
from app.main import app


class _RaisingTTS:
    """Provider stub whose stream raises a TTSError on the first chunk."""

    def __init__(self, code: str) -> None:
        self._code = code

    async def synthesize(self, text, *, voice=None) -> AsyncIterator[bytes]:
        raise TTSError(self._code, f"{self._code} failed")
        yield b""  # pragma: no cover — marks this an async generator


class _ChunkThenRaiseTTS:
    """Yields one chunk, then fails — exercises the after-streaming-starts path."""

    async def synthesize(self, text, *, voice=None) -> AsyncIterator[bytes]:
        yield b"first-chunk"
        raise TTSError("provider_error", "died mid-stream")


def _client(provider, *, raise_server_exceptions=True):
    app.dependency_overrides[get_tts_provider] = lambda: provider
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_speak_streams_raw_pcm():
    resp = _client(FakeTTSProvider()).post("/api/v1/tts/speak", json={"text": "hi"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/pcm"
    # Wire-format headers let the client configure playback before the first chunk.
    assert resp.headers["x-sample-rate"] == "24000"
    assert resp.headers["x-channels"] == "1"
    assert resp.headers["x-bits-per-sample"] == "16"
    # Streamed (chunked), not buffered: no Content-Length is set.
    assert "content-length" not in resp.headers
    assert resp.content == b"fake audio for: hi"


def test_speak_empty_text_maps_to_400():
    resp = _client(FakeTTSProvider()).post("/api/v1/tts/speak", json={"text": "   "})
    assert resp.status_code == 400
    assert resp.json()["code"] == "bad_request"


def test_speak_first_chunk_bad_request_maps_to_400():
    resp = _client(_RaisingTTS("bad_request")).post(
        "/api/v1/tts/speak", json={"text": "hi"}
    )
    assert resp.status_code == 400
    assert resp.json() == {"code": "bad_request", "message": "bad_request failed"}


def test_speak_first_chunk_provider_error_maps_to_502():
    resp = _client(_RaisingTTS("provider_error")).post(
        "/api/v1/tts/speak", json={"text": "hi"}
    )
    assert resp.status_code == 502
    assert resp.json()["code"] == "provider_error"


def test_speak_error_after_first_chunk_surfaces_as_stream_failure():
    # Once the first chunk is on the wire the 200 is committed, so a later
    # failure can't become a clean status — it tears the stream down instead.
    # In production that closes the connection; the client treats the truncated
    # stream as an error. (TestClient re-raises the server-side exception.)
    with pytest.raises(TTSError):
        _client(_ChunkThenRaiseTTS()).post("/api/v1/tts/speak", json={"text": "hi"})
