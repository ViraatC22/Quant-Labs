"""Risk-on / risk-off read, derived from cross-asset moves.

The classic tell: when risk appetite is on, equity futures and crypto catch a
bid while havens (gold, yen, franc) are sold — and vice versa. This module
scores that spread from the same delayed hourly contexts everything else uses.

Sign conventions matter here and are easy to get backwards: USDJPY *rising*
means the yen is weakening, which is risk-ON behaviour, so haven strength for
JPY is the *negative* of the USDJPY move. Same for CHF via USDCHF.

This is a description of recent cross-asset behaviour on delayed data — not a
regime forecast — and the response says so.
"""

from __future__ import annotations

from dataclasses import dataclass

# Instruments whose rallies signal appetite for risk.
RISK_ASSETS: tuple[tuple[str, str], ...] = (
    ("ES", "S&P 500 futures"),
    ("NQ", "Nasdaq futures"),
    ("BTC", "Bitcoin"),
)
# Havens: (symbol, label, sign) where sign converts the pair move into haven
# strength. Gold is quoted directly; JPY and CHF are read through their USD
# pairs, where a rising pair means a weakening haven.
HAVENS: tuple[tuple[str, str, float], ...] = (
    ("XAUUSD", "Gold", 1.0),
    ("USDJPY", "Yen (via USDJPY)", -1.0),
    ("USDCHF", "Franc (via USDCHF)", -1.0),
)

RISK_ON = "risk_on"
RISK_OFF = "risk_off"
MIXED = "mixed"

# Spread (percentage points) between risk appetite and haven strength below
# which the read is called mixed rather than forced into a direction.
MIXED_BAND = 0.15


@dataclass(frozen=True)
class MoodComponent:
    symbol: str
    label: str
    role: str  # "risk" | "haven"
    change_percent: float
    #: Signed contribution: positive pushes risk-on, negative risk-off.
    contribution: float


@dataclass(frozen=True)
class MarketMood:
    mood: str
    #: risk_score - haven_score, in percentage points.
    spread: float
    risk_score: float
    haven_score: float
    components: tuple[MoodComponent, ...]
    #: Symbols that could not be loaded; the read shrinks rather than guesses.
    unavailable: tuple[str, ...]
    summary: str
    caveat: str


def derive_mood(changes: dict[str, float], unavailable: tuple[str, ...] = ()) -> MarketMood:
    """Pure derivation from per-symbol percent changes. Fully testable."""
    components: list[MoodComponent] = []
    risk_values: list[float] = []
    haven_values: list[float] = []

    for symbol, label in RISK_ASSETS:
        if symbol not in changes:
            continue
        change = changes[symbol]
        risk_values.append(change)
        components.append(
            MoodComponent(
                symbol=symbol,
                label=label,
                role="risk",
                change_percent=round(change, 3),
                contribution=round(change, 3),
            )
        )

    for symbol, label, sign in HAVENS:
        if symbol not in changes:
            continue
        change = changes[symbol]
        haven_strength = sign * change
        haven_values.append(haven_strength)
        components.append(
            MoodComponent(
                symbol=symbol,
                label=label,
                role="haven",
                change_percent=round(change, 3),
                # Haven strength pushes the read toward risk-off.
                contribution=round(-haven_strength, 3),
            )
        )

    risk_score = sum(risk_values) / len(risk_values) if risk_values else 0.0
    haven_score = sum(haven_values) / len(haven_values) if haven_values else 0.0
    spread = risk_score - haven_score

    if not risk_values or not haven_values:
        mood = MIXED
        summary = (
            "Not enough cross-asset data to read risk appetite; "
            "the missing side is listed under unavailable."
        )
    elif abs(spread) < MIXED_BAND:
        mood = MIXED
        summary = (
            f"Risk assets ({risk_score:+.2f}%) and havens ({haven_score:+.2f}%) "
            "are moving together — no clear appetite either way."
        )
    elif spread > 0:
        mood = RISK_ON
        summary = (
            f"Risk assets are outpacing havens by {spread:.2f} points — "
            "recent flows lean risk-on."
        )
    else:
        mood = RISK_OFF
        summary = (
            f"Havens are outpacing risk assets by {abs(spread):.2f} points — "
            "recent flows lean risk-off."
        )

    return MarketMood(
        mood=mood,
        spread=round(spread, 3),
        risk_score=round(risk_score, 3),
        haven_score=round(haven_score, 3),
        components=tuple(components),
        unavailable=unavailable,
        summary=summary,
        caveat=(
            "Derived from delayed hourly moves in a small cross-asset basket; "
            "a description of recent behaviour, not a regime forecast."
        ),
    )
