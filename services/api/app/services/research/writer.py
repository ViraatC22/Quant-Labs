"""Grounded answer writer (Lattice L6/L7).

Composes an answer strictly from retrieved evidence — the model (or, by
default, this deterministic composer) never speaks from memory. Every statement
carries a citation to a chunk or claim, and the trust score is the measured
share of answer sentences backed by real evidence, not a synthetic confidence
number.

If nothing was retrieved, the writer refuses: it says so plainly and lists what
it would need, rather than fabricating a fluent answer. That refusal is the
whole point of the merge — trust is the product.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.research.retrieval import RetrievedChunk, RetrievedClaim


@dataclass
class Citation:
    ref: str  # e.g. "chunk:<uuid>" or "claim:<uuid>"
    kind: str  # "chunk" | "claim"
    source_title: str
    snippet: str


@dataclass
class AnswerResult:
    answer_markdown: str
    citations: list[Citation] = field(default_factory=list)
    trust_score: float = 0.0
    special_elements: list[dict[str, Any]] = field(default_factory=list)


NO_EVIDENCE = (
    "I don't have evidence in your memory to answer that yet. "
    "Import a source that covers it, and I'll answer with citations."
)


def compose(
    *,
    question: str,
    chunks: list[RetrievedChunk],
    claims: list[RetrievedClaim],
    conflicts: list[dict[str, Any]] | None = None,
) -> AnswerResult:
    conflicts = conflicts or []
    if not chunks and not claims:
        return AnswerResult(answer_markdown=NO_EVIDENCE, citations=[], trust_score=0.0)

    citations: list[Citation] = []
    lines: list[str] = ["Based on your memory:"]
    cited_sentences = 0
    total_sentences = 0

    for claim in claims[:4]:
        ref = f"claim:{claim.claim_id}"
        source = ", ".join(claim.source_titles) or "source"
        polarity_note = "" if claim.polarity == "supports" else f" _({claim.polarity})_"
        lines.append(f"- {claim.statement_text}{polarity_note} [{ref}]")
        citations.append(
            Citation(
                ref=ref,
                kind="claim",
                source_title=source,
                snippet=claim.statement_text[:200],
            )
        )
        cited_sentences += 1
        total_sentences += 1

    for chunk in chunks[:4]:
        ref = f"chunk:{chunk.chunk_id}"
        snippet = _first_sentence(chunk.text)
        lines.append(f"- {snippet} [{ref}]")
        citations.append(
            Citation(
                ref=ref,
                kind="chunk",
                source_title=chunk.source_title,
                snippet=snippet[:200],
            )
        )
        cited_sentences += 1
        total_sentences += 1

    special_elements: list[dict[str, Any]] = []
    if conflicts:
        lines.append("")
        lines.append("⚠️ Sources disagree on this:")
        for conflict in conflicts:
            lines.append(
                f"- {conflict['claim_a']} vs. {conflict['claim_b']}"
            )
        special_elements.append({"type": "conflict_callout", "conflicts": conflicts})

    if citations:
        special_elements.insert(
            0,
            {
                "type": "citation_list",
                "count": len(citations),
                "sources": sorted({c.source_title for c in citations}),
            },
        )

    trust = cited_sentences / total_sentences if total_sentences else 0.0
    return AnswerResult(
        answer_markdown="\n".join(lines),
        citations=citations,
        trust_score=round(trust, 3),
        special_elements=special_elements,
    )


def _first_sentence(text: str) -> str:
    stripped = text.strip()
    for terminator in (". ", "! ", "? "):
        index = stripped.find(terminator)
        if 0 < index < 240:
            return stripped[: index + 1]
    return stripped[:240]
