"""Recording macro-desk readings so changes can be reported truthfully.

The briefing wants to say "EURUSD moved to bearish". That sentence is only
honest if a previous reading was actually stored and actually differed. This
module is the memory that makes the claim checkable.

Writes are conditional: a snapshot is appended only when the reading is
materially different from the last one for that instrument. Recording every
poll would turn a 60-second refresh into ~1,440 rows per instrument per day and
make "changed" meaningless.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import BiasSnapshot
from app.services.desk.bias import InstrumentBias

# Confidence drift smaller than this is noise from the last bar rolling over,
# not a change worth telling anyone about. Direction flips always count.
CONFIDENCE_CHANGE_THRESHOLD = 10


@dataclass(frozen=True)
class BiasChange:
    symbol: str
    previous_direction: str
    direction: str
    previous_confidence: int
    confidence: int
    explanation: str

    @property
    def direction_changed(self) -> bool:
        return self.previous_direction != self.direction

    @property
    def headline(self) -> str:
        if self.direction_changed:
            return (
                f"{self.symbol} bias moved from {self.previous_direction} to "
                f"{self.direction} ({self.confidence}%)"
            )
        direction_word = "rose" if self.confidence > self.previous_confidence else "fell"
        return (
            f"{self.symbol} {self.direction} conviction {direction_word} from "
            f"{self.previous_confidence}% to {self.confidence}%"
        )


def latest_snapshot(db: Session, *, user_id: UUID, symbol: str) -> BiasSnapshot | None:
    return db.scalars(
        select(BiasSnapshot)
        .where(BiasSnapshot.user_id == user_id, BiasSnapshot.symbol == symbol)
        .order_by(BiasSnapshot.recorded_at.desc())
        .limit(1)
    ).first()


def _is_material(previous: BiasSnapshot, bias: InstrumentBias) -> bool:
    if previous.direction != bias.direction:
        return True
    return abs(previous.confidence - bias.confidence) >= CONFIDENCE_CHANGE_THRESHOLD


def record_bias(
    db: Session, *, user_id: UUID, bias: InstrumentBias
) -> BiasChange | None:
    """Append a snapshot when the reading has materially changed.

    Returns the change if one was recorded, or None when the reading is the
    first for this instrument (nothing to compare against) or is unchanged.
    A first-ever reading is stored but reported as no change — there is no
    prior state, so it is not a transition.
    """
    previous = latest_snapshot(db, user_id=user_id, symbol=bias.symbol)

    if previous is not None and not _is_material(previous, bias):
        return None

    db.add(
        BiasSnapshot(
            user_id=user_id,
            symbol=bias.symbol,
            direction=bias.direction,
            confidence=bias.confidence,
            change_percent=Decimal(str(round(bias.change_percent, 4))),
            explanation=bias.explanation,
            payload={
                # last_price makes the snapshot gradable later: without the
                # price at call time, "was the call right?" is unanswerable
                # and the report must say so instead of guessing.
                "last_price": bias.last_price,
                "price_basis": bias.price_basis,
                "provider": bias.provider,
                "sample_size": bias.sample_size,
                "strength": bias.strength,
                "agreement": bias.agreement,
                "coverage": bias.coverage,
                "proxy_note": bias.proxy_note,
                "explanation_mode": bias.explanation_mode,
            },
        )
    )

    if previous is None:
        return None

    return BiasChange(
        symbol=bias.symbol,
        previous_direction=previous.direction,
        direction=bias.direction,
        previous_confidence=previous.confidence,
        confidence=bias.confidence,
        explanation=bias.explanation,
    )


def record_all(
    db: Session, *, user_id: UUID, biases: list[InstrumentBias]
) -> list[BiasChange]:
    """Record every reading, returning only the genuine transitions."""
    changes = [
        change
        for change in (record_bias(db, user_id=user_id, bias=bias) for bias in biases)
        if change is not None
    ]
    db.commit()
    return changes


def recent_changes(
    db: Session, *, user_id: UUID, limit: int = 20
) -> list[BiasSnapshot]:
    """Most recent recorded snapshots across all instruments, newest first."""
    return list(
        db.scalars(
            select(BiasSnapshot)
            .where(BiasSnapshot.user_id == user_id)
            .order_by(BiasSnapshot.recorded_at.desc())
            .limit(limit)
        ).all()
    )
