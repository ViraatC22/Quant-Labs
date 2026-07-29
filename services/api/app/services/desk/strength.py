"""Currency strength and capital flow, derived from pairs already fetched.

Currency strength decomposes FX pair moves into per-currency contributions. A
pair is a ratio, so a move in EURUSD says something about *both* sides: if
EURUSD is +0.5%, that is +0.5 for EUR and -0.5 for USD. Averaging every pair a
currency appears in separates "EUR is strong" from "USD is weak", which a pair
chart alone cannot distinguish.

Both functions are pure — they take already-fetched changes and return rankings
— so they cost no extra upstream calls and are testable without a network.
"""

from __future__ import annotations

from dataclasses import dataclass

# The dollar pairs alone are not a basket: they put USD in all seven while
# every other currency appears exactly once, so "EUR strength" would just be
# EURUSD restated. The crosses below give each G8 currency at least three
# pairs, which is what makes "EUR is strong" separable from "USD is weak".
# `test_every_major_currency_is_covered_by_at_least_two_pairs` enforces this.
FX_MAJORS = (
    # USD legs
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "AUDUSD",
    "NZDUSD",
    "USDCAD",
    "USDCHF",
    # Crosses, so the non-USD currencies are not single-pair readings
    "EURGBP",
    "EURJPY",
    "EURCHF",
    "EURAUD",
    "GBPJPY",
    "GBPCHF",
    "AUDJPY",
    "AUDNZD",
    "CADJPY",
    "NZDJPY",
)


# Capital flow is a cross-asset ranking, so it spans indices and commodities as
# well as FX. Kept separate from FX_MAJORS on purpose: currency strength is only
# meaningful for pairs (an index has no second currency to decompose into), and
# feeding ES into that decomposition would be nonsense.
FLOW_EXTRAS: tuple[str, ...] = (
    # Index futures
    "ES",
    "NQ",
    "YM",
    "RTY",
    # Commodities
    "GC",
    "SI",
    "CL",
    "NG",
    "HG",
)

#: Default basket for the capital-flow ranking: every FX major plus the
#: cross-asset names above.
FLOW_BASKET: tuple[str, ...] = FX_MAJORS + FLOW_EXTRAS


@dataclass(frozen=True)
class CurrencyStrength:
    currency: str
    #: Mean signed contribution across every pair the currency appears in.
    score: float
    #: How many pairs backed the score. One pair is not a strength reading.
    pairs: int
    contributions: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class FlowEntry:
    symbol: str
    change_percent: float


def split_pair(pair: str) -> tuple[str, str] | None:
    """Split a six-character FX pair into ``(base, quote)``."""
    normalized = pair.strip().upper().replace("/", "")
    if len(normalized) != 6 or not normalized.isalpha():
        return None
    return normalized[:3], normalized[3:]


def currency_strength(changes: dict[str, float]) -> list[CurrencyStrength]:
    """Rank currencies by mean contribution across the supplied pair moves.

    ``changes`` maps pair symbol to percent change. Non-FX symbols are ignored
    rather than rejected, so callers can pass a mixed desk without filtering.
    """
    totals: dict[str, list[tuple[str, float]]] = {}

    for pair, change in changes.items():
        split = split_pair(pair)
        if split is None:
            continue
        base, quote = split
        # A rise in the pair is strength for the base and, by construction,
        # equal weakness for the quote.
        totals.setdefault(base, []).append((pair, change))
        totals.setdefault(quote, []).append((pair, -change))

    results = [
        CurrencyStrength(
            currency=currency,
            score=round(sum(value for _, value in entries) / len(entries), 3),
            pairs=len(entries),
            contributions=tuple(
                (pair, round(value, 3)) for pair, value in sorted(entries)
            ),
        )
        for currency, entries in totals.items()
    ]
    results.sort(key=lambda item: item.score, reverse=True)
    return results


def capital_flow(changes: dict[str, float]) -> list[FlowEntry]:
    """Instruments ranked by percent change, strongest first."""
    entries = [
        FlowEntry(symbol=symbol, change_percent=round(change, 3))
        for symbol, change in changes.items()
    ]
    entries.sort(key=lambda item: item.change_percent, reverse=True)
    return entries
