from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from math import sqrt
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
CONTEXT_CACHE_TTL_SECONDS = float(os.getenv("CONTEXT_CACHE_TTL_SECONDS", "300"))
CONTEXT_STALE_MAX_SECONDS = float(os.getenv("CONTEXT_STALE_MAX_SECONDS", "3600"))

# Trailing bars used for `change_percent` and trend efficiency. This is a
# recent-move window, NOT the full sample — callers describing the number to a
# user must say "last 13 bars", not "over the sample".
CHANGE_WINDOW_BARS = 13


# What a price actually is, ordered by how safe it is to execute against.
# This distinction is the whole point: a delayed indicative FX mid and a live
# top-of-book bid/ask are the same `Decimal` but mean completely different
# things at fill time. Callers that size real orders must branch on this
# rather than trusting `last_price` alone.
PRICE_BASIS_TOP_OF_BOOK = "top_of_book"
"""Live bid/ask from the venue the order will actually be routed to."""

PRICE_BASIS_LAST_TRADE = "last_trade"
"""Last printed trade on some venue. Not a quote; no size behind it."""

PRICE_BASIS_INDICATIVE_MID = "indicative_mid"
"""Aggregated FX/metal mid. No venue will fill you here — the real cost is
this value plus half the spread, and the spread is not in this feed."""


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
    # Bid/ask are None whenever the upstream feed does not publish a real book.
    # They are deliberately not synthesized from `last_price` — an invented
    # spread is worse than a missing one, because it looks like information.
    bid: Decimal | None = None
    ask: Decimal | None = None
    price_basis: str = PRICE_BASIS_LAST_TRADE
    # Set when the provider served a different instrument than the one asked
    # for (see SYMBOL_PROXIES), e.g. gold futures standing in for spot XAUUSD.
    proxy_note: str | None = None

    @property
    def spread(self) -> Decimal | None:
        """Absolute bid/ask spread, or None when the feed has no book."""
        if self.bid is None or self.ask is None:
            return None
        return self.ask - self.bid

    @property
    def executable(self) -> bool:
        """True only when this price is safe to size a live order against.

        A delayed price is never executable, and neither is an indicative mid
        or a bare last-trade print. In practice this is False for every quote
        the Yahoo adapter produces, which is the correct and intended answer:
        routing live orders requires a feed from the execution venue itself.
        """
        return (
            not self.delayed
            and not self.stale
            and self.price_basis == PRICE_BASIS_TOP_OF_BOOK
            and self.bid is not None
            and self.ask is not None
        )


@dataclass(frozen=True)
class PriceBar:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None


@dataclass(frozen=True)
class MarketContext:
    symbol: str
    provider_symbol: str
    provider: str
    interval: str
    lookback: str
    as_of: datetime
    delayed: bool
    stale: bool
    sample_size: int
    last_price: float
    change_percent: float
    rsi_14: float | None
    atr_percent: float | None
    bollinger_width_percent: float | None
    volume_percentile: float | None
    trend_efficiency: float | None
    flow: str
    bearing: str
    pulse: str
    confidence: float
    limitations: tuple[str, ...]
    price_basis: str = PRICE_BASIS_LAST_TRADE
    proxy_note: str | None = None


@dataclass
class _CacheEntry:
    quote: MarketQuote
    fetched_at: float


_cache: dict[str, _CacheEntry] = {}
_context_cache: dict[str, tuple[MarketContext, float]] = {}
_cache_lock = threading.Lock()


