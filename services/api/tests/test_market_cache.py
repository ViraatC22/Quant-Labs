"""Tests for the server-side quote cache and stale fallback (Phase 2.4)."""

from decimal import Decimal

import pytest

from app.services import market_data
from app.services.market_data import MarketQuote


@pytest.fixture(autouse=True)
def clear_cache():
    market_data._cache.clear()
    yield
    market_data._cache.clear()


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
