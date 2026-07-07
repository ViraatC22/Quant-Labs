from fastapi.testclient import TestClient

from app.api.v1 import vault
from app.main import create_app

ARXIV_ATOM = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<feed xmlns="http://www.w3.org/2005/Atom" '
    b'xmlns:arxiv="http://arxiv.org/schemas/atom">'
    b"<entry>"
    b"<id>https://arxiv.org/abs/2607.01705v1</id>"
    b"<updated>2026-07-02T04:56:40Z</updated>"
    b"<published>2026-07-02T04:56:40Z</published>"
    b"<title>Portfolio Optimization under Fast and Slow Latent "
    b"Mean-Reverting and Momentum Drift</title>"
    b"<summary>We show that the filtered estimate is driven by fast and slow "
    b"EMA-type processes of trailing price history, yielding a MACD-type signal. "
    b"We derive candidate optimal strategies in explicit feedback form.</summary>"
    b"<author><name>Dannin J. Eccles</name></author>"
    b"<author><name>Roger Lee</name></author>"
    b"<arxiv:comment>24 pages. Presented at Quantitative Finance Conference "
    b"2026</arxiv:comment>"
    b"<arxiv:doi>10.48550/arXiv.2607.01705</arxiv:doi>"
    b'<arxiv:primary_category term="q-fin.MF"/>'
    b'<category term="q-fin.MF"/>'
    b'<link href="https://arxiv.org/pdf/2607.01705v1" '
    b'title="pdf" type="application/pdf"/>'
    b"</entry>"
    b"</feed>"
)


class _FakeResponse:
    headers = {"content-type": "application/atom+xml"}

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return ARXIV_ATOM


def test_import_file_auto_extracts_text_fields() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/vault/import-file",
        files={
            "file": (
                "orb-notes.md",
                (
                    b"# ORB Strategy\nWait for VWAP, fair value gap, "
                    b"liquidity sweep, and volume confirmation."
                ),
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Orb Notes"
    assert payload["kind"] == "note"
    assert payload["source"] == "orb-notes.md"
    assert "Wait for VWAP" in payload["body"]
    assert "orb" in payload["tags"]
    assert "orb" in payload["ai_tags"]
    assert "opening-range-breakout" in payload["ai_tags"]
    assert payload["strategy_info"]["setup"] == "Opening range breakout"
    assert "Volume" in payload["strategy_info"]["indicators"]
    assert "vwap" in payload["metadata"]["technical_tags"]
    assert "fair-value-gap" in payload["metadata"]["technical_tags"]
    assert "liquidity-sweep" in payload["metadata"]["technical_tags"]
    assert "market_structure" in payload["metadata"]["technical_profile"]
    assert payload["metadata"]["enrichment_method"] == "local_semantic_rules"
    assert payload["metadata"]["ai_router"]["mode"] == "local"


def test_import_arxiv_pdf_scrapes_paper_metadata(monkeypatch) -> None:
    def fake_urlopen(request, timeout=10):  # noqa: ANN001
        assert "export.arxiv.org/api/query" in request.full_url
        assert timeout == 10
        return _FakeResponse()

    monkeypatch.setattr(vault, "urlopen", fake_urlopen)
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/vault/import-url",
        json={"url": "https://arxiv.org/pdf/2607.01705"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == (
        "Portfolio Optimization under Fast and Slow Latent Mean-Reverting and Momentum Drift"
    )
    assert payload["kind"] == "paper"
    assert "Dannin J. Eccles" in payload["metadata"]["source_details"]["authors"]
    assert payload["metadata"]["source_details"]["submitted"] == "2026-07-02"
    assert "q-fin.MF" == payload["metadata"]["source_details"]["primary_category"]
    assert "MACD-type signal" in payload["body"]
    assert payload["strategy_info"]["name"] == payload["title"]
    assert "MACD" in payload["strategy_info"]["indicators"]
    assert "Stochastic" not in payload["strategy_info"]["indicators"]
    assert "macd" in payload["metadata"]["technical_tags"]
    assert "paper" in payload["tags"]


def test_ai_provider_status_defaults_to_local_mode() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/vault/ai/providers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "local"
    assert payload["active_provider_id"] is None
    assert [provider["id"] for provider in payload["providers"]] == [
        "openrouter",
        "groq",
        "gemini",
        "cerebras",
    ]
