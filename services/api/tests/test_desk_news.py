"""News adapter tests, focused on how it degrades rather than the happy path.

The failure modes matter more than the success case here: a trading dashboard
that shows invented or silently-stale headlines is actively misleading.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.services.desk import news
from app.services.desk.news import NewsItem, fetch_news


@pytest.fixture(autouse=True)
def clear_news_cache():
    news._cache.clear()
    yield
    news._cache.clear()


def _install_rows(monkeypatch, rows, *, fail: bool = False) -> dict:
    """Point the adapter at an in-memory payload instead of the network."""
    calls = {"n": 0}

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, _limit=None):
            return json.dumps(rows).encode()

    def fake_open(url, timeout, headers=None):
        calls["n"] += 1
        if fail:
            raise TimeoutError("provider down")
        return _FakeResponse()

    monkeypatch.setattr(news, "safe_urlopen", fake_open)
    return calls


def _with_key(monkeypatch, key: str = "test-key") -> None:
    # Settings is a frozen dataclass, so swap the whole object rather than
    # mutating a field (matching the convention in test_ai_router.py).
    monkeypatch.setattr(news, "settings", replace(news.settings, fmp_api_key=key))


def test_missing_key_reports_unavailable_rather_than_empty_success(monkeypatch) -> None:
    monkeypatch.setattr(news, "settings", replace(news.settings, fmp_api_key=""))
    feed = fetch_news()
    assert feed.available is False
    assert feed.items == ()
    assert feed.reason is not None
    assert "FMP_API_KEY" in feed.reason


def test_headlines_are_parsed_from_the_provider(monkeypatch) -> None:
    _with_key(monkeypatch)
    _install_rows(
        monkeypatch,
        [
            {
                "title": "Dollar firms into the close",
                "url": "https://example.com/a",
                "site": "example.com",
                "publishedDate": "2026-07-24 12:30:00",
                "text": "Some body text.",
            }
        ],
    )
    feed = fetch_news(limit=5)
    assert feed.available is True
    assert len(feed.items) == 1
    item = feed.items[0]
    assert item.title == "Dollar firms into the close"
    assert item.source == "example.com"
    assert item.published_at == datetime(2026, 7, 24, 12, 30, tzinfo=UTC)


def test_rows_without_a_title_or_url_are_dropped(monkeypatch) -> None:
    _with_key(monkeypatch)
    _install_rows(
        monkeypatch,
        [
            {"title": "", "url": "https://example.com/a"},
            {"title": "No link here", "url": None},
            {"title": "Not a real scheme", "url": "javascript:alert(1)"},
            {"title": "Good one", "url": "https://example.com/good", "site": "x.com"},
        ],
    )
    feed = fetch_news()
    assert [item.title for item in feed.items] == ["Good one"]


def test_provider_error_body_is_treated_as_a_failure(monkeypatch) -> None:
    # FMP returns quota/auth errors as HTTP 200 with an error object.
    _with_key(monkeypatch)
    _install_rows(monkeypatch, {"Error Message": "Limit Reach"})
    feed = fetch_news()
    assert feed.available is False
    assert feed.items == ()


def test_second_call_is_served_from_cache(monkeypatch) -> None:
    _with_key(monkeypatch)
    calls = _install_rows(
        monkeypatch,
        [{"title": "One", "url": "https://example.com/1", "site": "example.com"}],
    )
    fetch_news(limit=3)
    fetch_news(limit=3)
    # Two endpoint variants exist, but a cache hit must not re-enter the network.
    assert calls["n"] == 1


def test_outage_serves_stale_cache_flagged_as_stale(monkeypatch) -> None:
    _with_key(monkeypatch)
    _install_rows(
        monkeypatch,
        [{"title": "Cached", "url": "https://example.com/1", "site": "example.com"}],
    )
    fetch_news(limit=3)

    monkeypatch.setattr(news, "NEWS_CACHE_TTL_SECONDS", 0.0)
    _install_rows(monkeypatch, [], fail=True)
    feed = fetch_news(limit=3)

    assert feed.available is True
    assert feed.stale is True
    assert feed.reason is not None
    assert [item.title for item in feed.items] == ["Cached"]


def test_outage_without_cache_is_unavailable_not_fabricated(monkeypatch) -> None:
    _with_key(monkeypatch)
    _install_rows(monkeypatch, [], fail=True)
    feed = fetch_news()
    assert feed.available is False
    assert feed.items == ()
    assert feed.reason is not None


def test_age_label_buckets_by_magnitude() -> None:
    now = datetime.now(UTC)

    def item(delta: timedelta) -> NewsItem:
        return NewsItem(
            title="t", url="https://e.com", source="e", published_at=now - delta
        )

    assert item(timedelta(minutes=36)).age_label == "36m ago"
    assert item(timedelta(hours=2)).age_label == "2h ago"
    assert item(timedelta(days=3)).age_label == "3d ago"
    assert NewsItem("t", "https://e.com", "e", None).age_label is None
