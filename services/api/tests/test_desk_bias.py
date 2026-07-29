"""Bias derivation tests.

The load-bearing property is that direction and confidence come from the data,
not from a model, and that confidence degrades when the evidence is thin or
contradictory.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.desk import bias as bias_module
from app.services.desk.bias import (
    BEARISH,
    BULLISH,
    CONFIRMATION,
    DIRECTIONAL,
    MAX_CONFIDENCE,
    NEUTRAL,
    BiasSignal,
    build_bias,
    confirmation_factor,
    derive_bias,
    derive_signals,
)
from app.services.market_data import PriceBar, analyze_market_bars


def _bars(
    count: int = 80, *, step: float = 0.4, volume: float | None = 1000.0
) -> list[PriceBar]:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    bars: list[PriceBar] = []
    price = 100.0
    for index in range(count):
        price += step
        bars.append(
            PriceBar(
                time=start + timedelta(hours=index),
                open=price - 0.2,
                high=price + 0.5,
                low=price - 0.5,
                close=price,
                volume=volume,
            )
        )
    return bars


def _context(**kwargs):
    bars = kwargs.pop("bars", None) or _bars()
    return analyze_market_bars(
        symbol=kwargs.pop("symbol", "TEST"),
        provider_symbol=kwargs.pop("provider_symbol", "TEST"),
        bars=bars,
        **kwargs,
    )


def test_rising_series_reads_bullish() -> None:
    direction, confidence, _, _, _ = derive_bias(_context(bars=_bars(step=0.4)))
    assert direction == BULLISH
    assert confidence > 0


def test_falling_series_reads_bearish() -> None:
    direction, _, _, _, _ = derive_bias(_context(bars=_bars(step=-0.4)))
    assert direction == BEARISH


def test_flat_series_reads_neutral() -> None:
    direction, _, _, _, _ = derive_bias(_context(bars=_bars(step=0.0)))
    assert direction == NEUTRAL


def test_confidence_never_exceeds_the_cap() -> None:
    # Even a perfectly clean trend must not present as near-certainty.
    for step in (0.1, 0.4, 2.0, 10.0):
        _, confidence, _, _, _ = derive_bias(_context(bars=_bars(step=step)))
        assert 0 <= confidence <= MAX_CONFIDENCE


def test_confidence_is_always_a_whole_number() -> None:
    # The reference dashboard renders 74.2223842927035%; ours must not.
    _, confidence, _, _, _ = derive_bias(_context())
    assert isinstance(confidence, int)


def test_participation_is_a_confirmation_signal_not_a_directional_one() -> None:
    """Regression: thin volume on a down move must not read as bullish.

    Participation was previously signed by the direction of the move, so a
    falling market on thin volume produced a positive (bullish) contribution.
    Volume corroborates a move; it never indicates which way price went.
    """
    context = _context(bars=_bars(step=-0.4))
    signals = derive_signals(context)
    participation = next(s for s in signals if s.label == "Participation")

    assert participation.role == CONFIRMATION
    assert participation.weight == 0.0  # casts no directional vote
    assert participation.direction in {"confirming", "undercutting", NEUTRAL}
    assert participation.direction not in {BULLISH, BEARISH}


def test_only_directional_signals_carry_voting_weight() -> None:
    signals = derive_signals(_context())
    for signal in signals:
        if signal.role == DIRECTIONAL:
            assert signal.weight > 0
        else:
            assert signal.weight == 0.0


def test_confirmation_factor_rewards_participation_and_penalises_thinness() -> None:
    heavy = (BiasSignal("Participation", 1.0, 0.0, "", role=CONFIRMATION),)
    thin = (BiasSignal("Participation", -1.0, 0.0, "", role=CONFIRMATION),)
    assert confirmation_factor(heavy) > 1.0
    assert confirmation_factor(thin) < 1.0
    assert confirmation_factor(()) == 1.0


def test_thin_participation_lowers_confidence_on_a_directional_call() -> None:
    trending = _bars(step=0.5)
    heavy = analyze_market_bars(
        symbol="T", provider_symbol="T", bars=[*trending]
    )
    # Rebuild with a rising volume profile so the last bar sits high in the
    # percentile distribution rather than flat.
    ramped = [
        PriceBar(b.time, b.open, b.high, b.low, b.close, 100 + index * 50)
        for index, b in enumerate(trending)
    ]
    confirmed = analyze_market_bars(symbol="T", provider_symbol="T", bars=ramped)

    _, thin_confidence, _, _, _ = derive_bias(heavy)
    _, confirmed_confidence, _, _, _ = derive_bias(confirmed)
    assert confirmed_confidence >= thin_confidence


def test_missing_indicators_lower_coverage_rather_than_voting_neutral() -> None:
    # A short sample drops indicators entirely; coverage (and therefore
    # confidence) must fall rather than the missing values voting "flat".
    short = _context(bars=_bars(count=25))
    long = _context(bars=_bars(count=120))
    assert short.confidence < long.confidence


def test_explanation_falls_back_to_derived_without_a_provider(monkeypatch) -> None:
    monkeypatch.setattr(bias_module.ai_router, "complete_json_with_ai", lambda **_: None)
    result = build_bias(_context(symbol="EURUSD"))
    assert result.explanation_mode == "derived"
    assert result.writer_provider_id is None
    assert "EURUSD" in result.explanation


def test_model_prose_is_rejected_when_it_invents_news(monkeypatch) -> None:
    class _Completion:
        payload = {"explanation": "Gold rallied on news of central bank buying."}
        provider_id = "fake"
        model = "fake-1"

    monkeypatch.setattr(
        bias_module.ai_router, "complete_json_with_ai", lambda **_: _Completion()
    )
    result = build_bias(_context(symbol="XAUUSD"))
    assert result.explanation_mode == "derived"
    assert "central bank" not in result.explanation


def test_model_prose_is_rejected_when_it_contradicts_the_math(monkeypatch) -> None:
    class _Completion:
        payload = {"explanation": "The instrument looks bearish here."}
        provider_id = "fake"
        model = "fake-1"

    monkeypatch.setattr(
        bias_module.ai_router, "complete_json_with_ai", lambda **_: _Completion()
    )
    # A cleanly rising series derives bullish; bearish prose must be discarded.
    result = build_bias(_context(bars=_bars(step=0.5)))
    assert result.direction == BULLISH
    assert result.explanation_mode == "derived"


def test_model_prose_is_accepted_when_it_stays_within_the_facts(monkeypatch) -> None:
    class _Completion:
        payload = {"explanation": "Price is drifting higher with momentum above 50."}
        provider_id = "fake"
        model = "fake-1"

    monkeypatch.setattr(
        bias_module.ai_router, "complete_json_with_ai", lambda **_: _Completion()
    )
    result = build_bias(_context(bars=_bars(step=0.5)))
    assert result.explanation_mode == "model"
    assert result.writer_provider_id == "fake"


def test_provider_exception_does_not_break_the_card(monkeypatch) -> None:
    def boom(**_):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(bias_module.ai_router, "complete_json_with_ai", boom)
    result = build_bias(_context())
    assert result.explanation_mode == "derived"


@pytest.mark.parametrize("step", [0.4, -0.4, 0.0])
def test_confidence_is_bounded_for_every_direction(step: float) -> None:
    _, confidence, _, _, _ = derive_bias(_context(bars=_bars(step=step)))
    assert 0 <= confidence <= MAX_CONFIDENCE
