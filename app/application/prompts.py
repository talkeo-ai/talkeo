"""Transform prompt loader (ADR-003: prompts as data).

Templates live in ``prompts/transform/*.md`` as plain markdown with ``$name``
placeholders — no logic, versioned in git, editable by non-engineers. This is
the "composition" half of ADR-003: a pure substitution over a cached file read.
Substitution stays simple (``string.Template``, no Jinja2) because the templates
carry no conditional logic; revisit if that changes.

Shared by the text-transform use cases (translate #21, explain #24, improve #8).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template

# repo_root/prompts/transform/  (this file is repo_root/app/application/prompts.py)
_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts" / "transform"


@lru_cache
def _load(name: str) -> str:
    """Read a template file once and cache it (the static portion never changes)."""
    path = _PROMPTS_DIR / f"{name}.md"
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"transform prompt is empty: {path}")
    return text


def render_prompt(name: str, /, **vars: str) -> str:
    """Render ``prompts/transform/{name}.md`` with ``$placeholder`` substitution.

    ``safe_substitute`` leaves unknown ``$tokens`` intact rather than raising, so
    a template can mention a literal ``$`` without breaking the render.
    """
    return Template(_load(name)).safe_substitute(vars)
