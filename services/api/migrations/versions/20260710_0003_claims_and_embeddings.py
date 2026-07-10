"""Claims layer, real embeddings, entity-resolution embeddings, graph uniqueness.

Revision ID: 20260710_0003
Revises: 20260708_0002
Create Date: 2026-07-10

Lattice merge, Phases L-1/L-2/L-4:
- Re-dimension the vector columns from 1536 to the configured embedding size
  (default 768, nomic-embed-text). No embeddings were ever written (the column
  was always NULL), so this is a safe re-type + HNSW rebuild.
- Add kg_nodes.label_embedding for embedding-similarity entity resolution.
- Unique indexes on concept nodes and edge triples (idempotent pipeline writes).
- claims / claim_evidence / claim_conflicts tables.

EMBEDDING_DIM here is fixed at migration-authoring time. If you change the
runtime EMBEDDING_DIM, add a follow-up migration re-typing these columns to
match, or the pgvector column and the vectors you write will disagree.
"""

from alembic import op

revision = "20260710_0003"
down_revision = "20260708_0002"
branch_labels = None
depends_on = None

EMBEDDING_DIM = 768


def upgrade() -> None:
    # --- re-dimension existing vector column (was always NULL) --------------
    op.execute("drop index if exists memory_chunks_embedding_hnsw_idx")
    op.execute(
        f"alter table memory_chunks "
        f"alter column embedding type vector({EMBEDDING_DIM}) using null::vector({EMBEDDING_DIM})"
    )
    op.execute(
        "create index memory_chunks_embedding_hnsw_idx "
        "on memory_chunks using hnsw (embedding vector_cosine_ops)"
    )

    # --- entity-resolution embedding on graph nodes ------------------------
    op.execute(f"alter table kg_nodes add column label_embedding vector({EMBEDDING_DIM})")

    # --- idempotent-write uniqueness (Lattice L12, v3 A4) ------------------
    op.execute(
        "create unique index kg_nodes_concept_unique "
        "on kg_nodes(user_id, node_type, label) where source_id is null"
    )
    op.execute(
        "create unique index kg_edges_triple_unique "
        "on kg_edges(user_id, edge_type, from_node_id, to_node_id)"
    )

    # --- claims layer ------------------------------------------------------
    op.execute(
        f"""
        create table claims (
          id uuid primary key default gen_random_uuid(),
          user_id uuid not null,
          workspace_id uuid,
          subject_node_id uuid not null references kg_nodes(id),
          predicate varchar(120) not null,
          object_node_id uuid references kg_nodes(id),
          object_literal text,
          statement_text text not null,
          embedding vector({EMBEDDING_DIM}),
          polarity varchar(16) not null default 'neutral',
          confidence numeric(5, 4),
          created_by varchar(80) not null default 'claim_extraction',
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );
        """
    )
    op.execute(
        """
        create table claim_evidence (
          id uuid primary key default gen_random_uuid(),
          claim_id uuid not null references claims(id),
          source_document_id uuid not null,
          chunk_id uuid,
          stance varchar(16) not null default 'supports',
          quote text,
          asserted_at timestamptz not null default now(),
          created_at timestamptz not null default now()
        );
        """
    )
    op.execute(
        """
        create table claim_conflicts (
          id uuid primary key default gen_random_uuid(),
          user_id uuid not null,
          claim_a_id uuid not null references claims(id),
          claim_b_id uuid not null references claims(id),
          detected_at timestamptz not null default now(),
          status varchar(16) not null default 'open',
          resolution_note text
        );
        """
    )

    op.execute("create index claims_user_subject_idx on claims(user_id, subject_node_id)")
    op.execute(
        "create unique index claims_natural_unique "
        "on claims(user_id, subject_node_id, predicate, object_literal, polarity)"
    )
    op.execute("create index claim_evidence_claim_idx on claim_evidence(claim_id)")
    op.execute("create index claim_conflicts_user_status_idx on claim_conflicts(user_id, status)")
    op.execute(
        "create unique index claim_conflicts_pair_unique "
        "on claim_conflicts(user_id, claim_a_id, claim_b_id)"
    )
    op.execute(
        "create trigger claims_set_updated_at before update on claims "
        "for each row execute function set_updated_at()"
    )

    # --- research conversation history -------------------------------------
    op.execute(
        """
        create table research_conversations (
          id uuid primary key default gen_random_uuid(),
          user_id uuid not null,
          question text not null,
          route varchar(32) not null,
          answer_markdown text not null,
          trust_score numeric(5, 4),
          payload jsonb not null default '{}',
          created_at timestamptz not null default now()
        );
        """
    )
    op.execute(
        "create index research_conversations_user_idx "
        "on research_conversations(user_id, created_at desc)"
    )


def downgrade() -> None:
    op.execute("drop table if exists research_conversations")
    op.execute("drop trigger if exists claims_set_updated_at on claims")
    op.execute("drop table if exists claim_conflicts")
    op.execute("drop table if exists claim_evidence")
    op.execute("drop table if exists claims")
    op.execute("drop index if exists kg_edges_triple_unique")
    op.execute("drop index if exists kg_nodes_concept_unique")
    op.execute("alter table kg_nodes drop column if exists label_embedding")
    op.execute("drop index if exists memory_chunks_embedding_hnsw_idx")
    op.execute("alter table memory_chunks alter column embedding type vector(1536) using null")
    op.execute(
        "create index memory_chunks_embedding_hnsw_idx "
        "on memory_chunks using hnsw (embedding vector_cosine_ops)"
    )