SYMBOL_ALIASES = {
    # --- Index futures ----------------------------------------------------
    # Futures rather than cash indices throughout, for a concrete reason:
    # Yahoo returns real volume for `=F` contracts and *none* for `^` cash
    # indices (^GDAXI, ^FTSE, ^N225, ^RUT all come back with zero volume
    # bars). No volume means no Flow reading and no participation signal, so
    # the futures leg is the better input as well as the tradeable one.
    "ES": "ES=F",
    "MES": "MES=F",
    "NQ": "NQ=F",
    "MNQ": "MNQ=F",
    "YM": "YM=F",
    "RTY": "RTY=F",
    # Broker-style index names traders actually type.
    "US500": "ES=F",
    "SPX500": "ES=F",
    "SP500": "ES=F",
    "US100": "NQ=F",
    "NAS100": "NQ=F",
    "NASDAQ": "NQ=F",
    "US30": "YM=F",
    "DOW": "YM=F",
    "US2000": "RTY=F",
    "RUSSELL": "RTY=F",
    # Cash indices where no liquid Yahoo future exists. These carry no volume,
    # so their Flow reads "unavailable" and coverage drops accordingly.
    "SPX": "^GSPC",
    "NDX": "^NDX",
    "DJI": "^DJI",
    "DAX": "^GDAXI",
    "GER40": "^GDAXI",
    "UK100": "^FTSE",
    "FTSE": "^FTSE",
    "JP225": "^N225",
    "NIKKEI": "^N225",
    # --- Commodities ------------------------------------------------------
    "CL": "CL=F",
    "GC": "GC=F",
    "SI": "SI=F",
    "NG": "NG=F",
    "HG": "HG=F",
    "PL": "PL=F",
    "BZ": "BZ=F",
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "PLATINUM": "PL=F",
    "COPPER": "HG=F",
    "OIL": "CL=F",
    "WTI": "CL=F",
    "USOIL": "CL=F",
    "BRENT": "BZ=F",
    "UKOIL": "BZ=F",
    "NATGAS": "NG=F",
    "NGAS": "NG=F",
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    # FX majors. Yahoo publishes USD-base pairs as `<PAIR>=X` and the dollar-
    # quoted yen pair as the bare `JPY=X`.
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "AUDUSD": "AUDUSD=X",
    "NZDUSD": "NZDUSD=X",
    "USDCAD": "USDCAD=X",
    "USDCHF": "USDCHF=X",
    "EURGBP": "EURGBP=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    "EURCHF": "EURCHF=X",
    "EURAUD": "EURAUD=X",
    "GBPCHF": "GBPCHF=X",
    "AUDJPY": "AUDJPY=X",
    "AUDNZD": "AUDNZD=X",
    "CADJPY": "CADJPY=X",
    "NZDJPY": "NZDJPY=X",
}

# Symbols with no true Yahoo equivalent, served by a *different instrument*
# that tracks it. `XAUUSD=X` and `XAGUSD=X` both 404 — Yahoo has no spot metal
# feed — so spot gold/silver fall back to the front-month future. Futures carry
# a basis over spot (financing plus storage, tens of dollars on gold), so these
# prices will NOT match an MT5 spot fill. The gap is surfaced to the caller as
# a limitation rather than silently absorbed, because a wrong price that looks
# right is the most expensive failure mode this module has.
SYMBOL_PROXIES = {
    "XAUUSD": (
        "GC=F",
        "Spot gold is unavailable; showing front-month COMEX gold futures "
        "(GC=F), which trades at a basis to spot.",
    ),
    "XAGUSD": (
        "SI=F",
        "Spot silver is unavailable; showing front-month COMEX silver futures "
        "(SI=F), which trades at a basis to spot.",
    ),
}


def resolve_provider_symbol(normalized: str) -> tuple[str, str | None]:
    """Map a user symbol to its provider symbol plus any proxy caveat.

    Returns ``(provider_symbol, proxy_note)`` where ``proxy_note`` is None when
    the provider serves the actual instrument requested.
    """
    proxy = SYMBOL_PROXIES.get(normalized)
    if proxy is not None:
        return proxy[0], proxy[1]
    return SYMBOL_ALIASES.get(normalized, normalized), None


