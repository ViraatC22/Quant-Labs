"""Regression tests for the Phase 1 trade correctness fixes.

Covers: contract-multiplier P&L (C2), the PATCH-clobbers-P&L bug (C4), enum
validation of side/asset_class (C5), and client-supplied UUID replay (C7).
"""

from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_pnl_includes_contract_multiplier() -> None:
    # 2-lot MES future, +5 points, multiplier 5 -> (5)*2*5 = 50, minus 1 fee.
    created = client.post(
        "/api/v1/trades",
        json={
            "symbol": "MES",
            "asset_class": "future",
            "side": "long",
            "entry_time": "2026-07-08T14:30:00Z",
            "entry_price": "5000",
            "exit_price": "5005",
            "quantity": "2",
            "contract_multiplier": "5",
            "fees": "1",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert Decimal(body["contract_multiplier"]) == Decimal("5.000000")
    assert Decimal(body["pnl_amount"]) == Decimal("49.000000")


def test_short_pnl_direction() -> None:
    created = client.post(
        "/api/v1/trades",
        json={
            "symbol": "AAPL",
            "side": "short",
            "entry_time": "2026-07-08T14:30:00Z",
            "entry_price": "100",
            "exit_price": "90",
            "quantity": "10",
        },
    )
    # short win: (100-90)*10*1 = 100
    assert Decimal(created.json()["pnl_amount"]) == Decimal("100.000000")


def test_patch_without_pnl_does_not_clobber_manual_value() -> None:
    created = client.post(
        "/api/v1/trades",
        json={
            "symbol": "TSLA",
            "side": "long",
            "entry_time": "2026-07-08T14:30:00Z",
            "entry_price": "200",
            "exit_price": "210",
            "quantity": "5",
            "pnl_amount": "999.5",  # manually recorded (e.g. broker-adjusted)
        },
    )
    trade_id = created.json()["id"]
    assert Decimal(created.json()["pnl_amount"]) == Decimal("999.500000")

    # Update only fees; omitting pnl_amount must preserve the manual value.
    updated = client.patch(f"/api/v1/trades/{trade_id}", json={"fees": "2"})
    assert updated.status_code == 200
    assert Decimal(updated.json()["pnl_amount"]) == Decimal("999.500000")

    # Explicitly clearing pnl_amount triggers a recompute.
    recomputed = client.patch(f"/api/v1/trades/{trade_id}", json={"pnl_amount": None})
    assert Decimal(recomputed.json()["pnl_amount"]) == Decimal("48.000000")  # (210-200)*5 - 2


def test_invalid_side_is_rejected() -> None:
    response = client.post(
        "/api/v1/trades",
        json={
            "symbol": "AAPL",
            "side": "Long",  # wrong case -> not a valid enum member
            "entry_time": "2026-07-08T14:30:00Z",
            "entry_price": "100",
            "quantity": "1",
        },
    )
    assert response.status_code == 422


def test_invalid_asset_class_is_rejected() -> None:
    response = client.post(
        "/api/v1/trades",
        json={
            "symbol": "AAPL",
            "asset_class": "stonks",
            "side": "long",
            "entry_time": "2026-07-08T14:30:00Z",
            "entry_price": "100",
            "quantity": "1",
        },
    )
    assert response.status_code == 422


def test_client_supplied_uuid_replays_idempotently() -> None:
    trade_id = "11111111-2222-3333-4444-555555555555"
    payload = {
        "id": trade_id,
        "symbol": "NVDA",
        "side": "long",
        "entry_time": "2026-07-08T14:30:00Z",
        "entry_price": "100",
        "quantity": "1",
    }
    first = client.post("/api/v1/trades", json=payload)
    assert first.status_code == 201
    assert first.json()["id"] == trade_id

    # Replaying the same id must not create a duplicate; it conflicts instead.
    second = client.post("/api/v1/trades", json=payload)
    assert second.status_code == 409
    listing = client.get("/api/v1/trades").json()
    assert sum(1 for t in listing if t["id"] == trade_id) == 1
