"""Confidence calibration: the desk learns how much to trust its own calls.

The loop: every bias call is snapshotted with its price → graded once against
what price subsequently did → the graded record per bucket adjusts the
confidence *displayed* on future calls toward the measured hit rate.

Three rules keep this measurement instead of self-deception:

* **Raw in, calibrated out.** Snapshots store the raw engine confidence, and
  calibration is applied only at display time. Calibrating on calibrated
  values would be a feedback loop learning from its own output.
* **Shrinkage, and a floor on evidence.** The empirical hit rate is blended
  with the raw confidence weighted by sample size (``n / (n + SHRINKAGE_K)``),
  and below ``MIN_SAMPLE`` graded calls no adjustment happens at all. Twelve
  lucky calls do not get to inflate anything.
* **A luck baseline rides along.** On the same graded windows, a coin-flip
  direction call would have been right ``(share of windows that moved beyond
  the flat band) / 2`` of the time. The stats always report that number next
  to the hit rate, so ordinary chance cannot masquerade as edge.

What this deliberately does NOT do: relearn the signal weights. With a few
correlated graded calls per day, fitting weights would be curve-fitting noise.
The graded record accumulating here is exactly the dataset that would make
weight learning legitimate later, at hundreds of samples.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import BiasSnapshot
from app.services.desk.bias import MAX_CONFIDENCE, NEUTRAL

# Below this many graded calls in a bucket, the raw confidence stands.
MIN_SAMPLE = 20
# Shrinkage constant: at n graded calls the empirical rate carries weight
# n / (n + SHRINKAGE_K). At n=20 that is 50/50 with the raw number.
SHRINKAGE_K = 20
# Raw-confidence boundary between the two directional buckets.
HIGH_CONFIDENCE_SPLIT = 45

BUCKET_DIRECTIONAL_LOW = "directional_low"
BUCKET_DIRECTIONAL_HIGH = "directional_high"
BUCKET_NEUTRAL = "neutral"

# Verdicts that count as observations. `flat` on a directional call is a miss
# that cost nothing, but for "was the call right" it is still not-correct.
_SCORED_VERDICTS = ("correct", "incorrect", "flat")


def bucket_for(direction: str, raw_confidence: int) -> str:
    if direction == NEUTRAL:
        return BUCKET_NEUTRAL
    if raw_confidence >= HIGH_CONFIDENCE_SPLIT:
        return BUCKET_DIRECTIONAL_HIGH
    return BUCKET_DIRECTIONAL_LOW


@dataclass(frozen=True)
class BucketStats:
    bucket: str
    graded: int
    correct: int

    @property
    def hit_rate(self) -> float | None:
        return self.correct / self.graded if self.graded else None


@dataclass(frozen=True)
class CalibrationStats:
    buckets: dict[str, BucketStats]
    #: Share of graded directional windows whose move exceeded the flat band.
    decisive_share: float | None
    #: What a coin-flip direction call would have scored on the same windows.
    luck_baseline: float | None
    total_graded: int


@dataclass(frozen=True)
class CalibratedConfidence:
    raw: int
    calibrated: int
    applied: bool
    bucket: str
    sample: int
    note: str


def load_stats(db: Session, *, user_id: UUID) -> CalibrationStats:
    """Aggregate the graded record. One query; cheap enough per request."""
    rows = db.scalars(
        select(BiasSnapshot).where(
            BiasSnapshot.user_id == user_id,
            BiasSnapshot.verdict.in_(_SCORED_VERDICTS),
        )
    ).all()

    counters: dict[str, dict[str, int]] = {}
    decisive = 0
    directional_windows = 0
    for row in rows:
        bucket = bucket_for(row.direction, row.confidence)
        entry = counters.setdefault(bucket, {"graded": 0, "correct": 0})
        entry["graded"] += 1
        if row.verdict == "correct":
            entry["correct"] += 1
        if row.direction != NEUTRAL:
            directional_windows += 1
            # A window is decisive when price moved beyond the flat band —
            # verdict correct or incorrect rather than flat.
            if row.verdict in ("correct", "incorrect"):
                decisive += 1

    decisive_share = decisive / directional_windows if directional_windows else None
    return CalibrationStats(
        buckets={
            bucket: BucketStats(bucket=bucket, graded=v["graded"], correct=v["correct"])
            for bucket, v in counters.items()
        },
        decisive_share=decisive_share,
        # Coin-flip: half the decisive windows, none of the flat ones.
        luck_baseline=decisive_share / 2 if decisive_share is not None else None,
        total_graded=len(rows),
    )


def calibrate(
    direction: str, raw_confidence: int, stats: CalibrationStats
) -> CalibratedConfidence:
    """Blend raw confidence toward the bucket's measured hit rate.

    The neutral bucket is never adjusted: its "confidence" is conviction in a
    non-move, which the directional hit-rate machinery does not measure.
    """
    bucket = bucket_for(direction, raw_confidence)
    bucket_stats = stats.buckets.get(bucket)
    sample = bucket_stats.graded if bucket_stats else 0

    if direction == NEUTRAL:
        return CalibratedConfidence(
            raw=raw_confidence,
            calibrated=raw_confidence,
            applied=False,
            bucket=bucket,
            sample=sample,
            note="Ranging calls are not calibrated against a directional hit rate.",
        )
    if bucket_stats is None or sample < MIN_SAMPLE:
        return CalibratedConfidence(
            raw=raw_confidence,
            calibrated=raw_confidence,
            applied=False,
            bucket=bucket,
            sample=sample,
            note=(
                f"{sample}/{MIN_SAMPLE} graded calls in this bucket — "
                "not enough evidence to adjust yet."
            ),
        )

    hit_rate = bucket_stats.correct / sample
    weight = sample / (sample + SHRINKAGE_K)
    empirical = hit_rate * MAX_CONFIDENCE
    blended = weight * empirical + (1 - weight) * raw_confidence
    calibrated = max(0, min(MAX_CONFIDENCE, round(blended)))
    return CalibratedConfidence(
        raw=raw_confidence,
        calibrated=calibrated,
        applied=calibrated != raw_confidence,
        bucket=bucket,
        sample=sample,
        note=(
            f"Blended toward a {hit_rate:.0%} hit rate over {sample} graded "
            f"calls (evidence weight {weight:.0%})."
        ),
    )
