from __future__ import annotations

from decimal import Decimal

from app.models.domain import SourceDocument, Trade
from app.schemas.trades import TradeRecommendationRead


def build_trade_recommendations(
    *,
    sources: list[SourceDocument],
    trades: list[Trade],
) -> list[TradeRecommendationRead]:
    source_recommendations = [
        _recommend_from_source(source, trades)
        for source in sources
        if _strategy_info(source) or _technical_tags(source)
    ]
    recommendations = [item for item in source_recommendations if item]
    if recommendations:
        return sorted(recommendations, key=lambda item: item.confidence, reverse=True)[:8]

    return [
        TradeRecommendationRead(
            id="upload-strategy-source",
            title="Upload a strategy source",
            action="Add a playbook, chart notes, or strategy PDF before asking for trade guidance.",
            confidence=0.2,
            technical_tags=[],
            rationale=(
                "Recommendations are generated from learned strategy sources, technical tags, "
                "and your closed-trade history."
            ),
            risk_notes=["No recommendation is produced until there is strategy evidence."],
            evidence=[],
        )
    ]


def _recommend_from_source(
    source: SourceDocument,
    trades: list[Trade],
) -> TradeRecommendationRead | None:
    metadata = source.source_metadata or {}
    strategy_info = _strategy_info(source)
    technical_tags = _technical_tags(source)
    strategy_name = _strategy_name(source.title, strategy_info)
    setup = _string(strategy_info.get("setup") if strategy_info else None)
    related_trades = _related_trades(
        trades,
        strategy_name=strategy_name,
        setup=setup,
        tags=technical_tags,
    )
    total_pnl = sum(_trade_pnl(trade) for trade in related_trades)
    wins = sum(1 for trade in related_trades if _trade_pnl(trade) > 0)
    win_rate = wins / len(related_trades) if related_trades else 0
    source_confidence = float(strategy_info.get("confidence", 0.45)) if strategy_info else 0.35
    validation_boost = min(0.25, len(related_trades) * 0.04)
    pnl_adjustment = 0.12 if total_pnl > 0 else -0.08 if total_pnl < 0 else 0
    confidence = max(0.05, min(0.95, source_confidence + validation_boost + pnl_adjustment))
    entry_rules = _rules(strategy_info, "entry_rules")
    exit_rules = _rules(strategy_info, "exit_rules")
    risk_rules = _rules(strategy_info, "risk_rules")
    action = _action(
        strategy_name=strategy_name,
        setup=setup,
        related_trades=related_trades,
        total_pnl=total_pnl,
    )
    evidence = [source.title]
    learned = metadata.get("learned_memory")
    if isinstance(learned, dict):
        evidence.append(
            f"{learned.get('chunk_count', 0)} learned chunks / "
            f"{learned.get('node_count', 0)} map nodes"
        )
    if related_trades:
        evidence.append(f"{len(related_trades)} matching trades, {round(win_rate * 100)}% win rate")

    return TradeRecommendationRead(
        id=f"recommend-{source.id}",
        title=setup or strategy_name,
        action=action,
        strategy=strategy_name,
        setup=setup,
        confidence=round(confidence, 2),
        technical_tags=technical_tags[:14],
        rationale=_rationale(source.title, entry_rules, exit_rules, related_trades),
        risk_notes=risk_rules[:4] or ["Define invalidation and max risk before taking this setup."],
        evidence=evidence,
    )


def _action(
    *,
    strategy_name: str,
    setup: str | None,
    related_trades: list[Trade],
    total_pnl: Decimal,
) -> str:
    label = setup or strategy_name
    if not related_trades:
        return f"Paper-trade {label} with tiny size until it has a journaled sample."
    if total_pnl > 0:
        return f"Favor {label} only when the source rules and current technical tags align."
    if total_pnl < 0:
        return f"Do not size up {label}; review losing examples before the next attempt."
    return f"Keep {label} in observation mode until the edge is clearer."


def _rationale(
    source_title: str,
    entry_rules: list[str],
    exit_rules: list[str],
    related_trades: list[Trade],
) -> str:
    pieces = [f"Learned from {source_title}."]
    if entry_rules:
        pieces.append(f"Entry evidence: {entry_rules[0]}")
    if exit_rules:
        pieces.append(f"Exit evidence: {exit_rules[0]}")
    if related_trades:
        pieces.append("Past trades are included in confidence weighting.")
    return " ".join(pieces)


def _related_trades(
    trades: list[Trade],
    *,
    strategy_name: str,
    setup: str | None,
    tags: list[str],
) -> list[Trade]:
    related: list[Trade] = []
    needles = {
        _normalize(strategy_name),
        _normalize(setup or ""),
        *[_normalize(tag) for tag in tags],
    }
    needles = {needle for needle in needles if needle}
    for trade in trades:
        metadata = trade.trade_metadata or {}
        haystack = " ".join(
            [
                str(metadata.get("strategy", "")),
                str(metadata.get("setup", "")),
                str(metadata.get("notes", "")),
                trade.symbol,
            ]
        )
        normalized_haystack = _normalize(haystack)
        if any(needle and needle in normalized_haystack for needle in needles):
            related.append(trade)
    return related


def _trade_pnl(trade: Trade) -> Decimal:
    if trade.exit_price is None:
        return Decimal("0")
    direction = Decimal("1") if trade.side == "long" else Decimal("-1")
    return (trade.exit_price - trade.entry_price) * trade.quantity * direction - trade.fees


def _strategy_info(source: SourceDocument) -> dict | None:
    metadata = source.source_metadata or {}
    value = metadata.get("strategyInfo") or metadata.get("strategy_info")
    return value if isinstance(value, dict) else None


def _strategy_name(title: str, strategy_info: dict | None) -> str:
    if not strategy_info:
        return title
    return _string(strategy_info.get("name")) or _string(strategy_info.get("setup")) or title


def _technical_tags(source: SourceDocument) -> list[str]:
    metadata = source.source_metadata or {}
    strategy_info = _strategy_info(source) or {}
    tags = set()
    for value in [
        *(metadata.get("tags") or []),
        *(metadata.get("technical_tags") or []),
        *(metadata.get("generated_tags") or []),
        *(metadata.get("aiTags") or []),
        *(strategy_info.get("technical_tags") or []),
    ]:
        if str(value).strip():
            tags.add(str(value).strip().lower())
    profile = strategy_info.get("technical_profile")
    if isinstance(profile, dict):
        for category, labels in profile.items():
            if isinstance(labels, list):
                for label in labels:
                    tags.add(str(label).strip().lower())
                    tags.add(f"{category}:{_normalize(str(label)).replace(' ', '-')}")
    return sorted(tag for tag in tags if tag)


def _rules(strategy_info: dict | None, key: str) -> list[str]:
    if not strategy_info:
        return []
    values = strategy_info.get(key)
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())
