import pytest

from app.application import prompts


@pytest.fixture(autouse=True)
def _tmp_prompts(tmp_path, monkeypatch):
    # Point the loader at a temp dir so tests own the templates and the cache
    # never leaks a real file (or vice versa) between cases.
    monkeypatch.setattr(prompts, "_PROMPTS_DIR", tmp_path)
    prompts._load.cache_clear()
    yield
    prompts._load.cache_clear()


def test_render_substitutes_placeholders(tmp_path):
    (tmp_path / "translate.md").write_text("from $source_lang to $target_lang")
    out = prompts.render_prompt("translate", source_lang="EN", target_lang="ES")
    assert out == "from EN to ES"


def test_render_leaves_unknown_tokens_intact(tmp_path):
    # safe_substitute: an unrelated `$token` (or a literal `$`) must not raise.
    (tmp_path / "x.md").write_text("price is $5 for $target_lang")
    assert prompts.render_prompt("x", target_lang="ES") == "price is $5 for ES"


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        prompts.render_prompt("does_not_exist")


def test_empty_file_raises(tmp_path):
    (tmp_path / "blank.md").write_text("   \n\t")
    with pytest.raises(ValueError, match="empty"):
        prompts.render_prompt("blank")
