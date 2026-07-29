"""The "For You" pre-session briefing, assembled from computed desk state.

Everything here is a summary of numbers produced elsewhere in this package —
there is no separate model call and no independent narrative. If the bias cards
say the book is mixed and thin, the briefing says the same thing, because it is
reading the same values.

One deliberate omission: this reports the **current** reading, not "bias
updated since yesterday". Change language requires stored prior snapshots, and
claiming a change without having recorded the previous state would be a
fabrication. Persisting snapshots is tracked separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.services.desk.bias import BEARISH, BULLISH, NEUTRAL, InstrumentBias
from app.services.desk.sessions import SessionState
from app.services.desk.snapshots import BiasChange

# Confidence bands shown as HIGH / MEDIUM / LOW next to a direction. The
# thresholds sit against bias.MAX_CONFIDENCE (75), not against 100.
HIGH_CONFIDENCE = 50
MEDIUM_CONFIDENCE = 30

RANGING = "Ranging"
DIRECTIONAL = "Directional"
MIXED = "Mixed"

CAUTIOUS = "Cautious"
CONSTRUCTIVE = "Constructive"


@dataclass(frozen=True)
class BriefingItem:
    symbol: str
    direction: str
    confidence: int
    band: str
    text: str
    as_of: str


@dataclass(frozen=True)
class Briefing:
    headline: str
    summary: str
    regime: str
    tone: str
    items: tuple[BriefingItem, ...]
    generated_at: datetime
    caveats: tuple[str, ...]
    #: Genuine transitions since the last stored reading. Empty when nothing
    #: changed or when no prior snapshot exists to compare against.
    changes: tuple[str, ...] = ()


def confidence_band(confidence: int) -> str:
    if confidence >= HIGH_CONFIDENCE:
        return "HIGH"
    if confidence >= MEDIUM_CONFIDENCE:
        return "MEDIUM"
    return "LOW"


def _regime(biases: list[InstrumentBias]) -> str:
    if not biases:
        return MIXED
    neutral = sum(1 for bias in biases if bias.direction == NEUTRAL)
    bullish = sum(1 for bias in biases if bias.direction == BULLISH)
    bearish = sum(1 for bias in biases if bias.direction == BEARISH)
    if neutral > len(biases) / 2:
        return RANGING
    if bullish and not bearish:
        return DIRECTIONAL
    if bearish and not bullish:
        return DIRECTIONAL
    return MIXED


def _tone(biases: list[InstrumentBias], sessions: list[SessionState]) -> str:
    """Cautious when conviction is thin or no major venue is actually open."""
    if not biases:
        return CAUTIOUS
    average = sum(bias.confidence for bias in biases) / len(biases)
    any_open = any(state.is_open for state in sessions)
    if average < MEDIUM_CONFIDENCE or not any_open:
        return CAUTIOUS
    return CONSTRUCTIVE


def _headline(biases: list[InstrumentBias], regime: str) -> str:
    if not biases:
        return "No instrument data is available for the desk right now."
    strongest = max(biases, key=lambda bias: bias.confidence)
    if regime == RANGING:
        return (
            f"{len(biases)} instruments are mostly ranging; "
            f"{strongest.symbol} carries the clearest reading."
        )
    directional = [bias for bias in biases if bias.direction != NEUTRAL]
    if not directional:
        return f"{strongest.symbol} carries the clearest reading on the desk."
    lead = max(directional, key=lambda bias: bias.confidence)
    return f"{lead.symbol} shows the strongest {lead.direction} reading on the desk."


def _summary(
    biases: list[InstrumentBias], sessions: list[SessionState], regime: str, tone: str
) -> str:
    if not biases:
        return (
            "The desk could not load market context for any configured "
            "instrument, so there is nothing to summarize."
        )

    bullish = [bias.symbol for bias in biases if bias.direction == BULLISH]
    bearish = [bias.symbol for bias in biases if bias.direction == BEARISH]
    neutral = [bias.symbol for bias in biases if bias.direction == NEUTRAL]

    parts: list[str] = []
    if bullish:
        parts.append(f"bullish on {', '.join(bullish)}")
    if bearish:
        parts.append(f"bearish on {', '.join(bearish)}")
    if neutral:
        parts.append(f"ranging on {', '.join(neutral)}")
    reading = "; ".join(parts) if parts else "no clear directional reading"

    open_now = [state.label for state in sessions if state.is_open]
    if open_now:
        venue = f"{', '.join(open_now)} {'is' if len(open_now) == 1 else 'are'} open"
    else:
        upcoming = min(sessions, key=lambda state: state.seconds_to_next, default=None)
        venue = (
            f"no major venue is open; {upcoming.label} {upcoming.next_phase_label.lower()} "
            f"in {upcoming.countdown}"
            if upcoming
            else "no session data is available"
        )

    average = round(sum(bias.confidence for bias in biases) / len(biases))
    return (
        f"The desk reads {regime.lower()} and {tone.lower()}: {reading}. "
        f"Average confidence across {len(biases)} instruments is {average}%, and {venue}."
    )


def _caveats(biases: list[InstrumentBias]) -> tuple[str, ...]:
    """Surface the data caveats that apply to the whole briefing, deduplicated."""
    seen: dict[str, None] = {}
    for bias in biases:
        if bias.proxy_note:
            seen.setdefault(bias.proxy_note, None)
        if bias.stale:
            seen.setdefault(
                f"{bias.symbol} is being served from a stale cache.", None
            )
    if any(bias.delayed for bias in biases):
        seen.setdefault(
            "All prices are delayed and are not executable quotes.", None
        )
    return tuple(seen)


def build_briefing(
    biases: list[InstrumentBias],
    sessions: list[SessionState],
    now: datetime,
    changes: list[BiasChange] | None = None,
) -> Briefing:
    regime = _regime(biases)
    tone = _tone(biases, sessions)
    items = tuple(
        BriefingItem(
            symbol=bias.symbol,
            direction=bias.direction,
            confidence=bias.confidence,
            band=confidence_band(bias.confidence),
            text=bias.explanation,
            as_of=bias.as_of,
        )
        for bias in sorted(biases, key=lambda bias: bias.confidence, reverse=True)
    )
    return Briefing(
        headline=_headline(biases, regime),
        summary=_summary(biases, sessions, regime, tone),
        regime=regime,
        tone=tone,
        items=items,
        generated_at=now,
        caveats=_caveats(biases),
        changes=tuple(change.headline for change in (changes or [])),
    )
