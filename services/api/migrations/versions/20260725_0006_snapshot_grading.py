"""Grading columns on bias snapshots.

Revision ID: 20260725_0006
Revises: 20260725_0005
Create Date: 2026-07-25

A verdict is written exactly once, when the snapshot ages into the grading
window: what price subsequently did relative to the call. Persisting it (rather
than regrading transiently) is what makes calibration possible — the desk can
only learn from its record if the record cannot shift under it.

The partial index serves the grading pass ("which snapshots are due?") without
paying for the ever-growing set of already-graded rows.
"""

from alembic import op

revision = "20260725_0006"
down_revision = "20260725_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        alter table bias_snapshots
          add column verdict varchar(16),
          add column graded_at timestamptz,
          add column price_at_grading numeric(18, 6),
          add column move_percent numeric(12, 4);
        """
    )
    op.execute(
        """
        create index ix_bias_snapshots_ungraded
          on bias_snapshots (user_id, recorded_at)
          where verdict is null;
        """
    )


def downgrade() -> None:
    op.execute("drop index if exists ix_bias_snapshots_ungraded;")
    op.execute(
        """
        alter table bias_snapshots
          drop column if exists verdict,
          drop column if exists graded_at,
          drop column if exists price_at_grading,
          drop column if exists move_percent;
        """
    )
