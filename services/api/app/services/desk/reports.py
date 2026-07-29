"""Daily pre-market report: composition and verifiable call grading.

Everything in a report is assembled from values the desk already computed —
bias cards, calendar events, currency strength — plus a **grading section**
that scores earlier directional calls against what price subsequently did.

The grading is the part that must not cheat, so its rules are explicit:

* A call is gradable only when its snapshot stored ``last_price`` at call time
  AND enough time has passed (``MIN_GRADE_AGE``). Anything else is reported as
  ungradable with the reason, never guessed.
* "Correct" means price moved at least ``FLAT_BAND_PERCENT`` in the called
  direction since the call; the mirror move is "incorrect"; less than the band
  either way is "flat". Neutral calls are correct when price stayed inside the
  band.
* The report never grades itself later — it stores the verdicts computed at
  generation time, so the archive is a record, not a rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.domain import BiasSnapshot, DeskReport
from app.services.desk.bias import NEUTRAL, InstrumentBias
from app.services.desk.calendar import CalendarEvent
from app.services.desk.sessions import SessionState
from app.services.desk.strength import CurrencyStrength

logger = get_logger("app.desk.reports")

# A call younger than this has not had time to be right or wrong.
MIN_GRADE_AGE = timedelta(hours=8)
# Ignore calls older than this — grading a week-old snapshot against today's
# price says nothing about the call.
MAX_GRADE_AGE = timedelta(hours=48)
# Moves inside this band are "flat" rather than a verdict either way.
FLAT_BAND_PERCENT = 0.10

CORRECT = "correct"
INCORRECT = "incorrect"
FLAT = "flat"
UNGRADABLE = "ungradable"


@dataclass(frozen=True)
class GradedCall:
    symbol: str
    direction: str
    confidence: int
    called_at: str
    verdict: str
    detail: str


def grade_snapshot(
    snapshot: BiasSnapshot, current_price: float | None, now: datetime
) -> GradedCall:
    """Grade one stored call against the price now. Pure; fully testable."""
    recorded = snapshot.recorded_at
    if recorded.tzinfo is None:
        recorded = recorded.replace(tzinfo=UTC)
    age = now - recorded

    def result(verdict: str, detail: str) -> GradedCall:
        return GradedCall(
            symbol=snapshot.symbol,
            direction=snapshot.direction,
            confidence=snapshot.confidence,
            called_at=recorded.isoformat(),
            verdict=verdict,
            detail=detail,
        )

    then_price = (snapshot.payload or {}).get("last_price")
    if not isinstance(then_price, int | float) or then_price <= 0:
        return result(
            UNGRADABLE, "The snapshot did not record a price at call time."
        )
    if age < MIN_GRADE_AGE:
        return result(
            UNGRADABLE, f"Too recent to grade ({age.total_seconds() / 3600:.0f}h old)."
        )
    if current_price is None or current_price <= 0:
        return result(UNGRADABLE, "No current price is available for comparison.")

    move = (current_price / then_price - 1) * 100
    moved = f"price moved {move:+.2f}% since the call"

    if abs(move) < FLAT_BAND_PERCENT:
        if snapshot.direction == NEUTRAL:
            return result(CORRECT, f"Called ranging and {moved}.")
        return result(FLAT, f"Called {snapshot.direction} but {moved}.")
    realized = "bullish" if move > 0 else "bearish"
    if snapshot.direction == NEUTRAL:
        return result(INCORRECT, f"Called ranging but {moved}.")
    if snapshot.direction == realized:
        return result(CORRECT, f"Called {snapshot.direction} and {moved}.")
    return result(INCORRECT, f"Called {snapshot.direction} but {moved}.")


def persist_due_grades(
    db: Session,
    *,
    user_id: UUID,
    now: datetime,
    price_lookup,
) -> list[BiasSnapshot]:
    """Grade every ungraded snapshot that has aged into the window, once.

    ``price_lookup(symbol) -> float | None`` supplies the current price.
    Verdicts are written permanently — a graded row is never revisited, so the
    calibration record cannot shift after the fact. Snapshots that aged past
    ``MAX_GRADE_AGE`` without a pass running are closed out as ungradable
    rather than graded against a price from the wrong era.

    Returns the rows graded in this pass.
    """
    due = list(
        db.scalars(
            select(BiasSnapshot).where(
                BiasSnapshot.user_id == user_id,
                BiasSnapshot.verdict.is_(None),
                BiasSnapshot.recorded_at <= now - MIN_GRADE_AGE,
            )
        ).all()
    )
    graded: list[BiasSnapshot] = []
    for snapshot in due:
        recorded = snapshot.recorded_at
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=UTC)
        if now - recorded > MAX_GRADE_AGE:
            snapshot.verdict = UNGRADABLE
            snapshot.graded_at = now
            graded.append(snapshot)
            continue

        current = price_lookup(snapshot.symbol)
        call = grade_snapshot(snapshot, current, now)
        snapshot.verdict = call.verdict
        snapshot.graded_at = now
        if current is not None and current > 0:
            snapshot.price_at_grading = Decimal(str(round(current, 6)))
            then_price = (snapshot.payload or {}).get("last_price")
            if isinstance(then_price, int | float) and then_price > 0:
                snapshot.move_percent = Decimal(
                    str(round((current / then_price - 1) * 100, 4))
                )
        graded.append(snapshot)
    if graded:
        db.commit()
        logger.info("graded %d bias snapshots", len(graded))
    return graded


def graded_calls_for_report(
    db: Session, *, user_id: UUID, now: datetime
) -> list[GradedCall]:
    """Recently graded calls, read from the persisted record."""
    rows = db.scalars(
        select(BiasSnapshot)
        .where(
            BiasSnapshot.user_id == user_id,
            BiasSnapshot.verdict.isnot(None),
            BiasSnapshot.graded_at >= now - MAX_GRADE_AGE,
        )
        .order_by(BiasSnapshot.graded_at.desc())
    ).all()
    calls: list[GradedCall] = []
    for row in rows:
        recorded = row.recorded_at
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=UTC)
        move = float(row.move_percent) if row.move_percent is not None else None
        if row.verdict == UNGRADABLE:
            detail = "Could not be graded (no stored price or no current price)."
        elif move is not None:
            detail = f"Called {row.direction}; price moved {move:+.2f}% since the call."
        else:
            detail = f"Called {row.direction}."
        calls.append(
            GradedCall(
                symbol=row.symbol,
                direction=row.direction,
                confidence=row.confidence,
                called_at=recorded.isoformat(),
                verdict=row.verdict or UNGRADABLE,
                detail=detail,
            )
        )
    return calls


def gradable_snapshots(
    db: Session, *, user_id: UUID, now: datetime
) -> list[BiasSnapshot]:
    """Latest snapshot per symbol inside the grading age window."""
    rows = db.scalars(
        select(BiasSnapshot)
        .where(
            BiasSnapshot.user_id == user_id,
            BiasSnapshot.recorded_at >= now - MAX_GRADE_AGE,
            BiasSnapshot.recorded_at <= now - MIN_GRADE_AGE,
        )
        .order_by(BiasSnapshot.recorded_at.desc())
    ).all()
    latest: dict[str, BiasSnapshot] = {}
    for row in rows:
        latest.setdefault(row.symbol, row)
    return list(latest.values())


def _title(report_date: date, biases: list[InstrumentBias], high_impact: int) -> str:
    day = report_date.strftime("%a %d %b")
    if not biases:
        return f"{day} — no market data was available for the desk"
    directional = [b for b in biases if b.direction != NEUTRAL]
    if directional:
        lead = max(directional, key=lambda b: b.confidence)
        stance = f"{lead.symbol} {lead.direction} leads the desk"
    else:
        stance = "the desk reads ranging"
    events = (
        f"{high_impact} high-impact event{'s' if high_impact != 1 else ''} ahead"
        if high_impact
        else "no high-impact events scheduled"
    )
    return f"{day} — {stance}; {events}"


def compose_report(
    *,
    report_date: date,
    biases: list[InstrumentBias],
    graded: list[GradedCall],
    events: list[CalendarEvent],
    strength: list[CurrencyStrength],
    sessions: list[SessionState],
    unavailable: dict[str, str],
) -> tuple[str, dict]:
    """Build the stored payload. Deterministic; no model involvement."""
    todays_events = [
        event
        for event in events
        if event.impact in {"high", "medium"}
        and (
            (event.scheduled_at is not None and event.scheduled_at.date() == report_date)
            or (event.scheduled_at is None and event.date_label
                == report_date.strftime("%m-%d-%Y"))
        )
    ]
    high_impact = sum(1 for event in todays_events if event.impact == "high")

    payload = {
        "graded_calls": [
            {
                "symbol": call.symbol,
                "direction": call.direction,
                "confidence": call.confidence,
                "called_at": call.called_at,
                "verdict": call.verdict,
                "detail": call.detail,
            }
            for call in graded
        ],
        "instruments": [
            {
                "symbol": bias.symbol,
                "direction": bias.direction,
                "confidence": bias.confidence,
                "change_percent": bias.change_percent,
                "explanation": bias.explanation,
                "price_basis": bias.price_basis,
                "proxy_note": bias.proxy_note,
            }
            for bias in sorted(biases, key=lambda b: b.confidence, reverse=True)
        ],
        "events": [
            {
                "title": event.title,
                "currency": event.currency,
                "impact": event.impact,
                "scheduled_at": (
                    event.scheduled_at.isoformat() if event.scheduled_at else None
                ),
                "forecast": event.forecast,
                "previous": event.previous,
            }
            for event in todays_events
        ],
        "strength": [
            {"currency": item.currency, "score": item.score, "pairs": item.pairs}
            for item in strength
        ],
        "sessions": [
            {
                "label": state.label,
                "phase_label": state.phase_label,
                "next_phase_label": state.next_phase_label,
                "countdown": state.countdown,
            }
            for state in sessions
        ],
        "unavailable": unavailable,
        "caveats": sorted(
            {
                *(bias.proxy_note for bias in biases if bias.proxy_note),
                "All prices are delayed and are not executable quotes.",
                "Bias verdicts grade past desk readings; they are not a forecast.",
            }
        ),
        "assets_analyzed": len(biases),
    }
    return _title(report_date, biases, high_impact), payload


def get_or_create_report(
    db: Session,
    *,
    user_id: UUID,
    report_date: date,
    builder,
) -> tuple[DeskReport, bool]:
    """Idempotent per-day fetch-or-generate.

    ``builder`` is called only on a miss and must return ``(title, payload)``.
    Generation is deliberately lazy (first visit of the day) rather than
    scheduled — the worker service is a stub, and a report nobody has looked
    at yet loses nothing by not existing.
    """
    existing = db.scalars(
        select(DeskReport).where(
            DeskReport.user_id == user_id, DeskReport.report_date == report_date
        )
    ).first()
    if existing is not None:
        return existing, False

    title, payload = builder()
    report = DeskReport(
        user_id=user_id, report_date=report_date, title=title, payload=payload
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    logger.info("desk report generated for %s", report_date.isoformat())
    return report, True
