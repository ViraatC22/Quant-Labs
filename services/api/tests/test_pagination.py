"""Phase 2.3: optional pagination on list endpoints (backward compatible)."""

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def _make_trade(symbol: str) -> None:
    response = client.post(
        "/api/v1/trades",
        json={
            "symbol": symbol,
            "side": "long",
            "entry_time": "2026-07-08T14:30:00Z",
            "entry_price": "100",
            "quantity": "1",
        },
    )
    assert response.status_code == 201


def test_trades_pagination_defaults_to_all_and_respects_limit_offset() -> None:
    for i in range(5):
        _make_trade(f"SYM{i}")

    # No params -> full list (backward compatible).
    assert len(client.get("/api/v1/trades").json()) == 5

    # limit caps the page.
    page = client.get("/api/v1/trades", params={"limit": 2}).json()
    assert len(page) == 2

    # offset walks the ordered list without overlap.
    second = client.get("/api/v1/trades", params={"limit": 2, "offset": 2}).json()
    assert len(second) == 2
    assert {t["id"] for t in page}.isdisjoint({t["id"] for t in second})


def test_invalid_pagination_params_are_rejected() -> None:
    assert client.get("/api/v1/trades", params={"limit": 0}).status_code == 422
    assert client.get("/api/v1/trades", params={"offset": -1}).status_code == 422
