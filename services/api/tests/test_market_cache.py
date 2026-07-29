"""Tests for the server-side quote cache and stale fallback (Phase 2.4)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.services import market_data
from app.services.market_data import MarketQuote, PriceBar, analyze_market_bars


@pytest.fixture(autouse=True)
def clear_cache():
    market_data._cache.clear()
    market_data._context_cache.clear()
    yield
    market_data._cache.clear()
    market_data._context_cache.clear()


def _quote(symbol: str, price: str) -> MarketQuote:
    return MarketQuote(
        symbol=symbol,
        provider_symbol=symbol,
        provider="test",
        last_price=Decimal(price),
    )


def test_second_call_is_served_from_cache(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_provider(symbol: str) -> MarketQuote:
        calls["n"] += 1
        return _quote("AAPL", "100")

    monkeypatch.setattr(market_data, "_fetch_from_provider", fake_provider)

    first = market_data.fetch_market_quote("aapl")
    second = market_data.fetch_market_quote("AAPL")

    assert calls["n"] == 1  # upstream hit only once within the TTL window
    assert first.last_price == second.last_price == Decimal("100")
    assert first.stale is False


def test_stale_cache_served_when_provider_fails(monkeypatch) -> None:
    state = {"fail": False}

    def flaky_provider(symbol: str) -> MarketQuote:
        if state["fail"]:
            raise TimeoutError("provider down")
        return _quote("AAPL", "100")

    monkeypatch.setattr(market_data, "_fetch_from_provider", flaky_provider)
    monkeypatch.setattr(market_data, "QUOTE_CACHE_TTL_SECONDS", 0)  # force a miss next call

    fresh = market_data.fetch_market_quote("AAPL")
    assert fresh.stale is False

    state["fail"] = True
    stale = market_data.fetch_market_quote("AAPL")
    assert stale.stale is True
    assert stale.last_price == Decimal("100")


def test_provider_failure_without_cache_raises(monkeypatch) -> None:
    def dead_provider(symbol: str) -> MarketQuote:
        raise TimeoutError("provider down")

    monkeypatch.setattr(market_data, "_fetch_from_provider", dead_provider)
    with pytest.raises(TimeoutError):
        market_data.fetch_market_quote("NVDA")


def test_market_context_exposes_indicator_provenance() -> None:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    bars = []
    price = 100.0
    for index in range(60):
        price += 0.4
        bars.append(
            PriceBar(
                time=start + timedelta(hours=index),
                open=price - 0.2,
                high=price + 0.5,
                low=price - 0.5,
                close=price,
                volume=100 + index * 10,
            )
        )
    context = analyze_market_bars(symbol="TEST", provider_symbol="TEST", bars=bars)
    assert context.sample_size == 60
    assert context.rsi_14 == 100.0
    assert context.flow == "crowded"
    assert context.bearing == "trending up"
    assert context.atr_percent is not None
    assert context.bollinger_width_percent is not None
    assert context.confidence > 0.5
    assert context.stale is False


def test_market_context_is_cached(monkeypatch) -> None:
    calls = {"n": 0}
    start = datetime(2026, 7, 1, tzinfo=UTC)
    bars = [
        PriceBar(
            time=start + timedelta(hours=index),
            open=100 + index,
            high=101 + index,
            low=99 + index,
            close=100 + index,
            volume=1000 + index,
        )
        for index in range(30)
    ]

    def fake_context(symbol: str):
        calls["n"] += 1
        return analyze_market_bars(symbol=symbol, provider_symbol=symbol, bars=bars)

    monkeypatch.setattr(market_data, "_fetch_market_context_from_provider", fake_context)
    first = market_data.fetch_market_context("aapl")
    second = market_data.fetch_market_context("AAPL")
    assert calls["n"] == 1
    assert first == second
