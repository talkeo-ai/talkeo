"""Structured improvement result (the improve endpoint's response shape, #8).

Improve rewrites the user's English so it sounds native and natural, and it
*teaches*: alongside the rewritten text it returns the individual changes, each
with the fragment it replaced, the replacement, and a short why. That structure
lets the Mac diff-highlight (mark each ``original`` in the source and each
``fixed`` in the improved text) and show a compact, scannable list of mistakes,
rather than parsing prose. The same shape is the learnable data Phase B (#16)
will persist for the practice zone.

Like explain's card, these Pydantic models are both the parse/validation target
for the model's JSON output and the API response model, so an invalid shape
fails loudly here rather than reaching the client.

An empty ``changes`` list is a first-class result: it means the original was
already natural (the "the original can be right" case), not a failure.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.application.cards import Example


class Change(BaseModel):
    """One edit the model made, framed to teach.

    ``original`` is the exact fragment from the user's text and ``fixed`` the
    exact fragment from ``improved`` that replaced it, so the client can locate
    and highlight both. ``why`` is the teaching value (one short sentence in the
    learner's language). ``examples`` ride along only when they genuinely teach
    (naturalness, word choice); they are skipped for obvious edits like spelling.
    """

    original: str
    fixed: str
    why: str
    type: Literal["spelling", "grammar", "naturalness"]
    examples: list[Example] = []


class ImproveResult(BaseModel):
    """The improved text plus the per-change breakdown that explains it."""

    improved: str
    # Empty = "already natural": the input needed no change. This is a valid,
    # trust-critical result, not an error or a missing field.
    changes: list[Change] = []
