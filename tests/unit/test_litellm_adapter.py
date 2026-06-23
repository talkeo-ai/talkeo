import asyncio
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.core.config import Settings
from app.domain.providers.errors import LLMError
from app.domain.providers.messages import Message
from app.infrastructure.providers.llm.litellm import LiteLLMProvider


# --- fakes for the injected AsyncOpenAI client -------------------------------


def _chunk(content):
    """A streaming chunk shaped like an OpenAI delta."""
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=content))])


def _empty_choices_chunk():
    """A usage/keepalive chunk with no choices (some proxies emit these)."""
    return SimpleNamespace(choices=[])


class _FakeStream:
    """Async iterator over pre-baked chunks; can raise mid-stream."""

    def __init__(self, chunks, *, raise_at=None, error=None):
        self._chunks = list(chunks)
        self._raise_at = raise_at
        self._error = error
        self._i = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._raise_at is not None and self._i == self._raise_at:
            raise self._error
        if self._i >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._i]
        self._i += 1
        return chunk


class _FakeClient:
    """Stands in for AsyncOpenAI: client.chat.completions.create(...)."""

    def __init__(self, *, stream=None, create_error=None):
        async def create(**kwargs):
            if create_error is not None:
                raise create_error
            return stream

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


# --- helpers -----------------------------------------------------------------


def _request():
    return httpx.Request("POST", "http://gw/chat/completions")


def _response(status):
    return httpx.Response(status, request=_request())


def _provider(client, *, model="gpt-test"):
    settings = Settings(
        ENV="test",
        LLM_PROVIDER="litellm",
        LITELLM_BASE_URL="http://gw",
        LLM_MODEL=model,
    )
    return LiteLLMProvider(settings, client=client)


def _collect(provider, messages=None):
    messages = messages or [Message(role="user", content="hi")]

    async def run():
        return [delta async for delta in provider.stream_chat(messages)]

    return asyncio.run(run())


def _completion(content):
    """A non-streaming completion shaped like an OpenAI response."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def _complete(provider, messages=None, **kwargs):
    messages = messages or [Message(role="user", content="hi")]
    return asyncio.run(provider.complete(messages, **kwargs))


# --- streaming ---------------------------------------------------------------


def test_streams_text_deltas():
    client = _FakeClient(stream=_FakeStream([_chunk("Hel"), _chunk("lo"), _chunk("!")]))
    assert "".join(_collect(_provider(client))) == "Hello!"


def test_skips_none_content_and_empty_choices():
    client = _FakeClient(
        stream=_FakeStream([_chunk("a"), _chunk(None), _empty_choices_chunk(), _chunk("b")])
    )
    assert _collect(_provider(client)) == ["a", "b"]


def test_empty_stream_yields_nothing():
    client = _FakeClient(stream=_FakeStream([]))
    assert _collect(_provider(client)) == []


# --- error mapping -----------------------------------------------------------


@pytest.mark.parametrize(
    "exc, code",
    [
        (openai.APITimeoutError(request=_request()), "timeout"),
        (openai.RateLimitError("rate", response=_response(429), body=None), "rate_limit"),
        (openai.AuthenticationError("auth", response=_response(401), body=None), "auth"),
        (openai.BadRequestError("bad", response=_response(400), body=None), "bad_request"),
        (openai.APIError("boom", request=_request(), body=None), "provider_error"),
    ],
)
def test_create_errors_map_to_llm_error(exc, code):
    client = _FakeClient(create_error=exc)
    with pytest.raises(LLMError) as excinfo:
        _collect(_provider(client))
    assert excinfo.value.code == code


def test_error_raised_mid_stream_is_mapped():
    err = openai.RateLimitError("rate", response=_response(429), body=None)
    client = _FakeClient(stream=_FakeStream([_chunk("a")], raise_at=1, error=err))
    with pytest.raises(LLMError) as excinfo:
        _collect(_provider(client))
    assert excinfo.value.code == "rate_limit"


def test_cancellation_propagates_unwrapped():
    client = _FakeClient(
        stream=_FakeStream([_chunk("a")], raise_at=1, error=asyncio.CancelledError())
    )
    with pytest.raises(asyncio.CancelledError):
        _collect(_provider(client))


# --- complete (non-streaming) ------------------------------------------------


def test_complete_returns_full_text():
    # _FakeClient.create returns whatever `stream` holds; for the non-streaming
    # path that is a completion object, and complete() reads message.content.
    client = _FakeClient(stream=_completion('{"ok": true}'))
    assert _complete(_provider(client)) == '{"ok": true}'


def test_complete_none_content_returns_empty_string():
    client = _FakeClient(stream=_completion(None))
    assert _complete(_provider(client)) == ""


def test_complete_errors_map_to_llm_error():
    client = _FakeClient(
        create_error=openai.RateLimitError("rate", response=_response(429), body=None)
    )
    with pytest.raises(LLMError) as excinfo:
        _complete(_provider(client))
    assert excinfo.value.code == "rate_limit"


def test_complete_no_model_configured_fails_loud():
    provider = _provider(_FakeClient(stream=_completion("x")), model=None)
    with pytest.raises(LLMError) as excinfo:
        _complete(provider)
    assert excinfo.value.code == "config"


# --- config ------------------------------------------------------------------


def test_no_model_configured_fails_loud():
    provider = _provider(_FakeClient(stream=_FakeStream([])), model=None)
    with pytest.raises(LLMError) as excinfo:
        _collect(provider)
    assert excinfo.value.code == "config"
