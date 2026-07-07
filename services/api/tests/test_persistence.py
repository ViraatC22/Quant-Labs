from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.v1 import trades as trades_api
from app.main import create_app
from app.services.market_data import MarketQuote

client = TestClient(create_app())


def test_trade_create_list_delete_cycle() -> None:
    payload = {
        "symbol": "aapl",
        "side": "long",
        "entry_time": "2026-07-05T00:00:00Z",
        "entry_price": "100",
        "exit_price": "110",
        "quantity": "10",
        "fees": "1",
        "metadata": {"strategy": "VWAP Pullback", "setup": "ORB"},
    }

    created = client.post("/api/v1/trades", json=payload)
    assert created.status_code == 201
    body = created.json()
    trade_id = body["id"]
    assert body["symbol"] == "AAPL"  # normalized to upper case
    assert body["metadata"]["strategy"] == "VWAP Pullback"

    listing = client.get("/api/v1/trades")
    assert listing.status_code == 200
    assert any(trade["id"] == trade_id for trade in listing.json())

    deleted = client.delete(f"/api/v1/trades/{trade_id}")
    assert deleted.status_code == 204
    assert all(trade["id"] != trade_id for trade in client.get("/api/v1/trades").json())

    missing = client.delete(f"/api/v1/trades/{trade_id}")
    assert missing.status_code == 404


def test_journal_and_document_persist_and_delete() -> None:
    journal = client.post(
        "/api/v1/vault/journal-entries",
        json={
            "entry_date": "2026-07-05",
            "title": "Morning prep",
            "body": "Waited for the setup.",
            "emotional_state": "focused",
            "tags": ["prep"],
            "metadata": {"routineDone": True},
        },
    )
    assert journal.status_code == 201
    journal_id = journal.json()["id"]

    document = client.post(
        "/api/v1/vault/documents",
        json={
            "title": "ORB notes",
            "document_type": "strategy",
            "content_text": "opening range breakout",
            "metadata": {"tags": ["orb"]},
        },
    )
    assert document.status_code == 201
    document_body = document.json()
    document_id = document_body["id"]
    learned = document_body["metadata"]["learned_memory"]
    assert learned["status"] == "learned"
    assert learned["chunk_count"] >= 1
    assert learned["node_count"] >= 3
    assert "ORB notes" in learned["map_labels"]

    assert any(e["id"] == journal_id for e in client.get("/api/v1/vault/journal-entries").json())
    assert any(d["id"] == document_id for d in client.get("/api/v1/vault/documents").json())
    graph_nodes = client.get("/api/v1/graph/nodes").json()
    graph_edges = client.get("/api/v1/graph/edges").json()
    assert any(
        node["label"] == "ORB notes" and node["node_type"] == "source"
        for node in graph_nodes
    )
    assert any(edge["edge_type"] == "supports_strategy" for edge in graph_edges)
    recommendations = client.get("/api/v1/trades/recommendations")
    assert recommendations.status_code == 200
    recommendation_body = recommendations.json()
    assert recommendation_body
    assert recommendation_body[0]["strategy"] == "ORB notes"
    assert "orb" in recommendation_body[0]["technical_tags"]
    assert recommendation_body[0]["draft"]["strategy"] == "ORB notes"
    assert recommendation_body[0]["draft"]["symbol"]
    assert recommendation_body[0]["draft"]["setup"] == "Opening range breakout"

    assert client.delete(f"/api/v1/vault/journal-entries/{journal_id}").status_code == 204
    assert client.delete(f"/api/v1/vault/documents/{document_id}").status_code == 204


def test_records_are_scoped_per_user() -> None:
    other_user = "00000000-0000-0000-0000-0000000000ff"
    created = client.post(
        "/api/v1/trades",
        json={
            "symbol": "MSFT",
            "side": "long",
            "entry_time": "2026-07-05T00:00:00Z",
            "entry_price": "1",
            "quantity": "1",
        },
    )
    trade_id = created.json()["id"]

    # A different user cannot see or delete the demo user's trade.
    other_listing = client.get("/api/v1/trades", headers={"x-user-id": other_user})
    assert all(trade["id"] != trade_id for trade in other_listing.json())
    assert (
        client.delete(f"/api/v1/trades/{trade_id}", headers={"x-user-id": other_user}).status_code
        == 404
    )


def test_open_trade_can_be_closed_with_patch() -> None:
    created = client.post(
        "/api/v1/trades",
        json={
            "symbol": "SPY",
            "side": "long",
            "entry_time": "2026-07-07T00:00:00Z",
            "entry_price": "100",
            "quantity": "2",
            "metadata": {"strategy": "Live test", "setup": "Quote mark"},
        },
    )

    assert created.status_code == 201
    created_body = created.json()
    assert created_body["exit_price"] is None
    assert created_body["pnl_amount"] is None

    updated = client.patch(
        f"/api/v1/trades/{created_body['id']}",
        json={"exit_price": "105", "metadata": {"status": "closed"}},
    )

    assert updated.status_code == 200
    updated_body = updated.json()
    assert Decimal(updated_body["pnl_amount"]) == Decimal("10.000000")
    assert updated_body["metadata"]["status"] == "closed"


def test_quote_endpoint_uses_market_data_adapter(monkeypatch) -> None:
    def fake_quote(symbol: str) -> MarketQuote:
        return MarketQuote(
            symbol=symbol.upper(),
            provider_symbol=symbol.upper(),
            provider="test",
            last_price=Decimal("101.25"),
            previous_close=Decimal("100.00"),
            currency="USD",
            market_time=datetime(2026, 7, 7, 14, 30, tzinfo=UTC),
        )

    monkeypatch.setattr(trades_api, "fetch_market_quote", fake_quote)

    response = client.get("/api/v1/trades/quotes/spy")

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "SPY"
    assert Decimal(body["last_price"]) == Decimal("101.2500")
    assert body["provider"] == "test"


def test_strategy_evaluation_scores_idea_and_logs_journal(monkeypatch) -> None:
    def fake_quote(symbol: str) -> MarketQuote:
        return MarketQuote(
            symbol=symbol.upper(),
            provider_symbol=symbol.upper(),
            provider="test",
            last_price=Decimal("5000"),
            currency="USD",
            market_time=datetime(2026, 7, 7, 14, 30, tzinfo=UTC),
        )

    monkeypatch.setattr(trades_api, "fetch_market_quote", fake_quote)
    document = client.post(
        "/api/v1/vault/documents",
        json={
            "title": "VWAP reclaim playbook",
            "document_type": "strategy",
            "content_text": "Use VWAP pullback with momentum, stop loss, and position sizing.",
            "metadata": {"tags": ["vwap", "momentum"]},
        },
    )
    assert document.status_code == 201

    evaluation = client.post(
        "/api/v1/trades/strategy/evaluate",
        json={
            "idea": "Trade ES long when momentum reclaims VWAP with a clear stop and size cap.",
            "symbol": "ES",
        },
    )

    assert evaluation.status_code == 200
    body = evaluation.json()
    assert body["journal_entry_id"]
    assert "vwap" in body["technical_tags"]
    assert Decimal(body["draft"]["entry_price"]) == Decimal("5000")
    assert body["draft"]["exit_price"]

    journal = client.get("/api/v1/vault/journal-entries").json()
    assert any(entry["id"] == body["journal_entry_id"] for entry in journal)
