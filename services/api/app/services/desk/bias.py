"""Per-instrument directional bias with a confidence number that means something.

The design constraint here is deliberate and load-bearing: **direction and
confidence are computed, never asserted by a language model.** A model is
allowed to phrase the explanation and nothing else. That structural split is
what stops the number on the card from drifting away from the evidence behind
it — a model asked for "confidence" will happily emit 94%, and there is no way
to audit that after the fact.

Confidence is the product of three independently-derived factors, each in
[0, 1]:

* **strength**  — how far the composite signal is from flat, in ATR-normalized
  terms. A 0.3% move means something very different on EURUSD than on BTC;
  dividing by realized volatility is what makes the two comparable.
* **agreement** — how much of the signal weight actually points the same way as
  the composite. Three indicators agreeing is worth more than one screaming
  while two disagree.
* **coverage**  — how much of the underlying data was actually present
  (`MarketContext.confidence`), so a thin sample cannot mint a high number.

Multiplying them means confidence degrades honestly: it is high only when a
strong, agreed-upon signal rests on complete data. Expect realistic values in
the 20–60 range, not the 85–95 that sentiment dashboards advertise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.services import ai_router
from app.services.market_data import CHANGE_WINDOW_BARS, MarketContext

logger = get_logger("app.desk.bias")

BULLISH = "bullish"
BEARISH = "bearish"
NEUTRAL = "neutral"

# Composite magnitude below which the instrument is called ranging rather than
# directional. Chosen so ordinary intraday noise does not read as a trend.
NEUTRAL_BAND = 0.18

# Composite magnitude that counts as a fully-developed directional signal.
# Anything at or beyond this scores strength 1.0.
FULL_STRENGTH = 0.65

# Confidence ceiling. Nothing derived from a delayed, indicative feed on a
# one-month hourly sample deserves to present as a near-certainty, and a capped
# number is a standing reminder that this is context and not a forecast.
MAX_CONFIDENCE = 75


DIRECTIONAL = "directional"
CONFIRMATION = "confirmation"

# How much a confirmation signal may swing confidence. Heavy participation
# behind a move earns a modest bump; thin participation takes one away. Kept
# small because volume is corroboration, not evidence of direction.
CONFIRMATION_SWING = 0.15


@dataclass(frozen=True)
class BiasSignal:
    """One contributing indicator, normalized to [-1, 1] and weighted.

    `role` decides how the value is consumed. **Directional** signals vote on
    which way the instrument is leaning. **Confirmation** signals do not vote at
    all — they only raise or lower confidence in whatever the directional
    signals concluded. Conflating the two produces nonsense like "thin volume,
    therefore bullish".
    """

    label: str
    value: float
    weight: float
    detail: str
    role: str = DIRECTIONAL

    @property
    def direction(self) -> str:
        if self.role == CONFIRMATION:
            if self.value > 0.05:
                return "confirming"
            if self.value < -0.05:
                return "undercutting"
            return NEUTRAL
        if self.value > 0.05:
            return BULLISH
        if self.value < -0.05:
            return BEARISH
        return NEUTRAL


@dataclass(frozen=True)
class InstrumentBias:
    symbol: str
    direction: str
    confidence: int
    strength: float
    agreement: float
    coverage: float
    last_price: float
    change_percent: float
    signals: tuple[BiasSignal, ...]
    explanation: str
    explanation_mode: str
    as_of: str
    provider: str
    price_basis: str
    sample_size: int
    delayed: bool
    stale: bool
    proxy_note: str | None
    limitations: tuple[str, ...]
    writer_provider_id: str | None = None
    writer_model: str | None = None


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def derive_signals(context: MarketContext) -> tuple[BiasSignal, ...]:
    """Normalize the raw indicators into comparable, signed contributions.

    Every signal is expressed in [-1, 1] where positive is bullish. Indicators
    the provider could not supply are omitted entirely rather than defaulted to
    zero, so a missing indicator lowers coverage instead of silently voting
    "neutral".
    """
    signals: list[BiasSignal] = []

    # Directional move, normalized by realized volatility. Without the ATR
    # divisor this term would rank a quiet instrument's 0.5% drift above a
    # volatile one's 2% drift, which is backwards.
    if context.atr_percent:
        move_in_atr = context.change_percent / context.atr_percent
        signals.append(
            BiasSignal(
                label="Trend",
                value=_clamp(move_in_atr / 4.0),
                weight=0.40,
                detail=(
                    f"{context.change_percent:+.2f}% over the last "
                    f"{CHANGE_WINDOW_BARS} bars ({move_in_atr:+.1f}× ATR)"
                ),
            )
        )
    else:
        signals.append(
            BiasSignal(
                label="Trend",
                value=_clamp(context.change_percent / 2.0),
                weight=0.25,
                detail=(
                    f"{context.change_percent:+.2f}% over the last "
                    f"{CHANGE_WINDOW_BARS} bars (no ATR available to normalize)"
                ),
            )
        )

    # Path efficiency only amplifies an existing direction; on its own it says
    # nothing about which way. Signed by the move so a clean downtrend is
    # bearish, not bullish.
    if context.trend_efficiency is not None:
        sign = 1.0 if context.change_percent >= 0 else -1.0
        signals.append(
            BiasSignal(
                label="Path quality",
                value=_clamp(sign * context.trend_efficiency),
                weight=0.25,
                detail=(
                    f"{context.trend_efficiency:.2f} trend efficiency "
                    f"({context.bearing})"
                ),
            )
        )

    # RSI as a tilt around 50, not as an overbought/oversold reversal call.
    # Treating 70+ as "sell" is a strategy assumption this module does not make.
    if context.rsi_14 is not None:
        signals.append(
            BiasSignal(
                label="Momentum",
                value=_clamp((context.rsi_14 - 50.0) / 30.0),
                weight=0.25,
                detail=f"RSI(14) at {context.rsi_14:.1f}",
            )
        )

    # Participation corroborates; it never points. Heavy volume confirms
    # whatever the directional signals found, thin volume undercuts it — in
    # both cases independently of which way price went. Signing this by
    # direction (an earlier mistake here) reports "thin volume" as bullish
    # evidence on a down move, which is meaningless.
    if context.volume_percentile is not None:
        signals.append(
            BiasSignal(
                label="Participation",
                value=_clamp((context.volume_percentile - 50.0) / 50.0),
                weight=0.0,
                detail=(
                    f"volume in the {context.volume_percentile:.0f}th percentile "
                    f"({context.flow})"
                ),
                role=CONFIRMATION,
            )
        )

    return tuple(signals)


def _directional(signals: tuple[BiasSignal, ...]) -> tuple[BiasSignal, ...]:
    return tuple(signal for signal in signals if signal.role == DIRECTIONAL)


def confirmation_factor(signals: tuple[BiasSignal, ...]) -> float:
    """Multiplier applied to confidence from corroborating (non-voting) signals."""
    confirmations = [signal for signal in signals if signal.role == CONFIRMATION]
    if not confirmations:
        return 1.0
    mean = sum(signal.value for signal in confirmations) / len(confirmations)
    return 1.0 + CONFIRMATION_SWING * mean


def _composite(signals: tuple[BiasSignal, ...]) -> float:
    total_weight = sum(signal.weight for signal in signals)
    if not total_weight:
        return 0.0
    return sum(signal.value * signal.weight for signal in signals) / total_weight


def _agreement(signals: tuple[BiasSignal, ...], composite: float) -> float:
    """Share of signal weight pointing the same way as the composite.

    Signals near zero are counted as half-agreeing: they are not evidence
    against the composite, but they are not support for it either.
    """
    total_weight = sum(signal.weight for signal in signals)
    if not total_weight or composite == 0:
        return 0.0
    aligned = 0.0
    for signal in signals:
        if abs(signal.value) < 0.05:
            aligned += signal.weight * 0.5
        elif (signal.value > 0) == (composite > 0):
            aligned += signal.weight
    return aligned / total_weight


def derive_bias(context: MarketContext) -> tuple[str, int, float, float, tuple[BiasSignal, ...]]:
    """Return ``(direction, confidence, strength, agreement, signals)``.

    Confidence is an integer percent. It is deliberately *not* a probability of
    the move continuing — no such number is available from this data — it is a
    measure of how well-supported the directional reading is.
    """
    signals = derive_signals(context)
    voting = _directional(signals)
    composite = _composite(voting)
    agreement = _agreement(voting, composite)
    strength = min(1.0, abs(composite) / FULL_STRENGTH)
    coverage = max(0.0, min(1.0, context.confidence))
    confirmation = confirmation_factor(signals)

    if abs(composite) < NEUTRAL_BAND:
        direction = NEUTRAL
        # For a ranging call, conviction comes from the *absence* of direction
        # resting on complete data — the inverse of the directional case.
        # Participation does not corroborate a non-move, so it is not applied.
        confidence = int(round(MAX_CONFIDENCE * (1.0 - strength) * coverage))
    else:
        direction = BULLISH if composite > 0 else BEARISH
        confidence = int(
            round(MAX_CONFIDENCE * strength * agreement * coverage * confirmation)
        )

    return direction, max(0, min(MAX_CONFIDENCE, confidence)), strength, agreement, signals


def _derived_explanation(
    context: MarketContext, direction: str, signals: tuple[BiasSignal, ...]
) -> str:
    """Deterministic prose built only from the computed signals.

    This is the default. The model path below is an optional rephrasing of
    exactly this content, never a source of new claims.
    """
    parts = [signal.detail for signal in signals]
    if direction == NEUTRAL:
        opener = f"{context.symbol} is ranging"
    else:
        word = "firm" if direction == BULLISH else "soft"
        opener = f"{context.symbol} is {word} at {context.last_price:g}"
    body = "; ".join(parts) if parts else "no indicators were available"
    return f"{opener} — {body}."


_EXPLANATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "explanation": {
            "type": "string",
            "description": (
                "One or two sentences describing the supplied metrics. No news, "
                "no events, no price targets, no recommendation."
            ),
        }
    },
    "required": ["explanation"],
}

_SYSTEM_PROMPT = (
    "You rephrase pre-computed market statistics into one or two plain "
    "sentences for a trading dashboard.\n"
    "Hard rules:\n"
    "- Use ONLY the numbers supplied. Invent nothing.\n"
    "- Reference news ONLY if headlines are supplied in the input, and only "
    "those headlines. Never invent events, central-bank actions, or "
    "geopolitics beyond them.\n"
    "- Never give a recommendation, price target, entry, or exit.\n"
    "- Never state a confidence, probability, or certainty of your own.\n"
    "- Do not contradict the supplied direction.\n"
    "- Two sentences maximum."
)

# Terms that indicate the model invented a causal narrative it cannot possibly
# have — the failure mode this whole module exists to prevent.
_FABRICATION_MARKERS = (
    "news",
    "reported",
    "announce",
    "central bank",
    "fed ",
    "ecb",
    "boj",
    "geopolit",
    "war",
    "election",
    "tariff",
    "inflation print",
    "data release",
    "earnings",
    "target of",
    "buy ",
    "sell ",
    "long ",
    "short ",
)


def _explanation_is_safe(
    text: str, direction: str, allowed_context: str = ""
) -> bool:
    """Reject model prose that fabricates causes or flips the derived call.

    ``allowed_context`` is the concatenated text of any *retrieved* headlines
    supplied to the model. A fabrication marker ("fed ", "earnings", …) is
    permitted only when it literally appears there — the model may echo themes
    from real headlines but still cannot introduce a cause no source mentioned.
    """
    if not text or len(text) > 500:
        return False
    lowered = text.lower()
    allowed = allowed_context.lower()
    for marker in _FABRICATION_MARKERS:
        if marker in lowered and marker not in allowed:
            return False
    # A model that names the opposite direction has contradicted the math.
    opposite = BEARISH if direction == BULLISH else BULLISH
    return not (direction != NEUTRAL and opposite in lowered)


def explain(
    context: MarketContext,
    direction: str,
    confidence: int,
    signals: tuple[BiasSignal, ...],
    headlines: tuple[str, ...] = (),
) -> tuple[str, str, str | None, str | None]:
    """Return ``(explanation, mode, provider_id, model)``.

    Falls back to the deterministic text whenever no provider is configured or
    the model output fails validation. ``headlines`` are *retrieved* titles the
    model may weave in; the validator only admits fabrication-marker terms that
    literally appear in them, so real headlines widen what may be said and
    nothing else does.
    """
    derived = _derived_explanation(context, direction, signals)

    facts = "\n".join(f"- {signal.label}: {signal.detail}" for signal in signals)
    headline_block = ""
    if headlines:
        titles = "\n".join(f"- {title}" for title in headlines)
        headline_block = (
            f"\nRecent retrieved headlines (the ONLY news you may reference):\n"
            f"{titles}\n"
        )
    user_prompt = (
        f"Instrument: {context.symbol}\n"
        f"Last price: {context.last_price:g}\n"
        f"Computed direction: {direction}\n"
        f"Computed confidence: {confidence}%\n"
        f"Volatility state: {context.pulse}\n"
        f"Metrics:\n{facts}\n"
        f"{headline_block}\n"
        "Rephrase the above as one or two sentences."
    )

    try:
        completion = ai_router.complete_json_with_ai(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_schema=_EXPLANATION_SCHEMA,
            max_output_tokens=220,
        )
    except Exception as exc:  # noqa: BLE001 - a dashboard must not 500 on prose
        logger.warning("bias explanation provider raised %s: %s", type(exc).__name__, exc)
        return derived, "derived", None, None

    if completion is None:
        return derived, "derived", None, None

    text = str(completion.payload.get("explanation", "")).strip()
    if not _explanation_is_safe(text, direction, " ".join(headlines)):
        logger.info(
            "bias explanation rejected for %s (provider=%s); using derived text",
            context.symbol,
            completion.provider_id,
        )
        return derived, "derived", None, None

    return text, "model", completion.provider_id, completion.model


def build_bias(
    context: MarketContext, headlines: tuple[str, ...] = ()
) -> InstrumentBias:
    """Compute the full bias card for one instrument."""
    direction, confidence, strength, agreement, signals = derive_bias(context)
    explanation, mode, provider_id, model = explain(
        context, direction, confidence, signals, headlines
    )
    return InstrumentBias(
        symbol=context.symbol,
        direction=direction,
        confidence=confidence,
        strength=round(strength, 3),
        agreement=round(agreement, 3),
        coverage=round(context.confidence, 3),
        last_price=context.last_price,
        change_percent=context.change_percent,
        signals=signals,
        explanation=explanation,
        explanation_mode=mode,
        as_of=context.as_of.isoformat(),
        provider=context.provider,
        price_basis=context.price_basis,
        sample_size=context.sample_size,
        delayed=context.delayed,
        stale=context.stale,
        proxy_note=context.proxy_note,
        limitations=context.limitations,
        writer_provider_id=provider_id,
        writer_model=model,
    )
