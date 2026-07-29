"""Financial news headlines via Financial Modeling Prep.

Degradation is the important part of this module. With no API key, a rate-limit
response, or an upstream outage, the feed returns *empty with a stated reason* —
it never invents headlines and never silently shows a stale feed as live. A
trading dashboard that fabricates news is worse than one with no news panel.

Fetches go through `safe_fetch`, so a redirect cannot walk the request onto a
loopback or metadata address.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse

from app.core.config import settings
from app.core.logging import get_logger
from app.services.market_data import (
    ASSET_COMMODITY,
    ASSET_CRYPTO,
    ASSET_FX,
    ASSET_INDEX,
    asset_class_for,
)
from app.services.safe_fetch import SsrfError, safe_urlopen

logger = get_logger("app.desk.news")

NEWS_CACHE_TTL_SECONDS = 300.0
# Served rather than 502-ing when the upstream is briefly unavailable. Items
# carry their own timestamps, and the feed is flagged `stale` so the UI can say
# so instead of implying the headlines are current.
NEWS_STALE_MAX_SECONDS = 3_600.0

_FMP_STABLE = "https://financialmodelingprep.com/stable/news/general-latest"
_FMP_LEGACY = "https://financialmodelingprep.com/api/v4/general_news"

# Per-instrument news. FMP splits news by asset class; the right endpoint
# depends on what the symbol is. Six-letter FX pairs and metals hit the forex
# endpoint, BTC/ETH the crypto one, everything else the stock endpoint.
_FMP_FOREX_NEWS = "https://financialmodelingprep.com/api/v4/forex_news"
_FMP_CRYPTO_NEWS = "https://financialmodelingprep.com/api/v4/crypto_news"
_FMP_STOCK_NEWS = "https://financialmodelingprep.com/api/v3/stock_news"

_CRYPTO_SYMBOLS = {"BTC", "ETH"}
_METAL_SYMBOLS = {"XAUUSD", "XAGUSD"}

_REQUEST_TIMEOUT = 8.0
_MAX_BYTES = 1_000_000

_cache: dict[str, tuple[list[NewsItem], float]] = {}
_cache_lock = threading.Lock()


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    source: str
    published_at: datetime | None
    summary: str | None = None
    image_url: str | None = None
    symbol: str | None = None

    @property
    def age_label(self) -> str | None:
        """Compact `36m ago` / `2h ago` label, or None without a timestamp."""
        if self.published_at is None:
            return None
        seconds = int((datetime.now(UTC) - self.published_at).total_seconds())
        if seconds < 0:
            return "just now"
        if seconds < 3_600:
            return f"{max(1, seconds // 60)}m ago"
        if seconds < 86_400:
            return f"{seconds // 3_600}h ago"
        return f"{seconds // 86_400}d ago"


@dataclass(frozen=True)
class NewsFeed:
    items: tuple[NewsItem, ...]
    available: bool
    stale: bool = False
    reason: str | None = None
    provider: str = "fmp"


def _configured() -> bool:
    return bool(settings.fmp_api_key)


def _parse_timestamp(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    for candidate in (text, text.replace(" ", "T")):
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _hostname(url: str) -> str:
    try:
        return urlparse(url).hostname or "unknown"
    except ValueError:
        return "unknown"


def _item_from_row(row: object) -> NewsItem | None:
    """Build an item from one upstream row, tolerating FMP's field drift.

    FMP spells the same concepts differently across its news endpoints
    (`site`/`publisher`, `text`/`content`, `publishedDate`/`date`), so each is
    read positionally rather than assuming one schema.
    """
    if not isinstance(row, dict):
        return None
    title = row.get("title")
    url = row.get("url") or row.get("link")
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return None

    source = row.get("site") or row.get("publisher") or row.get("source")
    summary = row.get("text") or row.get("content") or row.get("snippet")
    image = row.get("image") or row.get("imageUrl")
    symbol = row.get("symbol") or row.get("tickers")

    if isinstance(summary, str):
        summary = summary.strip() or None
        if summary and len(summary) > 400:
            summary = summary[:397].rstrip() + "…"
    else:
        summary = None

    return NewsItem(
        title=title.strip(),
        url=url,
        source=source.strip() if isinstance(source, str) and source.strip() else _hostname(url),
        published_at=_parse_timestamp(row.get("publishedDate") or row.get("date")),
        summary=summary,
        image_url=image if isinstance(image, str) and image.startswith("http") else None,
        symbol=symbol if isinstance(symbol, str) and symbol.strip() else None,
    )


def _request(url: str) -> list[object]:
    with safe_urlopen(
        url,
        timeout=_REQUEST_TIMEOUT,
        headers={"User-Agent": "QuantLabsDesk/0.1 (+local-first trading journal)"},
    ) as response:
        payload = json.loads(response.read(_MAX_BYTES))
    if isinstance(payload, dict):
        # FMP reports quota and auth problems as a 200 with an error body.
        message = payload.get("Error Message") or payload.get("message")
        raise ValueError(str(message) if message else "Unexpected news payload.")
    if not isinstance(payload, list):
        raise ValueError("Unexpected news payload.")
    return payload


def _fetch_from_provider(limit: int) -> list[NewsItem]:
    key = settings.fmp_api_key
    attempts = (
        f"{_FMP_STABLE}?{urlencode({'page': 0, 'limit': limit, 'apikey': key})}",
        f"{_FMP_LEGACY}?{urlencode({'page': 0, 'apikey': key})}",
    )
    last_error: Exception | None = None
    for url in attempts:
        try:
            rows = _request(url)
        except (HTTPError, URLError, SsrfError, TimeoutError, ValueError, OSError) as exc:
            last_error = exc
            logger.warning("news endpoint failed (%s): %s", type(exc).__name__, exc)
            continue
        items = [item for item in (_item_from_row(row) for row in rows) if item is not None]
        if items:
            return items[:limit]
    if last_error is not None:
        raise last_error
    return []


def fetch_news(limit: int = 12) -> NewsFeed:
    """Return the latest headlines, or an empty feed explaining why not."""
    if not _configured():
        return NewsFeed(
            items=(),
            available=False,
            reason="No FMP_API_KEY is configured, so the news feed is unavailable.",
        )

    cache_key = f"general:{limit}"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and now - cached[1] < NEWS_CACHE_TTL_SECONDS:
            return NewsFeed(items=tuple(cached[0]), available=True)

    try:
        items = _fetch_from_provider(limit)
    except Exception as exc:  # noqa: BLE001 - the panel degrades, never 500s
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached and now - cached[1] < NEWS_STALE_MAX_SECONDS:
                logger.warning("news provider failed; serving stale cache: %s", exc)
                return NewsFeed(
                    items=tuple(cached[0]),
                    available=True,
                    stale=True,
                    reason="Showing cached headlines; the news provider is unreachable.",
                )
        return NewsFeed(
            items=(),
            available=False,
            reason=f"The news provider is unavailable ({type(exc).__name__}).",
        )

    with _cache_lock:
        _cache[cache_key] = (items, time.monotonic())
    return NewsFeed(items=tuple(items), available=True)


def _symbol_news_url(symbol: str, limit: int) -> str:
    """Pick the FMP endpoint that actually covers this instrument.

    Routing is by asset class rather than by string shape. Guessing from the
    string breaks on names like ``NASDAQ`` — six alphabetic characters, which
    a naive check reads as an FX pair.

    Index and commodity futures have no per-instrument FMP news endpoint, so
    they fall back to the general financial feed. That is broader than the
    instrument, which is honest; querying ``tickers=ES`` would just return
    nothing and look like "no news" rather than "no coverage".
    """
    key = settings.fmp_api_key
    normalized = symbol.strip().upper().replace("/", "")
    asset_class = asset_class_for(normalized)

    if asset_class == ASSET_CRYPTO or normalized in _CRYPTO_SYMBOLS:
        base = normalized if normalized.endswith("USD") else f"{normalized}USD"
        query = urlencode({"symbol": base, "page": 0, "apikey": key})
        return f"{_FMP_CRYPTO_NEWS}?{query}"
    if asset_class == ASSET_FX or normalized in _METAL_SYMBOLS:
        query = urlencode({"symbol": normalized, "page": 0, "apikey": key})
        return f"{_FMP_FOREX_NEWS}?{query}"
    if asset_class in (ASSET_INDEX, ASSET_COMMODITY):
        query = urlencode({"page": 0, "limit": limit, "apikey": key})
        return f"{_FMP_STABLE}?{query}"
    query = urlencode({"tickers": normalized, "limit": limit, "apikey": key})
    return f"{_FMP_STOCK_NEWS}?{query}"


def fetch_symbol_news(symbol: str, limit: int = 5) -> NewsFeed:
    """Headlines for one instrument, with the same honesty rules as the rail.

    These feed the bias cards, so degradation matters twice over: an invented
    or stale-but-unlabelled headline next to a directional call would launder
    fiction into the analysis. No key or no coverage → explicitly unavailable.
    """
    if not _configured():
        return NewsFeed(
            items=(),
            available=False,
            reason="No FMP_API_KEY is configured, so instrument news is unavailable.",
        )

    normalized = symbol.strip().upper().replace("/", "")
    cache_key = f"symbol:{normalized}:{limit}"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and now - cached[1] < NEWS_CACHE_TTL_SECONDS:
            return NewsFeed(items=tuple(cached[0]), available=True)

    try:
        rows = _request(_symbol_news_url(normalized, limit))
        items = [
            item for item in (_item_from_row(row) for row in rows) if item is not None
        ][:limit]
    except Exception as exc:  # noqa: BLE001 - a bias card must not 500 on news
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached and now - cached[1] < NEWS_STALE_MAX_SECONDS:
                return NewsFeed(
                    items=tuple(cached[0]),
                    available=True,
                    stale=True,
                    reason="Showing cached headlines; the news provider is unreachable.",
                )
        logger.warning("symbol news failed for %s: %s", normalized, exc)
        return NewsFeed(
            items=(),
            available=False,
            reason=f"Instrument news is unavailable ({type(exc).__name__}).",
        )

    with _cache_lock:
        _cache[cache_key] = (items, time.monotonic())
    return NewsFeed(items=tuple(items), available=True)
