from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.models.domain import SourceDocument, Trade
from app.services.market_data import MarketQuote
from app.services.technical_extraction import (
    extract_technical_profile,
    extract_technical_tags,
    technical_tags_from_profile,
)


@dataclass(frozen=True)
class StrategyEvaluation:
    title: str
    decision: str
    score: float
    confidence: float
    rationale: str
    technical_tags: list[str]
    technical_profile: dict[str, list[str]]
    included: list[str]
    excluded: list[str]
    draft: dict


def evaluate_strategy_idea(
    *,
    idea: str,
    sources: list[SourceDocument],
    trades: list[Trade],
    symbol: str | None = None,
    quote: MarketQuote | None = None,
) -> StrategyEvaluation:
    profile = extract_technical_profile(idea)
    tags = sorted({*extract_technical_tags(idea), *technical_tags_from_profile(profile)})
    setup = _first_profile_value(profile, "setups") or _setup_from_tags(tags)
    strategy_name = _strategy_title(idea, setup)
    matched_sources = _matched_sources(sources, tags, idea)
    related_trades = _related_trades(trades, tags, strategy_name, setup)
    closed_related = [trade for trade in related_trades if trade.exit_price is not None]
    avg_related_pnl = _average_pnl(closed_related)
    losing_conflicts = [trade for trade in closed_related if _trade_pnl(trade) < 0]
    score = _score(tags, matched_sources, closed_related, avg_related_pnl, losing_conflicts)
    decision = _decision(score, tags)
    inferred_symbol = symbol or _symbol_from_text(idea, tags, matched_sources, trades)
    side = _side_from_text(idea, tags)
    included = _included_reasons(
        tags=tags,
        matched_sources=matched_sources,
        closed_related=closed_related,
        avg_related_pnl=avg_related_pnl,
        setup=setup,
    )
    excluded = _excluded_reasons(
        tags=tags,
        matched_sources=matched_sources,
        closed_related=closed_related,
        losing_conflicts=losing_conflicts,
        idea=idea,
    )
    rationale = _rationale(decision, score, included, excluded)

    return StrategyEvaluation(
        title=strategy_name,
        decision=decision,
        score=score,
        confidence=round(max(0.05, min(0.95, score)), 2),
        rationale=rationale,
        technical_tags=tags,
        technical_profile=profile,
        included=included,
        excluded=excluded,
        draft=_draft(
            symbol=inferred_symbol,
            side=side,
            strategy_name=strategy_name,
            setup=setup,
            tags=tags,
            rationale=rationale,
            quote=quote,
        ),
    )


def build_optimal_strategy(
    *,
    sources: list[SourceDocument],
    trades: list[Trade],
    quote: MarketQuote | None = None,
) -> StrategyEvaluation:
    candidates = [_candidate_text(source) for source in sources]
    if not candidates:
        return evaluate_strategy_idea(
            idea="Build a source-backed strategy after adding strategy notes or research papers.",
            sources=sources,
            trades=trades,
            symbol="SPY",
            quote=quote,
        )

    evaluations = [
        evaluate_strategy_idea(
            idea=candidate,
            sources=sources,
            trades=trades,
            quote=quote,
        )
        for candidate in candidates
    ]
    return sorted(evaluations, key=lambda item: item.score, reverse=True)[0]


def evaluation_journal_body(evaluation: StrategyEvaluation) -> str:
    included = "\n".join(f"- {item}" for item in evaluation.included[:5]) or "- No inclusions."
    excluded = "\n".join(f"- {item}" for item in evaluation.excluded[:5]) or "- No exclusions."
    tags = ", ".join(evaluation.technical_tags[:10]) or "none"
    return (
        f"Decision: {evaluation.decision}\n"
        f"Score: {round(evaluation.score * 100)}%\n"
        f"Rationale: {evaluation.rationale}\n\n"
        f"Included:\n{included}\n\n"
        f"Excluded:\n{excluded}\n\n"
        f"Technical tags: {tags}"
    )


def _candidate_text(source: SourceDocument) -> str:
    metadata = source.source_metadata or {}
    strategy = metadata.get("strategyInfo") or metadata.get("strategy_info") or {}
    if not isinstance(strategy, dict):
        strategy = {}
    pieces = [
        str(strategy.get("name") or source.title),
        str(strategy.get("summary") or ""),
        str(strategy.get("setup") or ""),
        " ".join(strategy.get("technical_tags") or []),
        source.content_text or "",
    ]
    return " ".join(piece for piece in pieces if piece.strip())[:5000]


