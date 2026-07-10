"""Read-only MCP server over the trading memory (Lattice L6).

Exposes the vault/graph/claims/research layer as MCP tools so Claude and other
assistants can answer over the user's own trading memory — with citations and
trust scores, never fabricated. Read-only by design: no tool mutates state.

Runs in-process against the same SQLAlchemy models as the API (single-user,
local SQLite/Postgres). Start it over stdio:

    python -m app.server            # from services/mcp

Requires ``mcp`` (FastMCP). If it isn't installed the module still imports so
tests can introspect the tool registry; ``main()`` raises a clear error.
"""

from __future__ import annotations

import os
import sys
from typing import Any
from uuid import UUID

# Reuse the API's models/services rather than duplicating them.
_API_APP = os.path.join(os.path.dirname(__file__), "..", "..", "api")
sys.path.insert(0, os.path.abspath(_API_APP))

from app.core.security import DEMO_USER_ID  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.models.domain import Claim, ClaimConflict  # noqa: E402
from app.services.research import pipeline, retrieval  # noqa: E402
from sqlalchemy import select  # noqa: E402

USER_ID: UUID = DEMO_USER_ID


def search_memory(query: str, limit: int = 8) -> list[dict[str, Any]]:
    """Hybrid vector+keyword search over saved source chunks."""
    with SessionLocal() as db:
        results = retrieval.search_chunks(db, user_id=USER_ID, query=query, limit=limit)
        return [
            {
                "source_title": r.source_title,
                "text": r.text,
                "score": r.score,
                "chunk_id": str(r.chunk_id),
            }
            for r in results
        ]


def ask_research(question: str) -> dict[str, Any]:
    """Answer a question grounded in the user's memory, with citations and a
    trust score. Refuses (trust 0) when there is no supporting evidence."""
    with SessionLocal() as db:
        answer = pipeline.answer_question(db, user_id=USER_ID, question=question)
        return {
            "question": answer.question,
            "route": answer.route,
            "answer": answer.answer_markdown,
            "trust_score": answer.trust_score,
            "citations": answer.citations,
        }


def get_entity(name: str) -> list[dict[str, Any]]:
    """Find graph entities (strategies, setups, indicators, tags…) by name."""
    with SessionLocal() as db:
        nodes = retrieval.link_entities(db, user_id=USER_ID, query=name, limit=8)
        return [
            {"id": str(n.id), "label": n.label, "node_type": n.node_type, "properties": n.properties}
            for n in nodes
        ]


def get_neighborhood(name: str, depth: int = 1) -> dict[str, Any]:
    """Expand the graph neighborhood around the best-matching entity."""
    with SessionLocal() as db:
        linked = retrieval.link_entities(db, user_id=USER_ID, query=name, limit=1)
        if not linked:
            return {"nodes": [], "edges": []}
        graph = retrieval.neighborhood(
            db, user_id=USER_ID, node_ids=[linked[0].id], depth=depth
        )
        return {
            "root": {"id": str(linked[0].id), "label": linked[0].label},
            "nodes": [{"id": str(n.id), "label": n.label, "node_type": n.node_type} for n in graph.nodes],
            "edges": [
                {"edge_type": e.edge_type, "from": str(e.from_node_id), "to": str(e.to_node_id)}
                for e in graph.edges
            ],
        }


def list_conflicts(status: str = "open") -> list[dict[str, Any]]:
    """List claims where two sources disagree."""
    with SessionLocal() as db:
        conflicts = db.scalars(
            select(ClaimConflict).where(
                ClaimConflict.user_id == USER_ID, ClaimConflict.status == status
            )
        ).all()
        out: list[dict[str, Any]] = []
        for conflict in conflicts:
            claim_a = db.get(Claim, conflict.claim_a_id)
            claim_b = db.get(Claim, conflict.claim_b_id)
            if claim_a and claim_b:
                out.append(
                    {
                        "id": str(conflict.id),
                        "claim_a": claim_a.statement_text,
                        "claim_b": claim_b.statement_text,
                    }
                )
        return out


# The tools exposed by this server, in one registry so both the MCP wiring and
# tests can enumerate them without importing the mcp package.
TOOLS = {
    "search_memory": search_memory,
    "ask_research": ask_research,
    "get_entity": get_entity,
    "get_neighborhood": get_neighborhood,
    "list_conflicts": list_conflicts,
}


def build_server():
    """Register the read-only tools on a FastMCP server."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised only without mcp
        raise RuntimeError(
            "The 'mcp' package is required to run the MCP server. "
            "Install it with: pip install mcp"
        ) from exc

    server = FastMCP("quant-labs-memory")
    for tool in TOOLS.values():
        server.tool()(tool)
    return server


def main() -> None:  # pragma: no cover - process entrypoint
    init_db()
    build_server().run()


if __name__ == "__main__":  # pragma: no cover
    main()
