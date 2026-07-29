"""News-grounded explanation tests.

The invariant: real retrieved headlines widen what the model may say, and
nothing else does. A headline mentioning the Fed lets the prose mention the
Fed; no headline, no Fed — even if the model insists.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.services.desk import bias as bias_module
from app.services.desk import news as news_service
from app.services.desk.bias import _explanation_is_safe, build_bias
from app.services.desk.news import fetch_symbol_news
from app.services.market_data import PriceBar, analyze_market_bars


def _context(step: float = 0.5):
    start = datetime(2026, 7, 1, tzinfo=UTC)
    price, bars = 100.0, []
    for index in range(80):
        price += step
        bars.append(
            PriceBar(
                time=start + timedelta(hours=index),
                open=price - 0.2,
                high=price + 0.5,
                low=price - 0.5,
                close=price,
                volume=1000 + index,
            )
        )
    return analyze_market_bars(symbol="EURUSD", provider_symbol="EURUSD=X", bars=bars)


# --- validator ---------------------------------------------------------------


def test_marker_terms_stay_rejected_without_headlines() -> None:
    assert not _explanation_is_safe(
        "Price is rising on news of central bank buying.", "bullish", ""
    )


def test_marker_terms_are_allowed_when_a_headline_contains_them() -> None:
    headlines = "Central bank buying lifts gold demand"
    assert _explanation_is_safe(
        "Price is rising; retrieved headlines cite central bank buying.",
        "bullish",
        headlines,
    )


def test_headlines_only_admit_their_own_terms() -> None:
    # A headline about earnings does not license invented geopolitics.
    headlines = "Tech earnings beat estimates"
    assert not _explanation_is_safe(
        "Price is rising on war fears.", "bullish", headlines
    )


def test_direction_contradiction_is_rejected_regardless_of_headlines() -> None:
    headlines = "Euro strength continues, analysts bearish on dollar"
    assert not _explanation_is_safe(
        "The instrument looks bearish here.", "bullish", headlines
    )


def test_model_prose_with_headline_terms_is_accepted_end_to_end(monkeypatch) -> None:
    class _Completion:
        payload = {"explanation": "Drifting higher; headlines flag ECB rate cut hopes."}
        provider_id = "fake"
        model = "fake-1"

    monkeypatch.setattr(
        bias_module.ai_router, "complete_json_with_ai", lambda **_: _Completion()
    )
    result = build_bias(_context(), headlines=("ECB rate cut hopes lift the euro",))
    assert result.explanation_mode == "model"

    # Same prose without the licensing headline is rejected.
    result = build_bias(_context(), headlines=())
    assert result.explanation_mode == "derived"


# --- symbol news adapter -----------------------------------------------------


@pytest.fixture(autouse=True)
def clear_news_cache():
    news_service._cache.clear()
    yield
    news_service._cache.clear()


def _with_key(monkeypatch) -> None:
    monkeypatch.setattr(
        news_service, "settings", replace(news_service.settings, fmp_api_key="k")
    )


def _install(monkeypatch, rows) -> list[str]:
    urls: list[str] = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, _limit=None):
            return json.dumps(rows).encode()

    def fake_open(url, timeout, headers=None):
        urls.append(url)
        return _FakeResponse()

    monkeypatch.setattr(news_service, "safe_urlopen", fake_open)
    return urls


def test_symbol_news_without_a_key_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        news_service, "settings", replace(news_service.settings, fmp_api_key="")
    )
    feed = fetch_symbol_news("EURUSD")
    assert feed.available is False
    assert feed.items == ()


def test_fx_pairs_route_to_the_forex_endpoint(monkeypatch) -> None:
    _with_key(monkeypatch)
    urls = _install(
        monkeypatch, [{"title": "T", "url": "https://e.com/1", "site": "e.com"}]
    )
    fetch_symbol_news("EURUSD")
    assert "forex_news" in urls[0]
    assert "symbol=EURUSD" in urls[0]


def test_crypto_symbols_route_to_the_crypto_endpoint(monkeypatch) -> None:
    _with_key(monkeypatch)
    urls = _install(
        monkeypatch, [{"title": "T", "url": "https://e.com/1", "site": "e.com"}]
    )
    fetch_symbol_news("BTC")
    assert "crypto_news" in urls[0]
    assert "symbol=BTCUSD" in urls[0]


def test_equities_route_to_the_stock_endpoint(monkeypatch) -> None:
    _with_key(monkeypatch)
    urls = _install(
        monkeypatch, [{"title": "T", "url": "https://e.com/1", "site": "e.com"}]
    )
    fetch_symbol_news("AAPL")
    assert "stock_news" in urls[0]
    assert "tickers=AAPL" in urls[0]


def test_symbol_news_is_cached_per_symbol(monkeypatch) -> None:
    _with_key(monkeypatch)
    urls = _install(
        monkeypatch, [{"title": "T", "url": "https://e.com/1", "site": "e.com"}]
    )
    fetch_symbol_news("EURUSD")
    fetch_symbol_news("EURUSD")
    assert len(urls) == 1


def test_provider_failure_degrades_to_unavailable(monkeypatch) -> None:
    _with_key(monkeypatch)

    def boom(url, timeout, headers=None):
        raise TimeoutError("down")

    monkeypatch.setattr(news_service, "safe_urlopen", boom)
    feed = fetch_symbol_news("EURUSD")
    assert feed.available is False
    assert feed.items == ()
