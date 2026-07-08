"""Tests for the vault edit endpoints (Phase 1.6)."""

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_document_can_be_edited_and_relearned() -> None:
    created = client.post(
        "/api/v1/vault/documents",
        json={
            "title": "Draft notes",
            "document_type": "note",
            "content_text": "vwap pullback continuation",
            "metadata": {"tags": ["vwap"]},
        },
    )
    assert created.status_code == 201
    document_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/vault/documents/{document_id}",
        json={"title": "Refined ORB plan", "content_text": "opening range breakout momentum"},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["title"] == "Refined ORB plan"
    assert body["content_text"] == "opening range breakout momentum"
    # Learning was re-run against the edited content, keeping the same doc id.
    learned = body["metadata"]["learned_memory"]
    assert learned["status"] == "learned"

    # The graph now reflects the new title, not the stale one.
    nodes = client.get("/api/v1/graph/nodes").json()
    labels = {node["label"] for node in nodes}
    assert "Refined ORB plan" in labels
    assert "Draft notes" not in labels


def test_edit_missing_document_is_404() -> None:
    missing = client.patch(
        "/api/v1/vault/documents/00000000-0000-0000-0000-0000000000aa",
        json={"title": "x"},
    )
    assert missing.status_code == 404


def test_journal_entry_can_be_edited() -> None:
    created = client.post(
        "/api/v1/vault/journal-entries",
        json={
            "entry_date": "2026-07-08",
            "title": "Morning",
            "body": "prep done",
            "emotional_state": "calm",
            "tags": ["prep"],
        },
    )
    entry_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/vault/journal-entries/{entry_id}",
        json={"body": "prep done, waited for setup", "tags": ["prep", "patience"]},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["body"] == "prep done, waited for setup"
    assert body["tags"] == ["prep", "patience"]
    assert body["title"] == "Morning"  # untouched fields preserved
