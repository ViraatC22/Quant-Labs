"""Bias snapshot and change-detection tests.

The property under test: "bias changed" may only ever be reported when a prior
snapshot exists and materially differs. A first reading is not a transition,
and confidence jitter from a rolling bar is not news.
"""

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.desk.bias import BiasSignal, InstrumentBias
from app.services.desk.snapshots import (
    CONFIDENCE_CHANGE_THRESHOLD,
    latest_snapshot,
    recent_changes,
    record_all,
    record_bias,
)


@pytest.fixture()
def db():
    session: Session = SessionLocal()
    yield session
    session.close()


def _bias(
    symbol: str = "EURUSD",
    direction: str = "bearish",
    confidence: int = 45,
    change_percent: float = -0.14,
) -> InstrumentBias:
    return InstrumentBias(
        symbol=symbol,
        direction=direction,
        confidence=confidence,
        strength=0.5,
        agreement=0.9,
        coverage=0.9,
        last_price=1.1375,
        change_percent=change_percent,
        signals=(BiasSignal("Trend", -0.4, 0.4, "test detail"),),
        explanation=f"{symbol} test reading",
        explanation_mode="derived",
        as_of="2026-07-25T00:00:00+00:00",
        provider="yahoo_chart",
        price_basis="indicative_mid",
        sample_size=500,
        delayed=True,
        stale=False,
        proxy_note=None,
        limitations=("test",),
    )


def test_first_reading_is_stored_but_not_reported_as_a_change(db) -> None:
    user_id = uuid4()
    change = record_bias(db, user_id=user_id, bias=_bias())
    db.commit()

    # Stored: the next comparison has something to compare against.
    assert latest_snapshot(db, user_id=user_id, symbol="EURUSD") is not None
    # Not a change: there was no prior state, so no transition happened.
    assert change is None


def test_direction_flip_is_recorded_and_reported(db) -> None:
    user_id = uuid4()
    record_bias(db, user_id=user_id, bias=_bias(direction="bearish", confidence=45))
    db.commit()

    change = record_bias(db, user_id=user_id, bias=_bias(direction="bullish", confidence=48))
    db.commit()

    assert change is not None
    assert change.direction_changed is True
    assert change.previous_direction == "bearish"
    assert "moved from bearish to bullish" in change.headline


def test_unchanged_reading_is_neither_stored_nor_reported(db) -> None:
    user_id = uuid4()
    record_bias(db, user_id=user_id, bias=_bias(confidence=45))
    db.commit()
    first = latest_snapshot(db, user_id=user_id, symbol="EURUSD")

    # Same direction, confidence drift below the threshold: noise.
    change = record_bias(
        db,
        user_id=user_id,
        bias=_bias(confidence=45 + CONFIDENCE_CHANGE_THRESHOLD - 1),
    )
    db.commit()

    assert change is None
    assert latest_snapshot(db, user_id=user_id, symbol="EURUSD").id == first.id


def test_confidence_jump_at_threshold_is_a_change(db) -> None:
    user_id = uuid4()
    record_bias(db, user_id=user_id, bias=_bias(confidence=40))
    db.commit()

    change = record_bias(
        db, user_id=user_id, bias=_bias(confidence=40 + CONFIDENCE_CHANGE_THRESHOLD)
    )
    db.commit()

    assert change is not None
    assert change.direction_changed is False
    assert "conviction rose" in change.headline


def test_changes_are_scoped_per_user(db) -> None:
    user_a, user_b = uuid4(), uuid4()
    record_bias(db, user_id=user_a, bias=_bias(direction="bearish"))
    db.commit()

    # User B has no prior snapshot; the same reading is a first for them.
    change = record_bias(db, user_id=user_b, bias=_bias(direction="bullish"))
    db.commit()
    assert change is None


def test_record_all_returns_only_genuine_transitions(db) -> None:
    user_id = uuid4()
    record_all(
        db,
        user_id=user_id,
        biases=[_bias("EURUSD", "bearish"), _bias("USDJPY", "neutral", 53)],
    )

    changes = record_all(
        db,
        user_id=user_id,
        biases=[
            _bias("EURUSD", "bullish"),  # flip -> change
            _bias("USDJPY", "neutral", 53),  # identical -> no change
            _bias("XAUUSD", "neutral", 67),  # first reading -> no change
        ],
    )

    assert [change.symbol for change in changes] == ["EURUSD"]


def test_recent_changes_returns_newest_first(db) -> None:
    user_id = uuid4()
    record_all(db, user_id=user_id, biases=[_bias("EURUSD")])
    record_all(db, user_id=user_id, biases=[_bias("EURUSD", "bullish")])

    rows = recent_changes(db, user_id=user_id)
    assert len(rows) == 2
    assert rows[0].recorded_at >= rows[1].recorded_at
    # Provenance travels with the snapshot.
    assert rows[0].payload["price_basis"] == "indicative_mid"
