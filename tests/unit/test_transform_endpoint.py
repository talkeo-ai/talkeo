from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_llm_provider
from app.domain.providers.errors import LLMError
from app.infrastructure.providers.llm.fake import FakeLLMProvider
from app.main import app

_URL = "/api/v1/transform/translate"


class _RaisingLLM:
    """Streams one delta, then fails — exercises the mid-stream error frame."""

    async def stream_chat(
        self, messages, *, model=None, temperature=None, max_tokens=None
    ) -> AsyncIterator[str]:
        yield "partial "
        raise LLMError("rate_limit", "slow down")


def _client(provider):
    app.dependency_overrides[get_llm_provider] = lambda: provider
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_translate_streams_sse():
    with _client(FakeLLMProvider()).stream(
        "POST", _URL, json={"text": "Hello", "target_lang": "ES"}
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = "".join(resp.iter_text())
    assert "data: " in body
    assert "event: done" in body
    assert "[DONE]" in body


def test_translate_empty_text_maps_to_400():
    resp = _client(FakeLLMProvider()).post(
        _URL, json={"text": "   ", "target_lang": "ES"}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "bad_request"


def test_translate_missing_target_lang_is_422():
    # target_lang is required by the request model.
    resp = _client(FakeLLMProvider()).post(_URL, json={"text": "hi"})
    assert resp.status_code == 422


def test_translate_provider_error_emits_error_frame():
    with _client(_RaisingLLM()).stream(
        "POST", _URL, json={"text": "Hello", "target_lang": "ES"}
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())
    assert "event: error" in body
    assert "rate_limit" in body
    assert "[DONE]" not in body  # a broken stream must not look cleanly finished
