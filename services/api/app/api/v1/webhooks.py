"""Inbound TradingView alert webhook → trade *records*.

Scope, stated once and enforced by construction: an alert here spawns or
closes a **journal record** priced from the alert. Nothing in this module
talks to a broker, and the live-execution path deliberately does not exist.

Security model:

* The endpoint is **disabled until a secret is configured**. An unauthenticated
  webhook that writes trade records would let anyone who can reach the API
  pollute the journal, so absent ``TRADINGVIEW_WEBHOOK_SECRET`` the route
  refuses outright rather than falling back to open access.
* TradingView cannot send custom headers, so the secret travels in the alert
  body and is compared constant-time (``hmac.compare_digest``).
* A wrong secret returns 401 without revealing whether the endpoint is enabled.

Idempotency: TradingView retries failed deliveries. When the alert carries an
``alert_id``, a duplicate delivery is acknowledged with 200 (so TradingView
stops retrying) but creates nothing.

Note the identity caveat: webhooks arrive with no user header, so records land
on the demo user — matching how the single-user local app already works. Real
multi-user auth would need a per-user webhook token; that is a future concern,
not this one.
"""

import hmac
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.trades import _compute_pnl
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.domain import Trade
from app.schemas.webhooks import TradingViewAlert, WebhookResult

logger = get_logger("app.webhooks")

router = APIRouter()

WEBHOOK_SOURCE = "tradingview_webhook"


def _require_valid_secret(supplied: str) -> None:
    configured = settings.tradingview_webhook_secret
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The TradingView webhook is disabled. Set "
                "TRADINGVIEW_WEBHOOK_SECRET to enable it."
            ),
        )
    if not hmac.compare_digest(supplied.encode(), configured.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret.",
        )


# TradingView retries a failed delivery within minutes, so a duplicate can only
# be a recent record. Bounding the scan keeps the JSON-metadata check (which is
# not portably queryable across SQLite and Postgres) from walking the journal.
_DUPLICATE_SCAN_LIMIT = 200


def _find_duplicate(db: Session, user_id: UUID, alert_id: str) -> Trade | None:
    """A recent trade record created or closed by the same alert delivery."""
    recent = db.scalars(
        select(Trade)
        .where(Trade.user_id == user_id)
        .order_by(Trade.entry_time.desc())
        .limit(_DUPLICATE_SCAN_LIMIT)
    )
    for trade in recent:
        meta = trade.trade_metadata or {}
        if meta.get("source") == WEBHOOK_SOURCE and alert_id in (
            meta.get("alert_id"),
            meta.get("exit_alert_id"),
        ):
            return trade
    return None


def _latest_open_trade(db: Session, user_id: UUID, symbol: str) -> Trade | None:
    return db.scalars(
        select(Trade)
        .where(
            Trade.user_id == user_id,
            Trade.symbol == symbol,
            Trade.exit_price.is_(None),
        )
        .order_by(Trade.entry_time.desc())
        .limit(1)
    ).first()


@router.post("/tradingview", response_model=WebhookResult)
def tradingview_alert(
    payload: TradingViewAlert,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> WebhookResult:
    _require_valid_secret(payload.secret)

    symbol = payload.symbol.strip().upper().replace("/", "")
    moment = payload.time or datetime.now(UTC)

    if payload.alert_id:
        duplicate = _find_duplicate(db, user_id, payload.alert_id)
        if duplicate is not None:
            # 200, not an error: a retry acknowledged is a retry stopped.
            logger.info("webhook duplicate alert_id=%s ignored", payload.alert_id)
            return WebhookResult(
                status="duplicate",
                trade_id=str(duplicate.id),
                detail="This alert was already processed; nothing was created.",
            )

    if payload.action == "entry":
        if payload.side is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="An entry alert must include a side (long or short).",
            )
        trade = Trade(
            user_id=user_id,
            symbol=symbol,
            asset_class=payload.asset_class.value,
            side=payload.side,
            entry_time=moment,
            entry_price=payload.price,
            quantity=payload.quantity,
            journal_summary=payload.notes,
            trade_metadata={
                "source": WEBHOOK_SOURCE,
                "alert_id": payload.alert_id,
                "strategy": payload.strategy,
                # The price is whatever the TradingView alert carried — their
                # feed, not ours. Recorded so the journal never conflates the
                # two.
                "price_source": "tradingview_alert",
            },
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)
        logger.info("webhook entry recorded symbol=%s side=%s", symbol, payload.side)
        return WebhookResult(
            status="created",
            trade_id=str(trade.id),
            detail=f"Opened a {payload.side} {symbol} record at {payload.price}.",
        )

    # action == "exit"
    open_trade = _latest_open_trade(db, user_id, symbol)
    if open_trade is None:
        # Acknowledged but explicit: closing what does not exist is a no-op,
        # not an invented round trip.
        return WebhookResult(
            status="no_open_trade",
            detail=f"No open {symbol} record to close; nothing was changed.",
        )

    open_trade.exit_time = moment
    open_trade.exit_price = payload.price
    open_trade.pnl_amount = _compute_pnl(
        side=open_trade.side,
        entry_price=Decimal(str(open_trade.entry_price)),
        exit_price=payload.price,
        quantity=Decimal(str(open_trade.quantity)),
        contract_multiplier=Decimal(str(open_trade.contract_multiplier)),
        fees=Decimal(str(open_trade.fees)),
    )
    meta = dict(open_trade.trade_metadata or {})
    meta["exit_alert_id"] = payload.alert_id
    meta["exit_price_source"] = "tradingview_alert"
    open_trade.trade_metadata = meta
    db.commit()
    db.refresh(open_trade)
    logger.info("webhook exit recorded symbol=%s pnl=%s", symbol, open_trade.pnl_amount)
    return WebhookResult(
        status="closed",
        trade_id=str(open_trade.id),
        detail=(
            f"Closed the {symbol} record at {payload.price}; "
            f"P&L {open_trade.pnl_amount}."
        ),
    )
