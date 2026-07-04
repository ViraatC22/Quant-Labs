"""Initial Trading Intelligence OS schema.

Revision ID: 20260704_0001
Revises:
Create Date: 2026-07-04
"""

from alembic import op

revision = "20260704_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("create extension if not exists vector")
    op.execute("create extension if not exists pgcrypto")

    op.execute(
        """
        create or replace function set_updated_at()
        returns trigger as $$
        begin
          new.updated_at = now();
          return new;
        end;
        $$ language plpgsql;
        """
    )

    op.execute(
        """
        create table users (
          id uuid primary key default gen_random_uuid(),
          email varchar(320) unique,
          display_name varchar(160),
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );
        """
    )

    op.execute(
        """
        create table source_documents (
          id uuid primary key default gen_random_uuid(),
          user_id uuid not null,
          title varchar(240) not null,
          document_type varchar(80) not null default 'note',
          uri text,
          content_text text,
          metadata jsonb not null default '{}',
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );
        """
    )

    op.execute(
        """
        create table journal_entries (
          id uuid primary key default gen_random_uuid(),
          user_id uuid not null,
          entry_date date not null,
          title varchar(240) not null,
          body text not null,
          emotional_state varchar(120),
          tags jsonb not null default '[]',
          metadata jsonb not null default '{}',
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );
        """
    )

    op.execute(
        """
        create table trades (
          id uuid primary key default gen_random_uuid(),
          user_id uuid not null,
          symbol varchar(32) not null,
          asset_class varchar(64) not null default 'equity',
          side varchar(16) not null,
          entry_time timestamptz not null,
          exit_time timestamptz,
          entry_price numeric(18, 6) not null,
          exit_price numeric(18, 6),
          quantity numeric(18, 6) not null,
          fees numeric(18, 6) not null default 0,
          pnl_amount numeric(18, 6),
          pnl_r numeric(18, 6),
          strategy_version_id uuid,
          setup_id uuid,
          timeframe varchar(32),
          session varchar(80),
          market_regime_id uuid,
          planned_risk_amount numeric(18, 6),
          actual_risk_amount numeric(18, 6),
          rule_adherence_score numeric(5, 2),
          emotional_state_before varchar(120),
          emotional_state_after varchar(120),
          journal_summary text,
          metadata jsonb not null default '{}',
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );
        """
    )

    op.execute(
        """
        create table taxonomy_items (
          id uuid primary key default gen_random_uuid(),
          user_id uuid not null,
          taxonomy_type varchar(80) not null,
          slug varchar(120) not null,
          label varchar(160) not null,
          description text,
          is_core boolean not null default false,
          properties jsonb not null default '{}',
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          unique (user_id, taxonomy_type, slug)
        );
        """
    )

    op.execute(
        """
        create table kg_nodes (
          id uuid primary key default gen_random_uuid(),
          user_id uuid not null,
          node_type varchar(80) not null,
          source_table varchar(120),
          source_id uuid,
          label varchar(240) not null,
          properties jsonb not null default '{}',
          confidence numeric(5, 4),
          created_by varchar(80) not null default 'system',
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );
        """
    )

    op.execute(
        """
        create table kg_edges (
          id uuid primary key default gen_random_uuid(),
          user_id uuid not null,
          edge_type varchar(80) not null,
          from_node_id uuid not null references kg_nodes(id),
          to_node_id uuid not null references kg_nodes(id),
          properties jsonb not null default '{}',
          confidence numeric(5, 4),
          evidence_chunk_ids uuid[] not null default '{}',
          created_by varchar(80) not null default 'system',
          created_at timestamptz not null default now()
        );
        """
    )

    op.execute(
        """
        create table memory_chunks (
          id uuid primary key default gen_random_uuid(),
          user_id uuid not null,
          source_type varchar(80) not null,
          source_id uuid not null,
          chunk_index integer not null,
          text text not null,
          embedding vector(1536),
          metadata jsonb not null default '{}',
          token_count integer,
          created_at timestamptz not null default now()
        );
        """
    )

    op.execute("create index source_documents_user_idx on source_documents(user_id)")
    op.execute("create index journal_entries_user_date_idx on journal_entries(user_id, entry_date)")
    op.execute("create index trades_user_entry_idx on trades(user_id, entry_time desc)")
    op.execute("create index trades_user_symbol_idx on trades(user_id, symbol)")
    op.execute(
        "create index taxonomy_items_user_type_idx on taxonomy_items(user_id, taxonomy_type)"
    )
    op.execute("create index kg_nodes_user_type_idx on kg_nodes(user_id, node_type)")
    op.execute("create index kg_edges_user_type_idx on kg_edges(user_id, edge_type)")
    op.execute("create index kg_edges_from_idx on kg_edges(from_node_id)")
    op.execute("create index kg_edges_to_idx on kg_edges(to_node_id)")
    op.execute(
        "create index memory_chunks_user_source_idx "
        "on memory_chunks(user_id, source_type, source_id)"
    )
    op.execute(
        "create index memory_chunks_embedding_hnsw_idx "
        "on memory_chunks using hnsw (embedding vector_cosine_ops)"
    )

    for table_name in [
        "users",
        "source_documents",
        "journal_entries",
        "trades",
        "taxonomy_items",
        "kg_nodes",
    ]:
        op.execute(
            f"""
            create trigger {table_name}_set_updated_at
            before update on {table_name}
            for each row execute function set_updated_at();
            """
        )


def downgrade() -> None:
    for table_name in [
        "users",
        "source_documents",
        "journal_entries",
        "trades",
        "taxonomy_items",
        "kg_nodes",
    ]:
        op.execute(f"drop trigger if exists {table_name}_set_updated_at on {table_name}")

    op.execute("drop table if exists memory_chunks")
    op.execute("drop table if exists kg_edges")
    op.execute("drop table if exists kg_nodes")
    op.execute("drop table if exists taxonomy_items")
    op.execute("drop table if exists trades")
    op.execute("drop table if exists journal_entries")
    op.execute("drop table if exists source_documents")
    op.execute("drop table if exists users")
    op.execute("drop function if exists set_updated_at")
