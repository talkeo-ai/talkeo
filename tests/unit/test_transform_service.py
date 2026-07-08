import asyncio
import json
from collections.abc import AsyncIterator

import pytest

from app.application.cards import ExplainCard
from app.application.improvements import ImproveResult
from app.application.transform_service import TransformService
from app.core.config import Settings
from app.domain.providers.errors import LLMError
from app.infrastructure.providers.llm.fake import FakeLLMProvider


def _settings(**overrides) -> Settings:
    # ENV=test + _env_file=None keep these hermetic — the model asserted below
    # must come from the overrides here, never from a developer's local .env.
    return Settings(ENV="test", _env_file=None, **overrides)


def _collect(agen: AsyncIterator[str]) -> list[str]:
    async def run() -> list[str]:
        return [delta async for delta in agen]

    return asyncio.run(run())


def _run(coro):
    return asyncio.run(coro)


class _JsonLLM:
    """Stub LLM whose ``complete`` returns a fixed string (valid or malformed)."""

    def __init__(self, payload: str) -> None:
        self._payload = payload

    async def complete(self, messages, **kwargs) -> str:
        return self._payload


_VALID_CARD = json.dumps(
    {
        "term": "get rid of",
        "category": "phrasal verb",
        "meanings": ["deshacerse de", "eliminar"],
        "examples": [{"source": "**get rid of** it", "target": "deshacerse de eso"}],
        "insight": {"type": "pattern", "text": "Va siempre con 'of'."},
    }
)


def test_translate_streams_deltas_from_the_text():
    # FakeLLMProvider echoes the last *user* message, so this also proves the
    # text is passed as the user message (not buried in the system prompt).
    svc = TransformService(FakeLLMProvider())
    deltas = _collect(svc.translate("Hello fox", target_lang="ES"))
    assert all(isinstance(d, str) for d in deltas)
    assert "".join(deltas).strip() == "fake reply to: Hello fox"


def test_translate_auto_detect_branch_streams():
    # source_lang=None exercises the auto-detect fallback clause without error.
    svc = TransformService(FakeLLMProvider())
    deltas = _collect(svc.translate("Bonjour", target_lang="EN"))
    assert "".join(deltas).strip() == "fake reply to: Bonjour"


def test_explain_returns_parsed_card():
    svc = TransformService(_JsonLLM(_VALID_CARD))
    card = _run(
        svc.explain("get rid of", "I want to get rid of it.", target_lang="ES")
    )
    assert isinstance(card, ExplainCard)
    assert card.term == "get rid of"
    assert card.category == "phrasal verb"
    assert card.meanings[0] == "deshacerse de"
    assert card.examples[0].source == "**get rid of** it"
    assert card.insight is not None and card.insight.type == "pattern"


def test_explain_strips_code_fences():
    fenced = f"```json\n{_VALID_CARD}\n```"
    svc = TransformService(_JsonLLM(fenced))
    card = _run(svc.explain("x", "a sentence with x", target_lang="ES"))
    assert card.term == "get rid of"


def test_explain_malformed_json_raises_provider_error():
    svc = TransformService(_JsonLLM("not json at all"))
    with pytest.raises(LLMError) as excinfo:
        _run(svc.explain("x", "a sentence with x", target_lang="ES"))
    assert excinfo.value.code == "provider_error"


def test_explain_schema_mismatch_raises_provider_error():
    # Valid JSON, wrong shape (empty meanings violates min_length=1).
    bad = json.dumps({"term": "x", "category": "noun", "meanings": []})
    svc = TransformService(_JsonLLM(bad))
    with pytest.raises(LLMError) as excinfo:
        _run(svc.explain("x", "a sentence with x", target_lang="ES"))
    assert excinfo.value.code == "provider_error"


