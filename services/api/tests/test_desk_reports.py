"""Daily report tests: grading honesty first, then the endpoint contract.

Grading is the section that must not cheat, so its rules get the coverage:
no stored price → ungradable, too fresh → ungradable, and verdicts follow the
flat band exactly.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import desk as desk_api
from app.main import create_app
from app.models.domain import BiasSnapshot
from app.services.desk.reports import (
    CORRECT,
    FLAT,
    FLAT_BAND_PERCENT,
    INCORRECT,
    MIN_GRADE_AGE,
    UNGRADABLE,
    grade_snapshot,
)

client = TestClient(create_app())

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


def _snapshot(
    direction: str = "bullish",
    *,
    last_price: float | None = 1.1000,
    age: timedelta = MIN_GRADE_AGE + timedelta(hours=2),
) -> BiasSnapshot:
    payload = {} if last_price is None else {"last_price": last_price}
    return BiasSnapshot(
        user_id=uuid4(),
        symbol="EURUSD",
        direction=direction,
        confidence=50,
        explanation="test",
        payload=payload,
        recorded_at=NOW - age,
    )


def test_snapshot_without_a_stored_price_is_ungradable() -> None:
    call = grade_snapshot(_snapshot(last_price=None), 1.2000, NOW)
    assert call.verdict == UNGRADABLE
    assert "did not record a price" in call.detail


def test_too_recent_call_is_ungradable_not_guessed() -> None:
    call = grade_snapshot(_snapshot(age=timedelta(hours=1)), 1.2000, NOW)
    assert call.verdict == UNGRADABLE
    assert "Too recent" in call.detail


def test_missing_current_price_is_ungradable() -> None:
    call = grade_snapshot(_snapshot(), None, NOW)
    assert call.verdict == UNGRADABLE


def test_bullish_call_followed_by_a_rise_is_correct() -> None:
    call = grade_snapshot(_snapshot("bullish", last_price=1.1000), 1.1100, NOW)
    assert call.verdict == CORRECT
    assert "+0.91%" in call.detail


def test_bullish_call_followed_by_a_fall_is_incorrect() -> None:
    call = grade_snapshot(_snapshot("bullish", last_price=1.1000), 1.0900, NOW)
    assert call.verdict == INCORRECT


def test_directional_call_inside_the_flat_band_is_flat() -> None:
    # A move smaller than the band is not a verdict either way.
    barely = 1.1000 * (1 + (FLAT_BAND_PERCENT / 2) / 100)
    call = grade_snapshot(_snapshot("bullish", last_price=1.1000), barely, NOW)
    assert call.verdict == FLAT


def test_neutral_call_is_correct_when_price_stays_flat() -> None:
    call = grade_snapshot(_snapshot("neutral", last_price=1.1000), 1.1002, NOW)
    assert call.verdict == CORRECT


def test_neutral_call_is_incorrect_when_price_trends() -> None:
    call = grade_snapshot(_snapshot("neutral", last_price=1.1000), 1.1300, NOW)
    assert call.verdict == INCORRECT


# --- endpoint contract -----------------------------------------------------


@pytest.fixture(autouse=True)
def stub_market(monkeypatch):
    from datetime import timedelta as td

    from app.services.market_data import PriceBar, analyze_market_bars

    def fake_context(symbol: str):
        start = datetime(2026, 7, 1, tzinfo=UTC)
        price, bars = 100.0, []
        for index in range(60):
            price += 0.3
            bars.append(
                PriceBar(
                    time=start + td(hours=index),
                    open=price - 0.1,
                    high=price + 0.4,
                    low=price - 0.4,
                    close=price,
                    volume=1000,
                )
            )
        return analyze_market_bars(symbol=symbol, provider_symbol=symbol, bars=bars)

    monkeypatch.setattr(desk_api, "fetch_market_context", fake_context)
    # The calendar is network-backed; a report must compose without it.
    from app.services.desk import calendar as calendar_service

    monkeypatch.setattr(
        calendar_service,
        "fetch_calendar",
        lambda: calendar_service.CalendarFeed(events=(), available=False, reason="test"),
    )
    yield


def test_generate_is_idempotent_per_day() -> None:
    first = client.post("/api/v1/desk/reports/generate")
    second = client.post("/api/v1/desk/reports/generate")
    assert first.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    body = first.json()
    assert body["title"]
    assert body["payload"]["assets_analyzed"] > 0
    assert body["payload"]["instruments"]
    # The delayed-data caveat must always survive into the stored report.
    assert any("delayed" in c.lower() for c in body["payload"]["caveats"])


def test_reports_list_and_read_state() -> None:
    generated = client.post("/api/v1/desk/reports/generate").json()

    listing = client.get("/api/v1/desk/reports").json()
    assert len(listing) == 1
    assert listing[0]["read_at"] is None
    assert listing[0]["assets_analyzed"] == generated["payload"]["assets_analyzed"]

    marked = client.patch(f"/api/v1/desk/reports/{generated['id']}/read").json()
    assert marked["read_at"] is not None
    # Marking read twice keeps the first timestamp.
    again = client.patch(f"/api/v1/desk/reports/{generated['id']}/read").json()
    assert again["read_at"] == marked["read_at"]


def test_report_detail_404s_for_unknown_id() -> None:
    response = client.get(f"/api/v1/desk/reports/{uuid4()}")
    assert response.status_code == 404
