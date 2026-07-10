"""Extract atomic claims from a source document (Lattice L2/L4 foundation).

A *claim* is a subject–predicate–object statement with a polarity and evidence.
Two kinds are produced:

1. Structured claims from ``strategy_info`` (entry/exit/risk rules, market,
   timeframe, setup) — always asserted with "supports" polarity.
2. Market-condition claims mined from the prose: statements that a subject
   works / does not work under a named market condition. Negation flips the
   polarity, which is what makes conflict detection between two sources
   possible (source A: "ORB works in chop"; source B: "ORB fails in chop").

This is the deterministic local extractor and runs with no network so
``AI_ENRICHMENT_MODE=local`` still yields claims. An LLM extractor can be
layered on later behind the same ``extract_claims`` return shape; the caller
upserts whatever it returns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

# Market/condition vocabulary the miner recognizes as claim objects. Values are
# the normalized object literal so "choppy"/"chop"/"ranging" collapse together.
_CONDITIONS: dict[str, str] = {
    "trending": "trend",
    "trend": "trend",
    "trend-up": "uptrend",
    "uptrend": "uptrend",
    "downtrend": "downtrend",
    # "ranging" only — the bare word "range" collides with "opening range" /
    # "15 minute range" (price ranges, not a ranging market condition).
    "ranging": "range",
    "chop": "chop",
    "choppy": "chop",
    "sideways": "chop",
    "volatile": "high-volatility",
    "high volatility": "high-volatility",
    "low volatility": "low-volatility",
    "quiet": "low-volatility",
    "london": "london-session",
    "new york": "ny-session",
    "asia": "asia-session",
    "premarket": "premarket",
}

_NEGATIONS = ("not", "n't", "never", "avoid", "fails", "fail", "poor", "worse", "worst", "weak")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
# Split a sentence into clauses so negation attaches to the right condition:
# "works in a trend but should be avoided in chop" → two clauses with opposite
# polarity, not one clause where "avoided" poisons both conditions.
_CLAUSE_RE = re.compile(
    r"\s*(?:;|,\s*(?:and|but|while|whereas)\b|\bbut\b|\bwhereas\b|\bwhile\b)\s*"
)


@dataclass
class ExtractedClaim:
    predicate: str
    statement_text: str
    polarity: str = "supports"
    object_literal: str | None = None
    quote: str | None = None
    confidence: Decimal = field(default_factory=lambda: Decimal("0.6"))


def extract_claims(
    *,
    subject_label: str,
    strategy_info: dict | None,
    text: str,
) -> list[ExtractedClaim]:
    claims: list[ExtractedClaim] = []
    claims.extend(_structured_claims(subject_label, strategy_info))
    claims.extend(_condition_claims(subject_label, text))
    return _dedupe(claims)


def _structured_claims(subject: str, strategy_info: dict | None) -> list[ExtractedClaim]:
    if not strategy_info:
        return []
    out: list[ExtractedClaim] = []
    rule_predicates = {
        "entry_rules": "enters_when",
        "exit_rules": "exits_when",
        "risk_rules": "limits_risk_with",
    }
    for key, predicate in rule_predicates.items():
        for rule in strategy_info.get(key) or []:
            rule_text = str(rule).strip()
            if rule_text:
                out.append(
                    ExtractedClaim(
                        predicate=predicate,
                        object_literal=rule_text[:240],
                        statement_text=f"{subject} {predicate.replace('_', ' ')} {rule_text}",
                        quote=rule_text[:240],
                    )
                )
    for key, predicate in (("market", "works_in"), ("timeframe", "works_on"), ("setup", "uses")):
        value = strategy_info.get(key)
        if isinstance(value, str) and value.strip():
            out.append(
                ExtractedClaim(
                    predicate=predicate,
                    object_literal=value.strip().lower()[:120],
                    statement_text=f"{subject} {predicate.replace('_', ' ')} {value.strip()}",
                )
            )
    return out


def _condition_claims(subject: str, text: str) -> list[ExtractedClaim]:
    out: list[ExtractedClaim] = []
    for sentence in _SENTENCE_RE.split(text or ""):
        if not sentence.strip():
            continue
        for clause in _CLAUSE_RE.split(sentence):
            lowered = clause.lower()
            if not lowered.strip():
                continue
            matched = _matched_condition(lowered)
            if not matched:
                continue
            polarity = "refutes" if _is_negated(lowered) else "supports"
            out.append(
                ExtractedClaim(
                    predicate="works_in",
                    object_literal=matched,
                    polarity=polarity,
                    statement_text=clause.strip()[:400],
                    quote=clause.strip()[:280],
                )
            )
    return out


def _matched_condition(lowered: str) -> str | None:
    # Longest phrase first so "high volatility" beats "volatile".
    for phrase in sorted(_CONDITIONS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(phrase)}\b", lowered):
            return _CONDITIONS[phrase]
    return None


def _is_negated(lowered: str) -> bool:
    return any(neg in lowered for neg in _NEGATIONS)


def _dedupe(claims: list[ExtractedClaim]) -> list[ExtractedClaim]:
    seen: dict[tuple[str, str | None, str], ExtractedClaim] = {}
    for claim in claims:
        key = (claim.predicate, claim.object_literal, claim.polarity)
        # Keep the first (structured claims precede mined ones and are cleaner).
        seen.setdefault(key, claim)
    return list(seen.values())
