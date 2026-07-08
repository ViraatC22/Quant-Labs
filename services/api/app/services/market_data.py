from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import quote
from urllib.request import Request, urlopen


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