def test_explain_fake_provider_returns_valid_card():
    # The dev fake produces a real card so mac#4 can render with no keys.
    svc = TransformService(FakeLLMProvider())
    card = _run(svc.explain("jumps over", "The fox jumps over.", target_lang="ES"))
    assert isinstance(card, ExplainCard)
    assert card.term == "jumps over"  # echoed from the user message


# --- improve (structured JSON) ----------------------------------------------


_VALID_IMPROVE = json.dumps(
    {
        "improved": "These improvements are great.",
        "changes": [
            {
                "original": "This improvements",
                "fixed": "These improvements",
                "why": "Con plural va 'these', no 'this'.",
                "type": "grammar",
                "examples": [
                    {"source": "**These** books", "target": "**Estos** libros"}
                ],
            }
        ],
    }
)


def test_improve_returns_parsed_result():
    svc = TransformService(_JsonLLM(_VALID_IMPROVE))
    result = _run(svc.improve("This improvements are great.", target_lang="ES"))
    assert isinstance(result, ImproveResult)
    assert result.improved == "These improvements are great."
    assert len(result.changes) == 1
    change = result.changes[0]
    assert change.original == "This improvements"
    assert change.fixed == "These improvements"
    assert change.type == "grammar"
    assert change.examples[0].source == "**These** books"


def test_improve_malformed_json_raises_provider_error():
    svc = TransformService(_JsonLLM("not json at all"))
    with pytest.raises(LLMError) as excinfo:
        _run(svc.improve("some text", target_lang="ES"))
    assert excinfo.value.code == "provider_error"


def test_improve_already_natural_returns_empty_changes():
    # The dev fake echoes the text with no changes: the "already natural" path.
    svc = TransformService(FakeLLMProvider())
    result = _run(svc.improve("This is already perfect.", target_lang="ES"))
    assert isinstance(result, ImproveResult)
    assert result.improved == "This is already perfect."
    assert result.changes == []


# --- per-feature model routing ----------------------------------------------


class _ModelSpyLLM:
    """Records the ``model`` kwarg each call receives, so a test can assert the
    model TransformService resolves per feature actually reaches the provider."""

    def __init__(self, payload: str = "{}") -> None:
        self._payload = payload
        self.model: str | None = None

    async def complete(self, messages, *, model=None, **kwargs) -> str:
        self.model = model
        return self._payload

    async def stream_chat(self, messages, *, model=None, **kwargs) -> AsyncIterator[str]:
        self.model = model
        yield "x"


def test_translate_passes_per_feature_model_to_provider():
    spy = _ModelSpyLLM()
    svc = TransformService(
        spy, _settings(TRANSLATE_LLM_MODEL="groq/translate-x", LLM_MODEL="default-m")
    )
    _collect(svc.translate("hi", target_lang="ES"))
    assert spy.model == "groq/translate-x"


def test_explain_passes_per_feature_model_to_provider():
    spy = _ModelSpyLLM(_VALID_CARD)
    svc = TransformService(
        spy, _settings(EXPLAIN_LLM_MODEL="groq/explain-x", LLM_MODEL="default-m")
    )
    _run(svc.explain("x", "a sentence with x", target_lang="ES"))
    assert spy.model == "groq/explain-x"


def test_improve_passes_per_feature_model_to_provider():
    spy = _ModelSpyLLM(_VALID_IMPROVE)
    svc = TransformService(
        spy, _settings(IMPROVE_LLM_MODEL="groq/improve-x", LLM_MODEL="default-m")
    )
    _run(svc.improve("some text", target_lang="ES"))
    assert spy.model == "groq/improve-x"


def test_model_falls_back_to_llm_model_when_per_feature_unset():
    # No IMPROVE_LLM_MODEL: the resolved model must be the global LLM_MODEL.
    spy = _ModelSpyLLM(_VALID_IMPROVE)
    svc = TransformService(spy, _settings(LLM_MODEL="default-m"))
    _run(svc.improve("some text", target_lang="ES"))
    assert spy.model == "default-m"
