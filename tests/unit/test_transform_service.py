import asyncio
from collections.abc import AsyncIterator

from app.application.transform_service import TransformService
from app.infrastructure.providers.llm.fake import FakeLLMProvider


def _collect(agen: AsyncIterator[str]) -> list[str]:
    async def run() -> list[str]:
        return [delta async for delta in agen]

    return asyncio.run(run())


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


def test_explain_streams_deltas_with_term_and_sentence():
    # FakeLLMProvider echoes the last user message, so this proves both the term
    # and the sentence reach the user message (not buried in the system prompt).
    svc = TransformService(FakeLLMProvider())
    deltas = _collect(
        svc.explain(
            "jumps over",
            "The fox jumps over the dog.",
            source_lang="EN",
            target_lang="ES",
        )
    )
    joined = "".join(deltas)
    assert "jumps over" in joined
    assert "The fox jumps over the dog." in joined


def test_explain_auto_detect_branch_streams():
    svc = TransformService(FakeLLMProvider())
    deltas = _collect(svc.explain("lazy", "The lazy dog.", target_lang="ES"))
    assert "lazy" in "".join(deltas)
