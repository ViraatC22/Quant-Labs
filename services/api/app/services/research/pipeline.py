"""Research pipeline orchestrator (Lattice L5+L6+L7 end to end).

Ties the router, retrievers, conflict surfacing, and writer into one call:
``answer_question`` → a grounded, cited answer with a trust score. The
``analytics`` route bypasses retrieval and answers from real trade math so
numeric questions never come from prose.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Claim, ClaimConflict, Trade
from app.services.research import retrieval, router, writer


@dataclass
class ResearchAnswer:
    question: str
    route: str
    answer_markdown: str
    trust_score: float
    citations: list[dict[str, Any]] = field(default_factory=list)
    special_elements: list[dict[str, Any]] = field(default_factory=list)
    retrieved: dict[str, Any] = field(default_factory=dict)


def answer_question(db: Session, *, user_id: UUID, question: str) -> ResearchAnswer:
    route = router.classify(question)
    if route == "analytics":
        return _answer_analytics(db, user_id=user_id, question=question)

    run_graph = route in ("connection", "hybrid")
    run_text = route in ("content", "hybrid")

    chunks = retrieval.search_chunks(db, user_id=user_id, query=question) if run_text else []
    claims = retrieval.search_claims(db, user_id=user_id, query=question)

    graph = retrieval.RetrievedGraph()
    if run_graph:
        linked = retrieval.link_entities(db, user_id=user_id, query=question)
        if linked:
            graph = retrieval.neighborhood(
                db, user_id=user_id, node_ids=[node.id for node in linked], depth=1
            )

    conflicts = _surface_conflicts(db, user_id=user_id, claims=claims)

    result = writer.compose(
        question=question, chunks=chunks, claims=claims, conflicts=conflicts
    )

    return ResearchAnswer(
        question=question,
        route=route,
        answer_markdown=result.answer_markdown,
        trust_score=result.trust_score,
        citations=[asdict(c) for c in result.citations],
        special_elements=result.special_elements,
        retrieved={
            "chunks": [
                asdict(c) | {"chunk_id": str(c.chunk_id), "source_id": str(c.source_id)}
                for c in chunks
            ],
            "claims": [asdict(c) | {"claim_id": str(c.claim_id)} for c in claims],
            "nodes": [
                {"id": str(n.id), "label": n.label, "node_type": n.node_type}
                for n in graph.nodes
            ],
            "edges": [
                {
                    "id": str(e.id),
                    "edge_type": e.edge_type,
                    "from_node_id": str(e.from_node_id),
                    "to_node_id": str(e.to_node_id),
                }
                for e in graph.edges
            ],
        },
    )


def _surface_conflicts(
    db: Session, *, user_id: UUID, claims: list[retrieval.RetrievedClaim]
) -> list[dict[str, Any]]:
    claim_ids = {claim.claim_id for claim in claims}
    if not claim_ids:
        return []
    rows = db.scalars(
        select(ClaimConflict).where(
            ClaimConflict.user_id == user_id,
            ClaimConflict.status == "open",
            ClaimConflict.claim_a_id.in_(claim_ids) | ClaimConflict.claim_b_id.in_(claim_ids),
        )
    ).all()
    out: list[dict[str, Any]] = []
    for conflict in rows:
        claim_a = db.get(Claim, conflict.claim_a_id)
        claim_b = db.get(Claim, conflict.claim_b_id)
        if claim_a is None or claim_b is None:
            continue
        out.append(
            {
                "conflict_id": str(conflict.id),
                "claim_a": claim_a.statement_text,
                "claim_b": claim_b.statement_text,
            }
        )
    return out


def _answer_analytics(db: Session, *, user_id: UUID, question: str) -> ResearchAnswer:
    trades = db.scalars(
        select(Trade).where(Trade.user_id == user_id, Trade.pnl_amount.is_not(None))
    ).all()
    n = len(trades)
    if n == 0:
        return ResearchAnswer(
            question=question,
            route="analytics",
            answer_markdown=(
                "You have no closed trades with recorded P&L yet, so there are no "
                "performance stats to compute."
            ),
            trust_score=1.0,
        )
    wins = [t for t in trades if (t.pnl_amount or Decimal(0)) > 0]
    total_pnl = sum((t.pnl_amount or Decimal(0)) for t in trades)
    win_rate = len(wins) / n
    r_values = [float(t.pnl_r) for t in trades if t.pnl_r is not None]
    avg_r = sum(r_values) / len(r_values) if r_values else None

    stat_row = {
        "type": "stat_row",
        "stats": [
            {"label": "closed trades", "value": n},
            {"label": "win rate", "value": f"{win_rate:.0%}"},
            {"label": "total P&L", "value": f"{float(total_pnl):.2f}"},
        ],
    }
    if avg_r is not None:
        stat_row["stats"].append({"label": "avg R", "value": f"{avg_r:.2f}"})

    answer = (
        f"Across {n} closed trade(s): win rate {win_rate:.0%}, "
        f"total P&L {float(total_pnl):.2f}"
    )
    if avg_r is not None:
        answer += f", average R {avg_r:.2f}"
    answer += ". Computed from your recorded trades."

    return ResearchAnswer(
        question=question,
        route="analytics",
        answer_markdown=answer,
        trust_score=1.0,
        special_elements=[stat_row],
        retrieved={"trades_counted": n},
    )
