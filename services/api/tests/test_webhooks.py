"""TradingView webhook tests.

Security properties first: the endpoint must be dead without a configured
secret, reject a wrong one, and never double-create on a retried delivery.
Then the journaling flow: entry spawns an open record, exit closes it with the
same P&L math the trades API uses, and closing nothing invents nothing.
"""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import webhooks as webhooks_module
from app.main import create_app

client = TestClient(create_app())

SECRET = "test-webhook-secret"


@pytest.fixture(autouse=True)
def configured_secret(monkeypatch):
    monkeypatch.setattr(
        webhooks_module,
        "settings",
        replace(webhooks_module.settings, tradingview_webhook_secret=SECRET),
    )


def _alert(**overrides) -> dict:
    payload = {
        "secret": SECRET,
        "action": "entry",
        "symbol": "EURUSD",
        "side": "long",
        "price": "1.1375",
        "quantity": "2",
        "alert_id": "alert-1",
    }
    payload.update(overrides)
    return payload


def _post(payload: dict):
    return client.post("/api/v1/webhooks/tradingview", json=payload)


def test_endpoint_is_disabled_without_a_configured_secret(monkeypatch) -> None:
    monkeypatch.setattr(
        webhooks_module,
        "settings",
        replace(webhooks_module.settings, tradingview_webhook_secret=""),
    )
    response = _post(_alert())
    assert response.status_code == 503
    assert "disabled" in response.json()["detail"]


def test_wrong_secret_is_rejected(_=None) -> None:
    response = _post(_alert(secret="not-the-secret"))
    assert response.status_code == 401


def test_entry_alert_spawns_an_open_trade_record() -> None:
    response = _post(_alert())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "created"
    assert body["trade_id"] is not None

    trades = client.get("/api/v1/trades").json()
    assert len(trades) == 1
    trade = trades[0]
    assert trade["symbol"] == "EURUSD"
    assert trade["side"] == "long"
    assert trade["exit_price"] is None
    # Provenance: the price came from the alert (TradingView's feed), and the
    # journal must say so.
    assert trade["metadata"]["source"] == "tradingview_webhook"
    assert trade["metadata"]["price_source"] == "tradingview_alert"


def test_entry_without_a_side_is_rejected() -> None:
    response = _post(_alert(side=None))
    assert response.status_code == 422


def test_retried_delivery_does_not_double_create() -> None:
    first = _post(_alert(alert_id="dup-1"))
    second = _post(_alert(alert_id="dup-1"))

    assert first.json()["status"] == "created"
    # 200 so TradingView stops retrying — but nothing new was written.
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert len(client.get("/api/v1/trades").json()) == 1


def test_exit_closes_the_open_record_with_computed_pnl() -> None:
    _post(_alert(alert_id="rt-entry"))
    response = _post(
        _alert(action="exit", price="1.1475", alert_id="rt-exit", side=None)
    )

    body = response.json()
    assert body["status"] == "closed"

    trade = client.get("/api/v1/trades").json()[0]
    assert trade["exit_price"] == "1.147500"
    # long 2 units, +0.01 move, multiplier 1, no fees -> 0.02
    assert float(trade["pnl_amount"]) == pytest.approx(0.02)
    assert trade["metadata"]["exit_alert_id"] == "rt-exit"


def test_short_round_trip_pnl_is_signed_correctly() -> None:
    _post(_alert(side="short", alert_id="s-entry"))
    _post(_alert(action="exit", price="1.1275", alert_id="s-exit", side=None))

    trade = client.get("/api/v1/trades").json()[0]
    # short 2 units, price fell 0.01 -> +0.02
    assert float(trade["pnl_amount"]) == pytest.approx(0.02)


def test_exit_with_no_open_trade_invents_nothing() -> None:
    response = _post(_alert(action="exit", side=None, alert_id="lonely-exit"))
    assert response.status_code == 200
    assert response.json()["status"] == "no_open_trade"
    assert client.get("/api/v1/trades").json() == []


def test_retried_exit_delivery_is_a_duplicate_not_a_second_close() -> None:
    _post(_alert(alert_id="x-entry"))
    _post(_alert(action="exit", price="1.1475", alert_id="x-exit", side=None))
    retry = _post(_alert(action="exit", price="1.1475", alert_id="x-exit", side=None))

    assert retry.json()["status"] == "duplicate"


def test_exit_closes_the_most_recent_open_record_for_the_symbol() -> None:
    _post(_alert(alert_id="a1", price="1.1000"))
    _post(_alert(alert_id="a2", price="1.2000"))
    _post(_alert(action="exit", price="1.2100", alert_id="a3", side=None))

    trades = client.get("/api/v1/trades").json()
    open_trades = [t for t in trades if t["exit_price"] is None]
    closed = [t for t in trades if t["exit_price"] is not None]
    assert len(open_trades) == 1
    assert len(closed) == 1
    assert closed[0]["entry_price"] == "1.200000"
