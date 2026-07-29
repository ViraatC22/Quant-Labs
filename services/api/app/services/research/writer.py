"""Grounded research answer synthesis.

The writer gives a configured chat model only the evidence selected by the
retrieval pipeline, then validates every inline reference before displaying the
answer. Invalid or unavailable model output falls back to a concise local
composer. No model is ever allowed to turn an unrelated retrieved snippet into
an unsupported explanation.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.services import ai_router
from app.services.research.retrieval import RetrievedChunk, RetrievedClaim, RetrievedTrade

_REF_RE = re.compile(r"\[((?:trade|chunk|claim):[0-9a-fA-F-]+)\]")


@dataclass
class Citation:
    ref: str  # e.g. "trade:<uuid>", "chunk:<uuid>", or "claim:<uuid>"
    kind: str  # "trade" | "chunk" | "claim"
    source_title: str
    snippet: str


@dataclass
class AnswerResult:
    answer_markdown: str
    citations: list[Citation] = field(default_factory=list)
    trust_score: float = 0.0
    special_elements: list[dict[str, Any]] = field(default_factory=list)
    generation_mode: str = "local"
    writer_provider_id: str | None = None
    writer_model: str | None = None


NO_EVIDENCE = (
    "I don't have evidence in a matching trade or relevant source to answer that yet. "
    "Add the trade note or import a source that covers it, and I'll answer with citations."
)

_ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer_markdown": {"type": "string"},
        "used_citation_refs": {
            "type": "array",
            "items": {"type": "string"},
        },
        "insufficient_evidence": {"type": "boolean"},
    },
    "required": ["answer_markdown", "used_citation_refs", "insufficient_evidence"],
    "additionalProperties": False,
}


def compose(
    *,
    question: str,
    chunks: list[RetrievedChunk],
    claims: list[RetrievedClaim],
    trades: list[RetrievedTrade] | None = None,
    conflicts: list[dict[str, Any]] | None = None,
    use_ai: bool | None = None,
) -> AnswerResult:
    trades = trades or []
    conflicts = conflicts or []
    citations_by_ref = _citation_map(trades=trades, chunks=chunks, claims=claims)
    if not citations_by_ref:
        return AnswerResult(answer_markdown=NO_EVIDENCE)

    # `None` means normal configured behavior; False is a hermetic escape hatch
    # for tests and explicitly local callers.
    if use_ai is not False:
        completion = ai_router.complete_json_with_ai(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=_user_prompt(
                question=question,
                trades=trades,
                chunks=chunks,
                claims=claims,
                conflicts=conflicts,
            ),
            response_schema=_ANSWER_SCHEMA,
        )
        if completion is not None:
            validated = _validated_ai_result(
                completion.payload,
                citations_by_ref=citations_by_ref,
                conflicts=conflicts,
                provider_id=completion.provider_id,
                model=completion.model,
            )
            if validated is not None:
                return validated

    return _compose_local(
        trades=trades,
        chunks=chunks,
        claims=claims,
        conflicts=conflicts,
        citations_by_ref=citations_by_ref,
    )


_SYSTEM_PROMPT = """
You are a rigorous trading-journal analyst. Answer only from the supplied
evidence records; never use outside facts or invent price action, news, market
conditions, motives, or strategy rules.

For a causal question such as "why did this trade lose?", prioritize the
matching trade's journal_summary and recorded fields. Clearly distinguish a
recorded cause from a reasonable inference. If the outcome is known but no
causal note exists, say the cause is not documented. A loss alone does not
prove why it happened. If several trades match, identify the date/symbol used.

