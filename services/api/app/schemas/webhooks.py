"""Payloads for inbound alert webhooks (TradingView-shaped).

The receiver creates and closes **trade records** — journaling. It never
places, routes, or amends an order anywhere, which is why the schema has no
order-type, venue, or account fields to begin with: the capability should be
absent from the contract, not merely unused.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.core.enums import AssetClass


class TradingViewAlert(BaseModel):
    """One alert delivery.

    TradingView webhooks cannot set custom headers, so the shared secret rides
    in the body. ``alert_id`` makes retries idempotent — TradingView re-sends
    on failure, and a duplicate delivery must not spawn a second trade record.
    """

    secret: str = Field(min_length=8, max_length=200)
    action: Literal["entry", "exit"]
    symbol: str = Field(min_length=1, max_length=32)
    price: Decimal = Field(gt=0)
    # Required for entries; ignored on exits (the open trade knows its side).
    side: Literal["long", "short"] | None = None
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    asset_class: AssetClass = AssetClass.forex
    # Alert-supplied identifier for retry deduplication. Optional but strongly
    # recommended in the alert template ({{timenow}} works).
    alert_id: str | None = Field(default=None, max_length=120)
    time: datetime | None = None
    strategy: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class WebhookResult(BaseModel):
    # created | closed | duplicate | no_open_trade
    status: str
    trade_id: str | None = None
    detail: str
