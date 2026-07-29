"""Calibration tests: the learning loop must be incapable of fooling itself.

Covered: the evidence gate (no adjustment under MIN_SAMPLE), shrinkage
direction and magnitude, the neutral-bucket exemption, the luck baseline,
grade-once persistence, and the feedback guard (snapshots store raw
confidence even when a calibrated value is displayed).
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.domain import BiasSnapshot
from app.services.desk.calibration import (
    BUCKET_DIRECTIONAL_HIGH,
    BUCKET_DIRECTIONAL_LOW,
    BUCKET_NEUTRAL,
    MIN_SAMPLE,
    bucket_for,
    calibrate,
    load_stats,
)
from app.services.desk.reports import (
    MIN_GRADE_AGE,
    graded_calls_for_report,
    persist_due_grades,
)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


@pytest.fixture()
def db():
    session: Session = SessionLocal()
    yield session
    session.close()


def _snapshot(
    user_id,
    *,
    direction: str = "bullish",
    confidence: int = 50,
    verdict: str | None = None,
    last_price: float = 1.1,
    age: timedelta = MIN_GRADE_AGE + timedelta(hours=2),
) -> BiasSnapshot:
    return BiasSnapshot(
        user_id=user_id,
        symbol="EURUSD",
        direction=direction,
        confidence=confidence,
        explanation="test",
        payload={"last_price": last_price},
        recorded_at=NOW - age,
        verdict=verdict,
        graded_at=NOW if verdict else None,
    )


def _seed_graded(db, user_id, *, count: int, correct: int, confidence: int = 50) -> None:
    for index in range(count):
        db.add(
            _snapshot(
                user_id,
                confidence=confidence,
                verdict="correct" if index < correct else "incorrect",
            )
        )
    db.commit()


def test_buckets_split_by_direction_and_confidence() -> None:
    assert bucket_for("neutral", 60) == BUCKET_NEUTRAL
    assert bucket_for("bullish", 44) == BUCKET_DIRECTIONAL_LOW
    assert bucket_for("bearish", 45) == BUCKET_DIRECTIONAL_HIGH


def test_no_adjustment_below_the_evidence_floor(db) -> None:
    user_id = uuid4()
    _seed_graded(db, user_id, count=MIN_SAMPLE - 1, correct=MIN_SAMPLE - 1)

    stats = load_stats(db, user_id=user_id)
    result = calibrate("bullish", 50, stats)

    # A perfect but tiny record adjusts nothing.
    assert result.applied is False
    assert result.calibrated == 50
    assert f"{MIN_SAMPLE - 1}/{MIN_SAMPLE}" in result.note


def test_poor_record_pulls_confidence_down(db) -> None:
    user_id = uuid4()
    # 40 graded calls, 30% hit rate, raw confidence 60.
    _seed_graded(db, user_id, count=40, correct=12, confidence=60)

    stats = load_stats(db, user_id=user_id)
    result = calibrate("bullish", 60, stats)

    assert result.applied is True
    assert result.calibrated < 60
    # Shrinkage check: weight 40/60, empirical 0.30*75=22.5 → 2/3*22.5 + 1/3*60 = 35.
    assert result.calibrated == 35


def test_strong_record_pulls_confidence_up(db) -> None:
    user_id = uuid4()
    # 40 graded calls at 90% — raw 50 should rise, still capped at 75.
    _seed_graded(db, user_id, count=40, correct=36, confidence=60)

    stats = load_stats(db, user_id=user_id)
    result = calibrate("bullish", 50, stats)
    assert result.calibrated > 50
    assert result.calibrated <= 75


def test_neutral_calls_are_never_calibrated(db) -> None:
    user_id = uuid4()
    _seed_graded(db, user_id, count=40, correct=10)
    stats = load_stats(db, user_id=user_id)

    result = calibrate("neutral", 60, stats)
    assert result.applied is False
    assert result.calibrated == 60
    assert "not calibrated" in result.note


def test_luck_baseline_is_half_the_decisive_share(db) -> None:
    user_id = uuid4()
    # 10 directional graded: 6 decisive (4 correct + 2 incorrect), 4 flat.
    for verdict in ["correct"] * 4 + ["incorrect"] * 2 + ["flat"] * 4:
        db.add(_snapshot(user_id, verdict=verdict))
    db.commit()

    stats = load_stats(db, user_id=user_id)
    assert stats.decisive_share == pytest.approx(0.6)
    assert stats.luck_baseline == pytest.approx(0.3)


def test_persist_due_grades_writes_each_verdict_exactly_once(db) -> None:
    user_id = uuid4()
    db.add(_snapshot(user_id, last_price=1.10))
    db.commit()

    first = persist_due_grades(
        db, user_id=user_id, now=NOW, price_lookup=lambda s: 1.12
    )
    assert len(first) == 1
    assert first[0].verdict == "correct"
    assert float(first[0].move_percent) == pytest.approx(1.8182, rel=1e-3)

    # A second pass, even with a reversed price, must not regrade.
    second = persist_due_grades(
        db, user_id=user_id, now=NOW, price_lookup=lambda s: 0.90
    )
    assert second == []
    row = db.query(BiasSnapshot).filter_by(user_id=user_id).one()
    assert row.verdict == "correct"


def test_aged_out_snapshots_are_closed_as_ungradable(db) -> None:
    user_id = uuid4()
    db.add(_snapshot(user_id, age=timedelta(days=5)))
    db.commit()

    graded = persist_due_grades(
        db, user_id=user_id, now=NOW, price_lookup=lambda s: 1.2
    )
    assert graded[0].verdict == "ungradable"
    # Ungradable rows never enter the calibration record.
    stats = load_stats(db, user_id=user_id)
    assert stats.total_graded == 0


def test_too_recent_snapshots_are_left_alone(db) -> None:
    user_id = uuid4()
    db.add(_snapshot(user_id, age=timedelta(hours=1)))
    db.commit()
    graded = persist_due_grades(
        db, user_id=user_id, now=NOW, price_lookup=lambda s: 1.2
    )
    assert graded == []


def test_graded_calls_for_report_reads_the_persisted_record(db) -> None:
    user_id = uuid4()
    db.add(_snapshot(user_id, last_price=1.10))
    db.commit()
    persist_due_grades(db, user_id=user_id, now=NOW, price_lookup=lambda s: 1.12)

    calls = graded_calls_for_report(db, user_id=user_id, now=NOW)
    assert len(calls) == 1
    assert calls[0].verdict == "correct"
    assert "+1.82%" in calls[0].detail


def test_snapshots_store_raw_confidence_not_calibrated(db) -> None:
    """The feedback guard, end to end at the endpoint layer.

    /briefing records snapshots from the raw engine output; /macro displays
    calibrated values. If snapshots ever stored the calibrated number, the
    system would learn from its own adjustments.
    """
    from fastapi.testclient import TestClient

    from app.api.v1 import desk as desk_api
    from app.main import create_app
    from app.services.market_data import PriceBar, analyze_market_bars

    def fake_context(symbol: str):
        start = datetime(2026, 7, 1, tzinfo=UTC)
        price, bars = 100.0, []
        for index in range(80):
            price += 0.5
            bars.append(
                PriceBar(
                    time=start + timedelta(hours=index),
                    open=price - 0.2,
                    high=price + 0.6,
                    low=price - 0.6,
                    close=price,
                    volume=1000,
                )
            )
        return analyze_market_bars(symbol=symbol, provider_symbol=symbol, bars=bars)

    client = TestClient(create_app())
    import unittest.mock

    with unittest.mock.patch.object(desk_api, "fetch_market_context", fake_context):
        # Seed a poor graded record so calibration adjusts downward.
        card = client.get("/api/v1/desk/macro", params={"symbols": "eurusd"}).json()[
            "instruments"
        ][0]
        raw = card["raw_confidence"]

        from app.core.security import DEMO_USER_ID

        _seed_graded(db, DEMO_USER_ID, count=40, correct=4, confidence=raw)

        card = client.get("/api/v1/desk/macro", params={"symbols": "eurusd"}).json()[
            "instruments"
        ][0]
        assert card["calibration_applied"] is True
        assert card["confidence"] < card["raw_confidence"]

        # Now record a snapshot via the briefing: it must carry the RAW value.
        client.get("/api/v1/desk/briefing", params={"symbols": "eurusd"})
        snapshot = (
            db.query(BiasSnapshot)
            .filter_by(user_id=DEMO_USER_ID, symbol="EURUSD")
            .order_by(BiasSnapshot.recorded_at.desc())
            .first()
        )
        assert snapshot is not None
        assert snapshot.confidence == card["raw_confidence"]
        assert snapshot.confidence != card["confidence"]
