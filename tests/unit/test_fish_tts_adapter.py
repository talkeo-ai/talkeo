import asyncio
import json

import httpx
import pytest

from app.core.config import Settings
from app.domain.providers.errors import TTSError
from app.infrastructure.providers.tts.fish import FishTTSProvider


def _settings(**overrides) -> Settings:
    return Settings(ENV="test", _env_file=None, FISH_API_KEY="fish-test", **overrides)


def _provider(handler, **settings_overrides) -> FishTTSProvider:
    """A Fish adapter whose HTTP goes to an in-memory mock transport — no network,
    no key. The handler inspects the request and returns a canned response."""
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return FishTTSProvider(_settings(**settings_overrides), client=client)


def _collect(provider, text="hello", **kwargs):
    async def run():
        return [chunk async for chunk in provider.synthesize(text, **kwargs)]

    return asyncio.run(run())


# --- synthesis ---------------------------------------------------------------


def test_synthesize_yields_raw_pcm_bytes():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["headers"] = request.headers
        return httpx.Response(200, content=b"\x01\x02\x03\x04")

    chunks = _collect(_provider(handler))
    assert b"".join(chunks) == b"\x01\x02\x03\x04"
    # PCM wire format is pinned in the request, not negotiated.
    assert captured["body"]["format"] == "pcm"
    assert captured["body"]["sample_rate"] == 24000
    assert captured["headers"]["authorization"] == "Bearer fish-test"
    assert captured["headers"]["model"] == "s2-pro"


def test_trailing_period_is_stripped():
    # Known Fish quirk: a trailing period truncates the audio.
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["text"] = json.loads(request.content)["text"]
        return httpx.Response(200, content=b"\x00\x00")

    _collect(_provider(handler), text="Hello there.")
    assert captured["text"] == "Hello there"


def test_reference_id_from_settings_voice():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, content=b"\x00\x00")

    _collect(_provider(handler, FISH_VOICE="voice-123"))
    assert captured["body"]["reference_id"] == "voice-123"


def test_per_request_voice_overrides_settings():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, content=b"\x00\x00")

    _collect(_provider(handler, FISH_VOICE="settings-voice"), voice="call-voice")
    assert captured["body"]["reference_id"] == "call-voice"


def test_no_reference_id_when_unset():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, content=b"\x00\x00")

    _collect(_provider(handler))
    assert "reference_id" not in captured["body"]


# --- errors ------------------------------------------------------------------


@pytest.mark.parametrize("text", ["", "   ", ".", "  .  "])
def test_empty_text_is_bad_request(text):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("should not call the API for empty text")

    with pytest.raises(TTSError) as excinfo:
        _collect(_provider(handler), text=text)
    assert excinfo.value.code == "bad_request"


@pytest.mark.parametrize(
    "status,code",
    [
        (400, "bad_request"),
        (401, "auth"),
        (403, "auth"),
        (429, "rate_limit"),
        (500, "provider_error"),
        (503, "provider_error"),
    ],
)
def test_http_errors_map_to_tts_error(status, code):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=b"upstream said no")

    with pytest.raises(TTSError) as excinfo:
        _collect(_provider(handler))
    assert excinfo.value.code == code


def test_empty_body_is_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    with pytest.raises(TTSError) as excinfo:
        _collect(_provider(handler))
    assert excinfo.value.code == "provider_error"


def test_transport_failure_is_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with pytest.raises(TTSError) as excinfo:
        _collect(_provider(handler))
    assert excinfo.value.code == "provider_error"
