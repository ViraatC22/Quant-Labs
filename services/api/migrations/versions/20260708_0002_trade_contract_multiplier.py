"""Add trades.contract_multiplier so P&L can include the contract/point size.

Revision ID: 20260708_0002
Revises: 20260704_0001
Create Date: 2026-07-08

Existing rows default to a multiplier of 1 (correct for equities). Historical
non-equity P&L is not retroactively recomputed here: the pre-migration
multiplier lived only in the untyped metadata blob and those legacy rows were
date-resolution records anyway. New trades compute P&L correctly server-side.
"""

from alembic import op

revision = "20260708_0002"
down_revision = "20260704_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "alter table trades "
        "add column contract_multiplier numeric(18, 6) not null default 1"
    )


def downgrade() -> None:
    op.execute("alter table trades drop column contract_multiplier")
