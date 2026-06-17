"""Leo — the voice agent's persona.

Loads the system prompt as data (ADR-003: no prompt strings hardcoded in Python)
and returns a configured LiveKit ``Agent``. The minimal first-loop prompt lives
in ``prompts/leo/system.md``; the production persona is iterated separately and
is not checked in here.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from livekit.agents import Agent

from app.core.config import Settings

# repo_root/prompts/leo/system.md  (this file is repo_root/app/agent/leo.py)
_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "leo" / "system.md"


@lru_cache
def _system_prompt() -> str:
    text = _PROMPT_PATH.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Leo system prompt is empty: {_PROMPT_PATH}")
    return text


def load_leo(settings: Settings) -> Agent:
    """Build Leo's ``Agent`` from the prompt file. ``settings`` is accepted for
    forward persona configuration (level, voice); unused in this first loop."""
    return Agent(instructions=_system_prompt())