ASSET_FX = "fx"
ASSET_INDEX = "index"
ASSET_COMMODITY = "commodity"
ASSET_CRYPTO = "crypto"
ASSET_EQUITY = "equity"

# Front-month roots by class, keyed on the Yahoo provider symbol so a rename of
# the user-facing alias cannot silently reclassify an instrument.
_INDEX_ROOTS = {"ES", "MES", "NQ", "MNQ", "YM", "RTY"}
_COMMODITY_ROOTS = {"GC", "SI", "CL", "BZ", "NG", "HG", "PL", "PA", "ZC", "ZW", "ZS"}


def asset_class_for(symbol: str) -> str:
    """Classify a user symbol for grouping and display.

    Purely descriptive — the bias engine is asset-class agnostic by design
    (ATR-normalization is what makes an ES move comparable to a EURUSD move).
    This exists so the UI can group a cross-asset desk sensibly.
    """
    normalized = _normalize_symbol(symbol)
    provider_symbol, _ = resolve_provider_symbol(normalized)

    if provider_symbol.startswith("^"):
        return ASSET_INDEX
    if provider_symbol.endswith("-USD"):
        return ASSET_CRYPTO
    if provider_symbol.endswith("=X"):
        return ASSET_FX
    if provider_symbol.endswith("=F"):
        root = provider_symbol[:-2]
        if root in _INDEX_ROOTS:
            return ASSET_INDEX
        if root in _COMMODITY_ROOTS:
            return ASSET_COMMODITY
        return ASSET_COMMODITY
    # Spot metals resolve to a futures proxy but are conceptually commodities.
    if normalized in SYMBOL_PROXIES:
        return ASSET_COMMODITY
    return ASSET_EQUITY


def price_basis_for(provider_symbol: str) -> str:
    """Classify what the upstream number represents for this symbol.

    Yahoo's `=X` FX/metal series are aggregated indicative mids with no book
    behind them; everything else is a delayed last-trade print.
    """
    if provider_symbol.endswith("=X"):
        return PRICE_BASIS_INDICATIVE_MID
    return PRICE_BASIS_LAST_TRADE


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


def fetch_market_context(symbol: str) -> MarketContext:
    """Fetch hourly bars and calculate an inspectable, non-predictive regime view.

    The labels deliberately describe observed participation, direction, and
    volatility. They are not trade signals and the response exposes every
    underlying indicator needed to audit the classification.
    """
    normalized = _normalize_symbol(symbol)
    now = time.monotonic()
    with _cache_lock:
        cached = _context_cache.get(normalized)
        if cached and now - cached[1] < CONTEXT_CACHE_TTL_SECONDS:
            return cached[0]
    try:
        context = _fetch_market_context_from_provider(normalized)
    except (OSError, TimeoutError, ValueError) as exc:
        with _cache_lock:
            cached = _context_cache.get(normalized)
            if cached and now - cached[1] < CONTEXT_STALE_MAX_SECONDS:
                logger.warning(
                    "context provider failed for %s; serving stale cache: %s",
                    normalized,
                    exc,
                )
                return replace(cached[0], stale=True)
        raise
    with _cache_lock:
        _context_cache[normalized] = (context, time.monotonic())
    return context


def _fetch_market_context_from_provider(normalized: str) -> MarketContext:
    provider_symbol, proxy_note = resolve_provider_symbol(normalized)
    interval = "1h"
    lookback = "1mo"
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{quote(provider_symbol)}?range={lookback}&interval={interval}"
    )
    request = Request(
        url,
        headers={"User-Agent": "QuantLabsMarketData/0.1 (+local-first trading journal)"},
    )
    with urlopen(request, timeout=8) as response:
        raw = response.read(2_000_000)
    payload = json.loads(raw)
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not isinstance(result, dict):
        raise ValueError(f"No market history returned for {normalized}.")
    timestamps = result.get("timestamp") or []
    quote_rows = (result.get("indicators", {}).get("quote") or [{}])[0]
    bars = _bars_from_chart(timestamps, quote_rows)
    if len(bars) < 20:
        raise ValueError(f"Not enough market history returned for {normalized}.")
    return analyze_market_bars(
        symbol=normalized,
        provider_symbol=provider_symbol,
        bars=bars,
        interval=interval,
        lookback=lookback,
        proxy_note=proxy_note,
    )


