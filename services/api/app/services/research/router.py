"""Question router (Lattice L5).

Classifies a question so the pipeline knows which retrievers to run:

- ``connection`` — "how is X related to Y" → graph traversal.
- ``content``    — "what does source Z say about …" → text search.
- ``analytics``  — "what's my win rate on …" → computed trade stats, not
  retrieval. This is a Quant-Labs-specific branch Lattice doesn't need: numeric
  questions must be answered from real trade math, never from prose.
- ``trade_review`` — "why did this trade lose?" → journaled trade retrieval
  plus relevant playbook evidence.
- ``hybrid``     — anything else → run both graph and text and reconcile.

Deterministic keyword classification by default (hermetic, offline). An LLM
classifier can be layered later; the routes are the stable contract.
"""

from __future__ import annotations

import re

Route = str  # "connection" | "content" | "hybrid" | "analytics" | "trade_review"

_CONNECTION_PATTERNS = (
    r"\bhow (is|are|does|do)\b.*\b(related|connected|linked|relate|connect)\b",
    r"\brelationship between\b",
    r"\bconnect(ed|ion)?\b.*\bto\b",
    r"\blinked to\b",
    r"\bwhat (uses|requires|supports)\b",
)
_CONTENT_PATTERNS = (
    r"\bwhat does\b.*\bsay\b",
    r"\bsummar(ize|y)\b",
    r"\bexplain\b",
    r"\bwhat is\b",
    r"\btell me about\b",
    r"\bwhat's new\b",
)
_ANALYTICS_PATTERNS = (
    r"\bwin[ - ]?rate\b",
    r"\bexpectancy\b",
    r"\bprofit factor\b",
    r"\bhow many (trades|wins|losses)\b",
    r"\bp&?l\b|\bpnl\b",
    r"\bavg(erage)? (r|risk|return)\b",
    r"\bmax drawdown\b",
    r"\bhow much (did|have) i (make|made|lose|lost)\b",
)
_TRADE_REVIEW_PATTERNS = (
    r"\bwhy\b.*\b(lose|losing|lost)\b.*\btrade\b",
    r"\bwhy\b.*\btrade\b.*\b(lose|losing|lost)\b",
    r"\bwhat went wrong\b.*\btrade\b",
    r"\breview\b.*\btrade\b",
    r"\btrade\b.*\b(loss|lost|failed)\b",
)


def classify(question: str) -> Route:
    lowered = question.lower().strip()
    if _matches(lowered, _TRADE_REVIEW_PATTERNS):
        return "trade_review"
    if _matches(lowered, _ANALYTICS_PATTERNS):
        return "analytics"
    is_connection = _matches(lowered, _CONNECTION_PATTERNS)
    is_content = _matches(lowered, _CONTENT_PATTERNS)
    if is_connection and not is_content:
        return "connection"
    if is_content and not is_connection:
        return "content"
    if is_connection and is_content:
        return "hybrid"
    # Default: a bare topical question benefits from both signals.
    return "hybrid"


def _matches(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)
