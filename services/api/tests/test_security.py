"""Security regression tests: SSRF guard (S1) and identity gating (S2)."""

import pytest
from fastapi.testclient import TestClient

from app.core import security
from app.main import create_app
from app.services.safe_fetch import SsrfError, assert_public_url

client = TestClient(create_app())


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:9001/",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "ftp://example.com/",
    ],
)
def test_ssrf_guard_blocks_non_public_and_bad_scheme(url: str) -> None:
    with pytest.raises((SsrfError, ValueError)):
        assert_public_url(url)


def test_import_url_rejects_loopback() -> None:
    response = client.post("/api/v1/vault/import-url", json={"url": "http://localhost:9001/"})
    assert response.status_code == 400


def test_import_url_rejects_metadata_endpoint() -> None:
    response = client.post(
        "/api/v1/vault/import-url",
        json={"url": "http://169.254.169.254/latest/meta-data/"},
    )
    assert response.status_code == 400


class _UntrustedSettings:
    trust_user_header = False


def test_user_header_ignored_when_untrusted(monkeypatch) -> None:
    # Simulate a hosted deployment: the header must not select another user.
    monkeypatch.setattr(security, "settings", _UntrustedSettings)
    other_user = "00000000-0000-0000-0000-0000000000ff"
    resolved = security.get_current_user_id(other_user)
    assert resolved == security.DEMO_USER_ID
