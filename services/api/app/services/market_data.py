from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.core.logging import get_logger

logger = get_logger("app.market_data")

# Server-side cache TTL. Every UI client polls open positions every 30s; without
# this each poll hit the upstream provider directly (per client, per symbol),
# which is both slow and a fast route to a provider ban. One cached fetch now
# serves every client within the window.
QUOTE_CACHE_TTL_SECONDS = float(os.getenv("QUOTE_CACHE_TTL_SECONDS", "20"))
# How long a cached value may still be served as a stale fallback when the
# upstream provider is failing, so an outage degrades to stale marks not 502s.
QUOTE_STALE_MAX_SECONDS = float(os.getenv("QUOTE_STALE_MAX_SECONDS", "900"))


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    provider_symbol: str
    provider: str
    last_price: Decimal
    previous_close: Decimal | None = None
    currency: str | None = None
    market_time: datetime | None = None
    delayed: bool = True
    stale: bool = False


@dataclass
class _CacheEntry:
    quote: MarketQuote
    fetched_at: float


_cache: dict[str, _CacheEntry] = {}
_cache_lock = threading.Lock()


SYMBOL_ALIASES = {
    "ES": "ES=F",
    "MES": "MES=F",
    "NQ": "NQ=F",
    "MNQ": "MNQ=F",
    "YM": "YM=F",
    "RTY": "RTY=F",
    "CL": "CL=F",
    "GC": "GC=F",
    "SI": "SI=F",
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
}


def fetch_market_quote(symbol: str) -> MarketQuote:
    """Return a quote, served from a short-lived server cache when fresh.

    On a cache miss the upstream provider is called. If that fails but a recent
    cached value exists (within QUOTE_STALE_MAX_SECONDS), the stale value is
    returned with ``stale=True`` instead of raising, so a provider outage
    degrades gracefully.
    """
    normalized = _normalize_symbol(symbol)
    now = time.monotonic()

    with _cache_lock:
        entry = _cache.get(normalized)
        if entry and now - entry.fetched_at < QUOTE_CACHE_TTL_SECONDS:
            return entry.quote

    try:
        quote_value = _fetch_from_provider(normalized)
    except (OSError, TimeoutError, ValueError) as exc:
        with _cache_lock:
            entry = _cache.get(normalized)
            if entry and now - entry.fetched_at < QUOTE_STALE_MAX_SECONDS:
                logger.warning(
                    "quote provider failed for %s; serving stale cache: %s", normalized, exc
                )
                return replace(entry.quote, stale=True)
        raise

    with _cache_lock:
        _cache[normalized] = _CacheEntry(quote=quote_value, fetched_at=time.monotonic())
    return quote_value


def _fetch_from_provider(symbol: str) -> MarketQuote:
    normalized = _normalize_symbol(symbol)
    provider_symbol = SYMBOL_ALIASES.get(normalized, normalized)
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{quote(provider_symbol)}?range=1d&interval=1m"
    )
    request = Request(
        url,
        headers={"User-Agent": "QuantLabsMarketData/0.1 (+local-first trading journal)"},
    )
    with urlopen(request, timeout=8) as response:
        raw = response.read(750_000)

    payload = json.loads(raw)
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not isinstance(result, dict):
        raise ValueError(f"No market quote returned for {symbol}.")

    meta = result.get("meta") or {}
    price = meta.get("regularMarketPrice") or meta.get("previousClose")
    if price is None:
        closes = (result.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
        price = next((value for value in reversed(closes) if value is not None), None)
    if price is None:
        raise ValueError(f"No market price returned for {symbol}.")

    market_time = None
    timestamp = meta.get("regularMarketTime")
    if isinstance(timestamp, int | float):
        market_time = datetime.fromtimestamp(timestamp, tz=UTC)

    last_price = _decimal(price)
    if last_price is None:
        raise ValueError(f"No market price returned for {symbol}.")

    return MarketQuote(
        symbol=normalized,
        provider_symbol=provider_symbol,
        provider="yahoo_chart",
        last_price=last_price,
        previous_close=_decimal(meta.get("previousClose")),
        currency=meta.get("currency"),
        market_time=market_time,
        delayed=True,
    )


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace("/", "")


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.0001"))
