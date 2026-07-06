import asyncio
from types import SimpleNamespace

import pytest
from livekit import rtc
from livekit.agents import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
)

from app.core.config import Settings
from app.domain.providers.errors import TTSError
from app.infrastructure.providers.tts.livekit import (
    LiveKitTTSProvider,
    build_tts_plugin,
)

_SAMPLE_RATE = 24000


# --- fakes for the injected LiveKit TTS plugin -------------------------------


def _frame(samples=240):
    """A real rtc.AudioFrame of silence — cheap, no network."""
    return rtc.AudioFrame(b"\x00\x00" * samples, _SAMPLE_RATE, 1, samples)


def _audio(frame):
    """Shaped like tts.SynthesizedAudio (only `.frame` is read)."""
    return SimpleNamespace(frame=frame)


class _FakeStream:
    """Async iterator + async context manager over pre-baked frames; can raise."""

    def __init__(self, frames, *, raise_at=None, error=None):
        self._items = [_audio(f) for f in frames]
        self._raise_at = raise_at
        self._error = error
        self._i = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._raise_at is not None and self._i == self._raise_at:
            raise self._error
        if self._i >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._i]
        self._i += 1
        return item

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakePlugin:
    """Stands in for a LiveKit TTS plugin: plugin.synthesize(text, conn_options=...)."""

    def __init__(self, *, stream=None, synth_error=None):
        self._stream = stream
        self._synth_error = synth_error
        self.aclose_calls = 0

    def synthesize(self, text, *, conn_options=None):
        if self._synth_error is not None:
            raise self._synth_error
        return self._stream

    async def aclose(self):
        self.aclose_calls += 1


# --- helpers -----------------------------------------------------------------


def _provider(plugin):
    settings = Settings(
        ENV="test",
        TTS_PROVIDER="livekit",
        TTS_ENGINE="openai",
        OPENAI_API_KEY="sk-test",
    )
    return LiveKitTTSProvider(settings, tts=plugin)


def _collect(provider, text="hello", **kwargs):
    async def run():
        return [chunk async for chunk in provider.synthesize(text, **kwargs)]

    return asyncio.run(run())


# --- synthesis ---------------------------------------------------------------


def test_synthesize_yields_raw_pcm_chunks():
    # Two frames in → at least two chunks out (streamed as they arrive, not
    # buffered into one body), each the frame's raw s16le PCM bytes.
    plugin = _FakePlugin(stream=_FakeStream([_frame(), _frame()]))
    chunks = _collect(_provider(plugin))
    assert len(chunks) == 2
    assert all(isinstance(c, bytes) for c in chunks)

    pcm = b"".join(chunks)
    # 2 frames × 240 samples × 2 bytes/sample (16-bit mono) = 960 bytes of silence.
    assert pcm == b"\x00\x00" * 240 * 2
    assert len(pcm) == 2 * 240 * 2


def test_injected_plugin_is_not_closed():
    plugin = _FakePlugin(stream=_FakeStream([_frame()]))
    _collect(_provider(plugin))
    # We only close plugins we build; an injected one belongs to the caller.
    assert plugin.aclose_calls == 0


# --- input validation --------------------------------------------------------


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_empty_text_is_bad_request(text):
    plugin = _FakePlugin(stream=_FakeStream([_frame()]))
    with pytest.raises(TTSError) as excinfo:
        _collect(_provider(plugin), text=text)
    assert excinfo.value.code == "bad_request"


def test_no_audio_produced_is_provider_error():
    plugin = _FakePlugin(stream=_FakeStream([]))
    with pytest.raises(TTSError) as excinfo:
        _collect(_provider(plugin))
    assert excinfo.value.code == "provider_error"


# --- error mapping -----------------------------------------------------------


@pytest.mark.parametrize(
    "exc, code",
    [
        (APITimeoutError(), "timeout"),
        (APIStatusError("auth", status_code=401), "auth"),
        (APIStatusError("forbidden", status_code=403), "auth"),
        (APIStatusError("rate", status_code=429), "rate_limit"),
        (APIStatusError("bad", status_code=400), "bad_request"),
        (APIStatusError("boom", status_code=500), "provider_error"),
        (APIConnectionError(), "provider_error"),
        (APIError("boom"), "provider_error"),
    ],
)
def test_synthesize_errors_map_to_tts_error(exc, code):
    plugin = _FakePlugin(synth_error=exc)
    with pytest.raises(TTSError) as excinfo:
        _collect(_provider(plugin))
    assert excinfo.value.code == code
    assert plugin.aclose_calls == 0  # injected plugin is owned by the caller


def test_error_raised_mid_stream_is_mapped():
    err = APIStatusError("rate", status_code=429)
    plugin = _FakePlugin(stream=_FakeStream([_frame()], raise_at=1, error=err))
    with pytest.raises(TTSError) as excinfo:
        _collect(_provider(plugin))
    assert excinfo.value.code == "rate_limit"


def test_cancellation_propagates_unwrapped():
    plugin = _FakePlugin(
        stream=_FakeStream([_frame()], raise_at=1, error=asyncio.CancelledError())
    )
    with pytest.raises(asyncio.CancelledError):
        _collect(_provider(plugin))


# --- build_tts_plugin: engine is the caller's argument, not read from settings


def test_build_tts_plugin_openai():
    plugin = build_tts_plugin(
        Settings(ENV="test", _env_file=None, OPENAI_API_KEY="sk-test"),
        engine="openai",
    )
    assert "openai" in type(plugin).__module__


def test_build_tts_plugin_elevenlabs():
    plugin = build_tts_plugin(
        Settings(ENV="test", _env_file=None, ELEVENLABS_API_KEY="el-test"),
        engine="elevenlabs",
    )
    assert "elevenlabs" in type(plugin).__module__


def test_build_tts_plugin_cartesia():
    plugin = build_tts_plugin(
        Settings(ENV="test", _env_file=None, CARTESIA_API_KEY="cart-test"),
        engine="cartesia",
    )
    assert "cartesia" in type(plugin).__module__


def test_build_tts_plugin_deepgram():
    plugin = build_tts_plugin(
        Settings(ENV="test", _env_file=None, DEEPGRAM_API_KEY="dg-test"),
        engine="deepgram",
    )
    assert "deepgram" in type(plugin).__module__


def test_build_tts_plugin_unknown_engine():
    with pytest.raises(TTSError) as excinfo:
        build_tts_plugin(Settings(ENV="test", _env_file=None), engine="bogus")
    assert excinfo.value.code == "config"