Write a concise, direct answer. Every factual paragraph or bullet must end with
one or more inline references exactly as provided, such as [trade:uuid] or
[chunk:uuid]. Return only the requested JSON object. Include only references
that appear inline in answer_markdown in used_citation_refs.
""".strip()


def _user_prompt(
    *,
    question: str,
    trades: list[RetrievedTrade],
    chunks: list[RetrievedChunk],
    claims: list[RetrievedClaim],
    conflicts: list[dict[str, Any]],
) -> str:
    evidence: list[dict[str, Any]] = []
    for trade in trades[:4]:
        evidence.append({"ref": f"trade:{trade.trade_id}", "kind": "trade", **asdict(trade)})
    for claim in claims[:4]:
        evidence.append({"ref": f"claim:{claim.claim_id}", "kind": "claim", **asdict(claim)})
    for chunk in chunks[:4]:
        evidence.append({"ref": f"chunk:{chunk.chunk_id}", "kind": "chunk", **asdict(chunk)})
    return (
        f"Question:\n{question}\n\n"
        f"Allowed evidence records:\n{json.dumps(evidence, default=str, ensure_ascii=False)}\n\n"
        f"Known source conflicts:\n{json.dumps(conflicts, ensure_ascii=False)}"
    )


def _validated_ai_result(
    payload: dict[str, Any],
    *,
    citations_by_ref: dict[str, Citation],
    conflicts: list[dict[str, Any]],
    provider_id: str,
    model: str,
) -> AnswerResult | None:
    answer = payload.get("answer_markdown")
    declared_refs = payload.get("used_citation_refs")
    insufficient = payload.get("insufficient_evidence")
    if (
        not isinstance(answer, str)
        or not answer.strip()
        or not isinstance(declared_refs, list)
        or not isinstance(insufficient, bool)
    ):
        return None

    inline_refs = list(dict.fromkeys(_REF_RE.findall(answer)))
    declared = [ref for ref in declared_refs if isinstance(ref, str)]
    # Reject, rather than silently hiding, any invented or inconsistent model
    # reference. The deterministic fallback is safer than partially repairing
    # an answer whose grounding contract was broken.
    if (
        any(ref not in citations_by_ref for ref in inline_refs)
        or any(ref not in citations_by_ref for ref in declared)
        or set(declared) != set(inline_refs)
    ):
        return None
    if not insufficient and not inline_refs:
        return None

    citations = [citations_by_ref[ref] for ref in inline_refs]
    return AnswerResult(
        answer_markdown=answer.strip(),
        citations=citations,
        trust_score=_evidence_coverage(answer),
        special_elements=_special_elements(citations, conflicts),
        generation_mode="ai",
        writer_provider_id=provider_id,
        writer_model=model,
    )


def _compose_local(
    *,
    trades: list[RetrievedTrade],
    chunks: list[RetrievedChunk],
    claims: list[RetrievedClaim],
    conflicts: list[dict[str, Any]],
    citations_by_ref: dict[str, Citation],
) -> AnswerResult:
    lines: list[str] = []
    used_refs: list[str] = []

    if trades:
        trade = trades[0]
        trade_ref = f"trade:{trade.trade_id}"
        used_refs.append(trade_ref)
        outcome = _trade_outcome(trade.pnl_amount)
        date_label = trade.entry_time.strftime("%B %-d, %Y")
        details = f"the {date_label} {trade.side} trade"
        if outcome:
            details += f", {outcome} after ${trade.fees:.2f} in fees"
        lines.append(f"The matching {trade.symbol} record is {details}. [{trade_ref}]")

        if trade.journal_summary:
            note = trade.journal_summary.strip()
            lines.append(
                "The clearest recorded explanation is execution discipline: "
                f"your journal says, “{note}” [{trade_ref}]"
            )
        else:
            lines.append(
                "The trade record confirms the result, but it does not contain a causal note, "
                f"so the reason for the outcome is not documented. [{trade_ref}]"
            )

        # A saved playbook is useful context only when the retrieval stage found
        # it relevant; it is never presented as a fact about what the market did.
        if chunks:
            chunk = chunks[0]
            chunk_ref = f"chunk:{chunk.chunk_id}"
            used_refs.append(chunk_ref)
            lines.append(
                f"Your saved playbook adds this relevant rule: {_first_sentence(chunk.text)} "
                f"[{chunk_ref}]"
            )
    else:
        for claim in claims[:3]:
            ref = f"claim:{claim.claim_id}"
            used_refs.append(ref)
            polarity_note = "" if claim.polarity == "supports" else f" ({claim.polarity})"
            lines.append(f"- {claim.statement_text}{polarity_note} [{ref}]")
        for chunk in chunks[:3]:
            ref = f"chunk:{chunk.chunk_id}"
            used_refs.append(ref)
            lines.append(f"- {_first_sentence(chunk.text)} [{ref}]")

    if conflicts:
        lines.extend(["", "Sources disagree on part of this evidence:"])
        for conflict in conflicts:
            lines.append(f"- {conflict['claim_a']} vs. {conflict['claim_b']}")

    answer = "\n\n".join(line for line in lines if line != "")
    unique_refs = list(dict.fromkeys(used_refs))
    citations = [citations_by_ref[ref] for ref in unique_refs if ref in citations_by_ref]
    return AnswerResult(
        answer_markdown=answer,
        citations=citations,
        trust_score=_evidence_coverage(answer),
        special_elements=_special_elements(citations, conflicts),
        generation_mode="local",
    )


def _citation_map(
    *,
    trades: list[RetrievedTrade],
    chunks: list[RetrievedChunk],
    claims: list[RetrievedClaim],
) -> dict[str, Citation]:
    citations: dict[str, Citation] = {}
    for trade in trades:
        ref = f"trade:{trade.trade_id}"
        pnl = _trade_outcome(trade.pnl_amount) or "open P&L"
        note = (
            trade.journal_summary.strip()
            if trade.journal_summary
            else "No causal note recorded."
        )
        citations[ref] = Citation(
            ref=ref,
            kind="trade",
            source_title=f"{trade.symbol} trade · {trade.entry_time.strftime('%b %-d, %Y')}",
            snippet=f"{pnl}. {note}"[:300],
        )
    for claim in claims:
        ref = f"claim:{claim.claim_id}"
        citations[ref] = Citation(
            ref=ref,
            kind="claim",
            source_title=", ".join(claim.source_titles) or "source",
            snippet=claim.statement_text[:300],
        )
    for chunk in chunks:
        ref = f"chunk:{chunk.chunk_id}"
        citations[ref] = Citation(
            ref=ref,
            kind="chunk",
            source_title=chunk.source_title,
            snippet=_first_sentence(chunk.text)[:300],
        )
    return citations


def _trade_outcome(pnl_amount: float | None) -> str | None:
    if pnl_amount is None:
        return None
    direction = "a gain of" if pnl_amount >= 0 else "a loss of"
    return f"{direction} ${abs(pnl_amount):,.2f}"


def _evidence_coverage(answer: str) -> float:
    """Measure factual line coverage, not truth, relevance, or confidence."""
    factual_lines = [
        line.strip()
        for line in answer.splitlines()
        if line.strip()
        and not line.strip().endswith(":")
        and not line.lstrip().startswith("#")
    ]
    if not factual_lines:
        return 0.0
    cited = sum(1 for line in factual_lines if _REF_RE.search(line))
    return round(cited / len(factual_lines), 3)


def _special_elements(
    citations: list[Citation], conflicts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    elements: list[dict[str, Any]] = []
    if citations:
        elements.append(
            {
                "type": "citation_list",
                "count": len(citations),
                "sources": sorted({citation.source_title for citation in citations}),
            }
        )
    if conflicts:
        elements.append({"type": "conflict_callout", "conflicts": conflicts})
    return elements


def _first_sentence(text: str) -> str:
    stripped = text.strip()
    for terminator in (". ", "! ", "? "):
        index = stripped.find(terminator)
        if 0 < index < 300:
            return stripped[: index + 1]
    return stripped[:300]
