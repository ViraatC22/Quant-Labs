"""Daily desk reports.

Revision ID: 20260725_0005
Revises: 20260725_0004
Create Date: 2026-07-25

One stored pre-market report per user per date. Stored rather than regenerated
so the archive shows what the desk actually said that morning. The unique index
on (user_id, report_date) is what makes the generate endpoint idempotent.
"""

from alembic import op

revision = "20260725_0005"
down_revision = "20260725_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table desk_reports (
          id uuid primary key default gen_random_uuid(),
          user_id uuid not null,
          report_date date not null,
          title varchar(300) not null,
          payload jsonb not null default '{}'::jsonb,
          read_at timestamptz,
          created_at timestamptz not null default now()
        );
        """
    )
    op.execute("create index ix_desk_reports_user_id on desk_reports (user_id);")
    op.execute("create index ix_desk_reports_report_date on desk_reports (report_date);")
    op.execute(
        """
        create unique index ux_desk_reports_user_date
          on desk_reports (user_id, report_date);
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists desk_reports;")