def _strategy_title(idea: str, setup: str | None) -> str:
    first_sentence = idea.strip().split(".")[0].strip()
    if first_sentence and len(first_sentence) <= 90:
        return first_sentence
    return setup or "Plain-English strategy idea"


def _matched_sources(
    sources: list[SourceDocument],
    tags: list[str],
    idea: str,
) -> list[SourceDocument]:
    tag_set = set(tags)
    idea_norm = _normalize(idea)
    matches: list[SourceDocument] = []
    for source in sources:
        metadata = source.source_metadata or {}
        strategy = metadata.get("strategyInfo") or metadata.get("strategy_info") or {}
        source_tags = {
            str(tag).strip().lower()
            for tag in [
                *(metadata.get("technical_tags") or []),
                *(metadata.get("tags") or []),
                *(metadata.get("generated_tags") or []),
                *_strategy_tags(strategy),
            ]
            if str(tag).strip()
        }
        source_text = _normalize(f"{source.title} {source.content_text or ''}")
        idea_words = idea_norm.split()[:8]
        if tag_set.intersection(source_tags) or any(word in source_text for word in idea_words):
            matches.append(source)
    return matches


def _related_trades(
    trades: list[Trade],
    tags: list[str],
    strategy_name: str,
    setup: str | None,
) -> list[Trade]:
    needles = {
        _normalize(strategy_name),
        _normalize(setup or ""),
        *[_normalize(tag) for tag in tags],
    }
    needles = {needle for needle in needles if needle}
    related: list[Trade] = []
    for trade in trades:
        metadata = trade.trade_metadata or {}
        haystack = _normalize(
            " ".join(
                [
                    trade.symbol,
                    str(metadata.get("strategy", "")),
                    str(metadata.get("setup", "")),
                    str(metadata.get("notes", "")),
                ]
            )
        )
        if any(needle and needle in haystack for needle in needles):
            related.append(trade)
    return related


def _score(
    tags: list[str],
    matched_sources: list[SourceDocument],
    related_trades: list[Trade],
    avg_related_pnl: Decimal,
    losing_conflicts: list[Trade],
) -> float:
    score = 0.36
    score += min(0.24, len(matched_sources) * 0.06)
    score += min(0.16, len(tags) * 0.015)
    score += min(0.14, len(related_trades) * 0.035)
    if avg_related_pnl > 0:
        score += 0.12
    if avg_related_pnl < 0:
        score -= 0.12
    score -= min(0.18, len(losing_conflicts) * 0.06)
    if not tags:
        score -= 0.2
    return round(max(0.05, min(0.95, score)), 2)


def _decision(score: float, tags: list[str]) -> str:
    if not tags:
        return "needs-structure"
    if score >= 0.68:
        return "beneficial"
    if score >= 0.48:
        return "observe"
    return "weakens-edge"


def _included_reasons(
    *,
    tags: list[str],
    matched_sources: list[SourceDocument],
    closed_related: list[Trade],
    avg_related_pnl: Decimal,
    setup: str | None,
) -> list[str]:
    reasons: list[str] = []
    if setup:
        reasons.append(f"Setup extracted: {setup}.")
    if tags:
        reasons.append(f"Technicals extracted: {', '.join(tags[:8])}.")
    if matched_sources:
        reasons.append(f"{len(matched_sources)} learned source(s) overlap with this idea.")
    if closed_related:
        reasons.append(
            f"{len(closed_related)} related closed trade(s), average P&L {_money(avg_related_pnl)}."
        )
    return reasons or ["The idea was captured, but it needs clearer technical structure."]


def _excluded_reasons(
    *,
    tags: list[str],
    matched_sources: list[SourceDocument],
    closed_related: list[Trade],
    losing_conflicts: list[Trade],
    idea: str,
) -> list[str]:
    reasons: list[str] = []
    if not tags:
        reasons.append("No concrete technical tags were found, so the idea is too vague to trade.")
    if not matched_sources:
        reasons.append("No learned source strongly supports this idea yet.")
    if not closed_related:
        reasons.append("No matching closed-trade sample exists for validation.")
    if losing_conflicts:
        reasons.append(f"{len(losing_conflicts)} matching trade(s) are losing examples.")
    if not any(word in idea.lower() for word in ["risk", "stop", "invalidation", "size"]):
        reasons.append("Risk, invalidation, or sizing rules were not explicit.")
    return reasons


