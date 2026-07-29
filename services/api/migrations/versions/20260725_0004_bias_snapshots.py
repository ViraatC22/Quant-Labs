"""Macro-desk bias snapshots.

Revision ID: 20260725_0004
Revises: 20260710_0003
Create Date: 2026-07-25

Stores one row per instrument per *change* in the computed macro bias, so the
"For You" briefing can report a genuine transition ("EURUSD moved to bearish")
instead of restating the current reading. Without prior state there is nothing
to compare against, and claiming a change would be unverifiable.

Append-only. The (user_id, symbol, recorded_at desc) index serves the only read
path: "the most recent snapshot for this instrument".
"""

from alembic import op

revision = "20260725_0004"
down_revision = "20260710_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table bias_snapshots (
          id uuid primary key default gen_random_uuid(),
          user_id uuid not null,
          symbol varchar(32) not null,
          direction varchar(16) not null,
          confidence integer not null,
          change_percent numeric(12, 4),
          explanation text not null default '',
          payload jsonb not null default '{}'::jsonb,
          recorded_at timestamptz not null default now()
        );
        """
    )
    op.execute("create index ix_bias_snapshots_user_id on bias_snapshots (user_id);")
    op.execute("create index ix_bias_snapshots_symbol on bias_snapshots (symbol);")
    op.execute(
        "create index ix_bias_snapshots_recorded_at on bias_snapshots (recorded_at);"
    )
    op.execute(
        """
        create index ix_bias_snapshots_user_symbol_time
          on bias_snapshots (user_id, symbol, recorded_at desc);
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists bias_snapshots;")