def analyze_market_bars(
    *,
    symbol: str,
    provider_symbol: str,
    bars: list[PriceBar],
    interval: str = "1h",
    lookback: str = "1mo",
    proxy_note: str | None = None,
) -> MarketContext:
    closes = [bar.close for bar in bars]
    rsi = _rsi(closes, 14)
    atrs = _atr_series(bars, 14)
    latest_atr = atrs[-1] if atrs else None
    atr_percent = (latest_atr / closes[-1] * 100) if latest_atr else None
    bb_width = _bollinger_width(closes, 20)
    volume_values = [bar.volume for bar in bars if bar.volume is not None and bar.volume > 0]
    volume_percentile = (
        _percentile_rank(volume_values[:-1], volume_values[-1])
        if len(volume_values) >= 10
        else None
    )
    recent = closes[-CHANGE_WINDOW_BARS:]
    path = sum(abs(recent[index] - recent[index - 1]) for index in range(1, len(recent)))
    efficiency = abs(recent[-1] - recent[0]) / path if path else 0.0
    change_percent = ((closes[-1] / recent[0]) - 1) * 100 if recent[0] else 0.0

    if volume_percentile is None:
        flow = "unavailable"
    elif volume_percentile < 30:
        flow = "thin"
    elif volume_percentile > 70:
        flow = "crowded"
    else:
        flow = "healthy"

    direction = "up" if change_percent > 0.15 else "down" if change_percent < -0.15 else "flat"
    if direction == "flat":
        bearing = "flat"
    elif efficiency < 0.3:
        bearing = f"choppy {direction}"
    else:
        bearing = f"trending {direction}"

    atr_percentile = _percentile_rank(atrs[:-1], atrs[-1]) if len(atrs) >= 10 else None
    if atr_percentile is None:
        pulse = "unavailable"
    elif atr_percentile < 25:
        pulse = "quiet"
    elif atr_percentile > 80:
        pulse = "wild"
    else:
        pulse = "tradable"

    basis = price_basis_for(provider_symbol)
    limitations: list[str] = [
        "Yahoo chart data is delayed and may be incomplete.",
        "Labels describe recent bars; they are not forecasts or trade signals.",
    ]
    if proxy_note:
        limitations.append(proxy_note)
    if basis == PRICE_BASIS_INDICATIVE_MID:
        limitations.append(
            "Prices are indicative mids with no bid/ask; a live fill will differ by "
            "at least half the spread."
        )
    if volume_percentile is None:
        limitations.append("Reliable volume was unavailable for this instrument.")
    if len(bars) < 100:
        limitations.append("The sample is smaller than 100 hourly bars.")
    data_coverage = min(1.0, len(bars) / 120)
    indicator_coverage = (
        sum(value is not None for value in [rsi, atr_percent, bb_width, volume_percentile]) / 4
    )
    confidence = round((data_coverage * 0.55) + (indicator_coverage * 0.45), 2)
    return MarketContext(
        symbol=symbol,
        provider_symbol=provider_symbol,
        provider="yahoo_chart",
        interval=interval,
        lookback=lookback,
        as_of=bars[-1].time,
        delayed=True,
        stale=False,
        sample_size=len(bars),
        last_price=round(closes[-1], 6),
        change_percent=round(change_percent, 3),
        rsi_14=round(rsi, 2) if rsi is not None else None,
        atr_percent=round(atr_percent, 3) if atr_percent is not None else None,
        bollinger_width_percent=round(bb_width, 3) if bb_width is not None else None,
        volume_percentile=round(volume_percentile, 1) if volume_percentile is not None else None,
        trend_efficiency=round(efficiency, 3),
        flow=flow,
        bearing=bearing,
        pulse=pulse,
        confidence=confidence,
        limitations=tuple(limitations),
        price_basis=basis,
        proxy_note=proxy_note,
    )


