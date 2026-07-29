"""Tests for price provenance: basis, executability, and proxy instruments.

These guard the distinction that matters when an order is being sized: a
delayed indicative FX mid and a live top-of-book quote are both a `Decimal`,
and only one of them is a price you can be filled at.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.services import market_data
from app.services.market_data import (
    PRICE_BASIS_INDICATIVE_MID,
    PRICE_BASIS_LAST_TRADE,
    PRICE_BASIS_TOP_OF_BOOK,
    MarketQuote,
    PriceBar,
    analyze_market_bars,
    price_basis_for,
    resolve_provider_symbol,
)


def test_fx_pairs_are_classified_as_indicative_mids() -> None:
    for symbol in ("EURUSD", "USDJPY", "GBPUSD", "AUDUSD"):
        provider_symbol, proxy_note = resolve_provider_symbol(symbol)
        assert provider_symbol.endswith("=X")
        assert proxy_note is None
        assert price_basis_for(provider_symbol) == PRICE_BASIS_INDICATIVE_MID


def test_usdjpy_maps_to_the_dollar_quoted_yen_series() -> None:
    # Yahoo publishes USD/JPY as the bare `JPY=X`, not `USDJPY=X`.
    assert resolve_provider_symbol("USDJPY")[0] == "JPY=X"


def test_spot_metals_resolve_to_futures_with_an_explicit_caveat() -> None:
    # Yahoo 404s on XAUUSD=X, so spot gold is served by the front-month future.
    # The substitution must be reported, never silently absorbed.
    provider_symbol, proxy_note = resolve_provider_symbol("XAUUSD")
    assert provider_symbol == "GC=F"
    assert proxy_note is not None
    assert "futures" in proxy_note.lower()

    provider_symbol, proxy_note = resolve_provider_symbol("XAGUSD")
    assert provider_symbol == "SI=F"
    assert proxy_note is not None


def test_equities_pass_through_unmapped_as_last_trade() -> None:
    provider_symbol, proxy_note = resolve_provider_symbol("AAPL")
    assert provider_symbol == "AAPL"
    assert proxy_note is None
    assert price_basis_for(provider_symbol) == PRICE_BASIS_LAST_TRADE


def test_delayed_quote_is_never_executable() -> None:
    quote = MarketQuote(
        symbol="EURUSD",
        provider_symbol="EURUSD=X",
        provider="yahoo_chart",
        last_price=Decimal("1.1375"),
        delayed=True,
        price_basis=PRICE_BASIS_INDICATIVE_MID,
    )
    assert quote.executable is False
    assert quote.spread is None


def test_indicative_mid_is_not_executable_even_when_realtime() -> None:
    quote = MarketQuote(
        symbol="EURUSD",
        provider_symbol="EURUSD=X",
        provider="some_realtime_feed",
        last_price=Decimal("1.1375"),
        delayed=False,
        price_basis=PRICE_BASIS_INDICATIVE_MID,
    )
    assert quote.executable is False


def test_top_of_book_with_both_sides_is_executable() -> None:
    quote = MarketQuote(
        symbol="EURUSD",
        provider_symbol="EUR_USD",
        provider="broker",
        last_price=Decimal("1.1375"),
        bid=Decimal("1.1374"),
        ask=Decimal("1.1376"),
        delayed=False,
        price_basis=PRICE_BASIS_TOP_OF_BOOK,
    )
    assert quote.executable is True
    assert quote.spread == Decimal("0.0002")


def test_top_of_book_missing_a_side_is_not_executable() -> None:
    quote = MarketQuote(
        symbol="EURUSD",
        provider_symbol="EUR_USD",
        provider="broker",
        last_price=Decimal("1.1375"),
        bid=Decimal("1.1374"),
        ask=None,
        delayed=False,
        price_basis=PRICE_BASIS_TOP_OF_BOOK,
    )
    assert quote.executable is False
    assert quote.spread is None


def test_stale_quote_is_never_executable() -> None:
    quote = MarketQuote(
        symbol="EURUSD",
        provider_symbol="EUR_USD",
        provider="broker",
        last_price=Decimal("1.1375"),
        bid=Decimal("1.1374"),
        ask=Decimal("1.1376"),
        delayed=False,
        stale=True,
        price_basis=PRICE_BASIS_TOP_OF_BOOK,
    )
    assert quote.executable is False


def _bars(count: int = 60) -> list[PriceBar]:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    bars = []
    price = 100.0
    for index in range(count):
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
    return bars


def test_context_reports_spread_limitation_for_indicative_feeds() -> None:
    context = analyze_market_bars(
        symbol="EURUSD", provider_symbol="EURUSD=X", bars=_bars()
    )
    assert context.price_basis == PRICE_BASIS_INDICATIVE_MID
    assert any("half the spread" in item for item in context.limitations)


def test_context_carries_the_proxy_caveat_into_limitations() -> None:
    _, proxy_note = resolve_provider_symbol("XAUUSD")
    context = analyze_market_bars(
        symbol="XAUUSD",
        provider_symbol="GC=F",
        bars=_bars(),
        proxy_note=proxy_note,
    )
    assert context.proxy_note == proxy_note
    assert proxy_note in context.limitations


def test_provider_bid_ask_is_rejected_when_crossed(monkeypatch) -> None:
    # A crossed or non-positive book is bad data; it must degrade to "no book"
    # rather than produce a negative spread that downstream sizing would trust.
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": 100.0,
                        "previousClose": 99.0,
                        "currency": "USD",
                        "bid": 101.0,
                        "ask": 99.5,
                    }
                }
            ]
        }
    }
    _install_fake_yahoo(monkeypatch, payload)
    quote = market_data._fetch_from_provider("AAPL")
    assert quote.bid is None
    assert quote.ask is None
    assert quote.executable is False


def test_provider_bid_ask_is_kept_when_valid(monkeypatch) -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": 100.0,
                        "previousClose": 99.0,
                        "currency": "USD",
                        "bid": 99.98,
                        "ask": 100.02,
                    }
                }
            ]
        }
    }
    _install_fake_yahoo(monkeypatch, payload)
    quote = market_data._fetch_from_provider("AAPL")
    assert quote.bid == Decimal("99.9800")
    assert quote.ask == Decimal("100.0200")
    # Still not executable: the Yahoo feed is delayed and only last-trade basis.
    assert quote.executable is False


def _install_fake_yahoo(monkeypatch, payload: dict) -> None:
    """Replace urlopen with a context manager returning ``payload`` as JSON."""
    import json

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, _limit=None):
            return json.dumps(payload).encode()

    monkeypatch.setattr(market_data, "urlopen", lambda *a, **k: _FakeResponse())