def _rationale(decision: str, score: float, included: list[str], excluded: list[str]) -> str:
    if decision == "beneficial":
        prefix = "This looks additive to the current knowledge base"
    elif decision == "observe":
        prefix = "This is worth paper-trading before promotion"
    elif decision == "needs-structure":
        prefix = "This needs clearer technical structure"
    else:
        prefix = "This may weaken the current strategy set"
    suffix = excluded[0] if excluded else ""
    return f"{prefix} at {round(score * 100)}% score. {included[0]} {suffix}".strip()


def _draft(
    *,
    symbol: str,
    side: str,
    strategy_name: str,
    setup: str | None,
    tags: list[str],
    rationale: str,
    quote: MarketQuote | None,
) -> dict:
    entry = quote.last_price if quote else None
    target_percent = _target_percent(tags)
    exit_price = None
    if entry is not None:
        multiplier = (
            Decimal("1") + target_percent
            if side == "long"
            else Decimal("1") - target_percent
        )
        exit_price = (entry * multiplier).quantize(Decimal("0.0001"))

    return {
        "symbol": symbol,
        "side": side,
        "strategy": strategy_name,
        "setup": setup or _setup_from_tags(tags),
        "emotion": "patient",
        "quantity": "1",
        "fees": "0",
        "entry_price": str(entry) if entry is not None else None,
        "exit_price": str(exit_price) if exit_price is not None else None,
        "price_source": quote.provider if quote else None,
        "price_time": quote.market_time.isoformat() if quote and quote.market_time else None,
        "notes": f"{rationale} Tags: {', '.join(tag for tag in tags[:6] if ':' not in tag)}.",
    }


def _first_profile_value(profile: dict[str, list[str]], key: str) -> str | None:
    values = profile.get(key)
    return values[0] if values else None


def _setup_from_tags(tags: list[str]) -> str:
    text = " ".join(tags)
    for needle, label in [
        ("opening-range-breakout", "Opening range breakout"),
        ("vwap-pullback", "VWAP pullback"),
        ("risk-parity", "Risk parity"),
        ("mean-reversion", "Mean reversion"),
        ("trend-following", "Trend following"),
        ("momentum", "Momentum"),
        ("breakout", "Breakout"),
    ]:
        if needle in text:
            return label
    return "Source-backed setup"


def _symbol_from_text(
    idea: str,
    tags: list[str],
    sources: list[SourceDocument],
    trades: list[Trade],
) -> str:
    upper = idea.upper()
    for symbol in ["ES", "NQ", "SPY", "QQQ", "BTC", "ETH", "AAPL", "MSFT", "NVDA"]:
        if f" {symbol} " in f" {upper} ":
            return symbol
    if trades:
        counts: dict[str, int] = {}
        for trade in trades:
            counts[trade.symbol] = counts.get(trade.symbol, 0) + 1
        if counts:
            return sorted(counts.items(), key=lambda item: item[1], reverse=True)[0][0]
    source_text = " ".join(
        f"{source.title} {source.content_text or ''}" for source in sources
    ).lower()
    tag_text = " ".join(tags)
    if "futures" in tag_text or "futures" in source_text or "cme" in source_text:
        return "ES"
    if "crypto" in tag_text or "btc" in source_text:
        return "BTC"
    return "SPY"


def _side_from_text(idea: str, tags: list[str]) -> str:
    text = f"{idea} {' '.join(tags)}".lower()
    if any(word in text for word in ["short", "fade", "breakdown", "sell"]):
        return "short"
    return "long"


def _target_percent(tags: list[str]) -> Decimal:
    text = " ".join(tags)
    if "risk-parity" in text:
        return Decimal("0.006")
    if "opening-range-breakout" in text or "breakout" in text:
        return Decimal("0.012")
    if "mean-reversion" in text or "vwap-pullback" in text:
        return Decimal("0.008")
    return Decimal("0.01")


def _average_pnl(trades: list[Trade]) -> Decimal:
    if not trades:
        return Decimal("0")
    return sum(_trade_pnl(trade) for trade in trades) / Decimal(len(trades))


def _trade_pnl(trade: Trade) -> Decimal:
    if trade.exit_price is None:
        return Decimal("0")
    direction = Decimal("1") if trade.side == "long" else Decimal("-1")
    return (trade.exit_price - trade.entry_price) * trade.quantity * direction - trade.fees


def _money(value: Decimal) -> str:
    return f"${value.quantize(Decimal('0.01'))}"


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())


def _strategy_tags(strategy: object) -> list[str]:
    if not isinstance(strategy, dict):
        return []
    return [str(tag) for tag in strategy.get("technical_tags") or []]