def _fetch_from_provider(symbol: str) -> MarketQuote:
    normalized = _normalize_symbol(symbol)
    provider_symbol, proxy_note = resolve_provider_symbol(normalized)
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

    # Yahoo's chart `meta` occasionally carries bid/ask for listed equities and
    # never for the `=X` FX series. Take them only when genuinely present; a
    # missing book stays None rather than being back-filled from last_price.
    bid = _decimal(meta.get("bid"))
    ask = _decimal(meta.get("ask"))
    if bid is not None and ask is not None and (bid <= 0 or ask <= 0 or ask < bid):
        bid = ask = None

    return MarketQuote(
        symbol=normalized,
        provider_symbol=provider_symbol,
        provider="yahoo_chart",
        last_price=last_price,
        previous_close=_decimal(meta.get("previousClose")),
        currency=meta.get("currency"),
        market_time=market_time,
        delayed=True,
        bid=bid,
        ask=ask,
        price_basis=price_basis_for(provider_symbol),
        proxy_note=proxy_note,
    )


def _bars_from_chart(timestamps: list[object], values: dict) -> list[PriceBar]:
    opens = values.get("open") or []
    highs = values.get("high") or []
    lows = values.get("low") or []
    closes = values.get("close") or []
    volumes = values.get("volume") or []
    bars: list[PriceBar] = []
    for index, timestamp in enumerate(timestamps):
        open_value = opens[index] if index < len(opens) else None
        high_value = highs[index] if index < len(highs) else None
        low_value = lows[index] if index < len(lows) else None
        close_value = closes[index] if index < len(closes) else None
        if (
            not isinstance(timestamp, int | float)
            or not isinstance(open_value, int | float)
            or not isinstance(high_value, int | float)
            or not isinstance(low_value, int | float)
            or not isinstance(close_value, int | float)
        ):
            continue
        volume = volumes[index] if index < len(volumes) else None
        bars.append(
            PriceBar(
                time=datetime.fromtimestamp(timestamp, tz=UTC),
                open=float(open_value),
                high=float(high_value),
                low=float(low_value),
                close=float(close_value),
                volume=float(volume) if isinstance(volume, int | float) else None,
            )
        )
    return bars


def _rsi(closes: list[float], period: int) -> float | None:
    if len(closes) <= period:
        return None
    changes = [closes[index] - closes[index - 1] for index in range(1, len(closes))]
    recent = changes[-period:]
    avg_gain = sum(max(change, 0) for change in recent) / period
    avg_loss = sum(max(-change, 0) for change in recent) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    relative_strength = avg_gain / avg_loss
    return 100 - (100 / (1 + relative_strength))


def _atr_series(bars: list[PriceBar], period: int) -> list[float]:
    if len(bars) <= period:
        return []
    true_ranges: list[float] = []
    for index, bar in enumerate(bars):
        previous_close = bars[index - 1].close if index else bar.close
        true_ranges.append(
            max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        )
    return [
        sum(true_ranges[index - period + 1 : index + 1]) / period
        for index in range(period - 1, len(true_ranges))
    ]


def _bollinger_width(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    sample = closes[-period:]
    mean = sum(sample) / period
    if not mean:
        return None
    variance = sum((value - mean) ** 2 for value in sample) / period
    standard_deviation = sqrt(variance)
    return ((4 * standard_deviation) / mean) * 100


def _percentile_rank(history: list[float], value: float) -> float | None:
    clean = [item for item in history if item >= 0]
    if not clean:
        return None
    return sum(item <= value for item in clean) / len(clean) * 100


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace("/", "")


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.0001"))
