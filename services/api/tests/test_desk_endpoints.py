"""Desk endpoint contract tests.

Market context is stubbed so these never touch the network: the point is the
API contract and the degradation behaviour, not Yahoo's uptime.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import desk as desk_api
from app.main import create_app
from app.services.desk import news as news_service
from app.services.market_data import PriceBar, analyze_market_bars

client = TestClient(create_app())


def _context(symbol: str, provider_symbol: str | None = None, *, rising: bool = True):
    start = datetime(2026, 7, 1, tzinfo=UTC)
    bars: list[PriceBar] = []
    price = 100.0
    for index in range(80):
        price += 0.4 if rising else -0.4
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
    return analyze_market_bars(
        symbol=symbol, provider_symbol=provider_symbol or symbol, bars=bars
    )


@pytest.fixture(autouse=True)
def stub_market(monkeypatch):
    monkeypatch.setattr(desk_api, "fetch_market_context", lambda symbol: _context(symbol))
    news_service._cache.clear()
    yield
    news_service._cache.clear()


def test_macro_desk_returns_a_card_per_configured_symbol() -> None:
    response = client.get("/api/v1/desk/macro")
    assert response.status_code == 200
    body = response.json()
    assert body["instruments"]
    assert body["unavailable"] == {}
    for card in body["instruments"]:
        assert 0 <= card["confidence"] <= 100
        # Confidence must be a whole number — the reference dashboard leaks
        # raw floats like 74.2223842927035 onto the screen.
        assert card["confidence"] == int(card["confidence"])
        assert card["direction"] in {"bullish", "bearish", "neutral"}
        assert card["explanation"]
        assert card["explanation_mode"] in {"derived", "model"}
        assert card["signals"]


def test_macro_desk_accepts_an_explicit_symbol_list() -> None:
    response = client.get("/api/v1/desk/macro", params={"symbols": "eurusd,aapl"})
    assert response.status_code == 200
    symbols = [card["symbol"] for card in response.json()["instruments"]]
    assert symbols == ["EURUSD", "AAPL"]


def test_confidence_is_capped_below_certainty() -> None:
    response = client.get("/api/v1/desk/macro", params={"symbols": "eurusd"})
    card = response.json()["instruments"][0]
    # A cleanly trending synthetic series is the best case available; even that
    # must not present as a near-certainty.
    assert card["confidence"] <= 75


def test_one_failing_symbol_degrades_only_that_card(monkeypatch) -> None:
    def flaky(symbol: str):
        if symbol == "GBPUSD":
            raise TimeoutError("provider down")
        return _context(symbol)

    monkeypatch.setattr(desk_api, "fetch_market_context", flaky)
    response = client.get("/api/v1/desk/macro", params={"symbols": "eurusd,gbpusd"})

    assert response.status_code == 200
    body = response.json()
    assert [card["symbol"] for card in body["instruments"]] == ["EURUSD"]
    assert "GBPUSD" in body["unavailable"]


def test_sessions_endpoint_reports_every_venue() -> None:
    response = client.get("/api/v1/desk/sessions")
    assert response.status_code == 200
    body = response.json()
    assert len(body["sessions"]) == 5
    assert any(state["key"] == "cme" for state in body["sessions"])
    for state in body["sessions"]:
        assert state["phase"] in {"pre_market", "open", "after_hours", "closed"}
        assert state["seconds_to_next"] >= 0
        assert state["countdown"]


def test_news_without_a_key_is_unavailable_with_a_reason(monkeypatch) -> None:
    monkeypatch.setattr(
        news_service, "settings", replace(news_service.settings, fmp_api_key="")
    )
    response = client.get("/api/v1/desk/news")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["items"] == []
    assert "FMP_API_KEY" in body["reason"]


def test_briefing_summarizes_the_desk() -> None:
    response = client.get("/api/v1/desk/briefing", params={"symbols": "eurusd,gbpusd"})
    assert response.status_code == 200
    body = response.json()
    assert body["headline"]
    assert body["summary"]
    assert body["regime"] in {"Ranging", "Directional", "Mixed"}
    assert body["tone"] in {"Cautious", "Constructive"}
    assert len(body["items"]) == 2
    for item in body["items"]:
        assert item["band"] in {"HIGH", "MEDIUM", "LOW"}
    # Delayed data must always be disclosed on the briefing.
    assert any("delayed" in caveat.lower() for caveat in body["caveats"])


def test_briefing_handles_a_completely_empty_desk(monkeypatch) -> None:
    def dead(symbol: str):
        raise TimeoutError("provider down")

    monkeypatch.setattr(desk_api, "fetch_market_context", dead)
    response = client.get("/api/v1/desk/briefing", params={"symbols": "eurusd"})

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    # No data must read as "nothing to summarize", never as an invented view.
    assert "nothing to summarize" in body["summary"].lower()


def test_symbol_fanout_is_bounded(monkeypatch) -> None:
    calls: list[str] = []

    def counting(symbol: str):
        calls.append(symbol)
        return _context(symbol)

    monkeypatch.setattr(desk_api, "fetch_market_context", counting)
    many = ",".join(f"SYM{index}" for index in range(40))
    client.get("/api/v1/desk/macro", params={"symbols": many})
    assert len(calls) <= 12
