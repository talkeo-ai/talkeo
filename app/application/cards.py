"""Structured vocabulary card (the explain endpoint's response shape, #27).

A highlighted term is best learned as a small structured card, not a prose
paragraph: distinct sections the client renders natively (real bold, separate
blocks, a styled false-friend warning). These Pydantic models are both the
parse/validation target for the model's JSON output and the API response model,
so an invalid shape from the model fails loudly here rather than reaching the
client. The same shape is what Phase B (#16) will persist as the vocab dataset.

The card is adaptive: meanings carry only the senses that matter (one for a
monosemous word, several for "run"/"set"), examples appear only when they
clarify, and insight is emitted only when it genuinely adds value.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Example(BaseModel):
    """A usage example. ``source`` is in the term's language, ``target`` its
    translation; the term is wrapped in ``**…**`` on the source side to bold."""

    source: str
    target: str


class Insight(BaseModel):
    """The single highest-value note about the term, when one applies.

    ``false_friend`` is the highest-signal case for ES learners (the UI styles it
    as a warning); ``pattern`` covers grammar/collocation, ``register`` covers
    formality/slang cautions, ``confusable`` flags an easily-mixed-up word.
    """

    type: Literal["false_friend", "pattern", "register", "confusable"]
    text: str


class ExplainCard(BaseModel):
    """The contextual vocabulary card for one highlighted term."""

    term: str
    # Optional: the client doesn't render it, and models occasionally drop it or
    # mislabel the key, so a missing category shouldn't fail the whole card.
    category: str = ""
    meanings: list[str] = Field(min_length=1)
    examples: list[Example] = []
    insight: Insight | None = None
