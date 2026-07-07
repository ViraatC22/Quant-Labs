from __future__ import annotations

from decimal import Decimal

from app.models.domain import SourceDocument, Trade
from app.schemas.trades import TradeRecommendationRead
from app.services.technical_extraction import (
    extract_technical_tags,
    is_technical_tag,
    technical_tags_from_profile,
)


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

    risk_notes = [_excerpt(note, 150) for note in risk_rules[:2]]

    return TradeRecommendationRead(
        id=f"recommend-{source.id}",
        title=setup or strategy_name,
        action=action,
        strategy=strategy_name,
        setup=setup,
        confidence=round(confidence, 2),
        technical_tags=technical_tags[:14],
        rationale=_excerpt(_rationale(source.title, entry_rules, exit_rules, related_trades), 220),
        risk_notes=risk_notes or ["Define invalidation and max risk before taking this setup."],
        evidence=evidence,
        draft=_trade_draft(
            source=source,
            strategy_name=strategy_name,
            setup=setup,
            technical_tags=technical_tags,
            related_trades=related_trades,
        ),
    )


def _action(
    *,
    strategy_name: str,
    setup: str | None,
    related_trades: list[Trade],
    total_pnl: Decimal,
) -> str:
    label = _excerpt(setup or strategy_name, 72)
    if not related_trades:
        return f"Paper-trade {label} with tiny size until it has a journaled sample."
    if total_pnl > 0:
        return f"Favor {label} only when the source rules and current technical tags align."
    if total_pnl < 0:
        return f"Do not size up {label}; review losing examples before the next attempt."
    return f"Keep {label} in observation mode until the edge is clearer."


def _trade_draft(
    *,
    source: SourceDocument,
    strategy_name: str,
    setup: str | None,
    technical_tags: list[str],
    related_trades: list[Trade],
) -> dict:
    selected_setup = setup or _setup_from_tags(technical_tags)
    symbol = _common_trade_value(related_trades, "symbol") or _symbol_from_source(
        source,
        technical_tags,
    )
    side = _common_trade_value(related_trades, "side") or _side_from_tags(technical_tags)
    notes = _draft_notes(source, selected_setup, technical_tags)
    return {
        "symbol": symbol,
        "side": side,
        "strategy": strategy_name,
        "setup": selected_setup,
        "emotion": "patient",
        "quantity": "1",
        "fees": "0",
        "notes": notes,
        "quick_text": (
            f"{symbol} {side} entry [price] exit [price] qty 1 "
            f"strategy {strategy_name} setup {selected_setup} notes {notes}"
        ),
    }


def _setup_from_tags(tags: list[str]) -> str:
    tag_text = " ".join(tags)
    priorities = [
        ("opening-range-breakout", "Opening range breakout"),
        ("vwap-pullback", "VWAP pullback"),
        ("mean-reversion", "Mean reversion"),
        ("trend-following", "Trend following"),
        ("risk-parity", "Risk parity"),
        ("momentum", "Momentum"),
        ("breakout", "Breakout"),
        ("macd", "MACD momentum"),
        ("moving-average", "Moving average trend"),
    ]
    for needle, label in priorities:
        if needle in tag_text:
            return label
    return "Source-backed setup"


def _common_trade_value(trades: list[Trade], attr: str) -> str | None:
    counts: dict[str, int] = {}
    for trade in trades:
        value = str(getattr(trade, attr, "")).strip()
        if value:
            counts[value] = counts.get(value, 0) + 1
    if not counts:
        return None
    return sorted(counts.items(), key=lambda item: item[1], reverse=True)[0][0]


def _symbol_from_source(source: SourceDocument, tags: list[str]) -> str:
    text = f"{source.title} {source.content_text or ''} {' '.join(tags)}".lower()
    if any(value in text for value in ["futures", "cme", "cross-asset"]):
        return "ES"
    if "crypto" in text or "btc" in text:
        return "BTC"
    if "forex" in text or "fx" in text:
        return "EURUSD"
    return "SPY"


def _side_from_tags(tags: list[str]) -> str:
    tag_text = " ".join(tags)
    if any(value in tag_text for value in ["fade", "breakdown", "short"]):
        return "short"
    return "long"


def _draft_notes(source: SourceDocument, setup: str, tags: list[str]) -> str:
    metadata = source.source_metadata or {}
    details = metadata.get("source_details")
    notes: list[str] = []
    if isinstance(details, dict):
        notes.extend(
            str(note).strip()
            for note in details.get("implementation_notes", [])
            if str(note).strip()
        )
    if not notes:
        strategy_info = _strategy_info(source) or {}
        notes.extend(_rules(strategy_info, "entry_rules")[:1])
    tag_summary = ", ".join(tag for tag in tags[:5] if ":" not in tag)
    base = _excerpt(notes[0], 150) if notes else f"Use {setup} only when source conditions align."
    return f"{base} Tags: {tag_summary}.".strip()


def _excerpt(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit].rsplit(' ', 1)[0]}..."


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

    tags.update(
        extract_technical_tags(
            " ".join([source.title, source.document_type, source.content_text or ""])
        )
    )

    for value in [
        *(metadata.get("technical_tags") or []),
        *(strategy_info.get("technical_tags") or []),
    ]:
        if str(value).strip():
            tags.add(str(value).strip().lower())

    for value in [
        *(metadata.get("tags") or []),
        *(metadata.get("generated_tags") or []),
        *(metadata.get("aiTags") or []),
    ]:
        if str(value).strip() and is_technical_tag(str(value)):
            tags.add(str(value).strip().lower())

    for profile in [
        metadata.get("technical_profile"),
        strategy_info.get("technical_profile"),
    ]:
        if isinstance(profile, dict):
            tags.update(technical_tags_from_profile(profile))
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
