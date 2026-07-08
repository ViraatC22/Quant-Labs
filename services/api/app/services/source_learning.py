from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import KgEdge, KgNode, MemoryChunk, SourceDocument

MAX_CHUNK_CHARS = 1600


def learn_from_source_document(
    db: Session,
    *,
    document: SourceDocument,
    user_id: UUID,
) -> dict:
    text = document.content_text or ""
    metadata = document.source_metadata or {}
    tags = _metadata_tags(metadata)
    strategy_info = _strategy_info(metadata)
    technical_profile = _technical_profile(metadata, strategy_info)
    chunk_ids = _create_memory_chunks(
        db,
        document=document,
        user_id=user_id,
        text=text,
        tags=tags,
        strategy_info=strategy_info,
    )
    learned_nodes: list[KgNode] = []
    learned_edges: list[KgEdge] = []

    source_node = _get_or_create_node(
        db,
        user_id=user_id,
        node_type="source",
        label=document.title,
        source_table="source_documents",
        source_id=document.id,
        properties={
            "document_type": document.document_type,
            "uri": document.uri,
            "tags": tags,
            "technical_profile": technical_profile,
            "excerpt": text[:360],
        },
        confidence=Decimal("1.0"),
    )
    learned_nodes.append(source_node)

    strategy_node: KgNode | None = None
    if strategy_info or document.document_type == "strategy" or "strategy" in tags:
        strategy_name = _strategy_name(document.title, strategy_info)
        strategy_node = _get_or_create_node(
            db,
            user_id=user_id,
            node_type="strategy",
            label=strategy_name,
            properties={
                "summary": strategy_info.get("summary") if strategy_info else None,
                "setup": strategy_info.get("setup") if strategy_info else None,
                "entry_rules": strategy_info.get("entry_rules", []) if strategy_info else [],
                "exit_rules": strategy_info.get("exit_rules", []) if strategy_info else [],
                "risk_rules": strategy_info.get("risk_rules", []) if strategy_info else [],
                "technical_tags": strategy_info.get("technical_tags", []) if strategy_info else [],
                "technical_profile": technical_profile,
                "source_title": document.title,
            },
            confidence=_confidence(strategy_info),
        )
        learned_nodes.append(strategy_node)
        learned_edges.append(
            _get_or_create_edge(
                db,
                user_id=user_id,
                edge_type="supports_strategy",
                from_node=source_node,
                to_node=strategy_node,
                evidence_chunk_ids=chunk_ids[:3],
                confidence=_confidence(strategy_info),
            )
        )

    if strategy_info and strategy_node:
        setup = strategy_info.get("setup")
        if isinstance(setup, str) and setup.strip():
            setup_node = _get_or_create_node(
                db,
                user_id=user_id,
                node_type="setup",
                label=setup.strip(),
                properties={"source_title": document.title},
                confidence=_confidence(strategy_info),
            )
            learned_nodes.append(setup_node)
            learned_edges.append(
                _get_or_create_edge(
                    db,
                    user_id=user_id,
                    edge_type="has_setup",
                    from_node=strategy_node,
                    to_node=setup_node,
                    evidence_chunk_ids=chunk_ids[:2],
                    confidence=_confidence(strategy_info),
                )
            )

        for attribute in _strategy_attributes(strategy_info):
            attribute_node = _get_or_create_node(
                db,
                user_id=user_id,
                node_type=attribute["type"],
                label=attribute["label"],
                properties={"source_title": document.title},
                confidence=_confidence(strategy_info),
            )
            learned_nodes.append(attribute_node)
            learned_edges.append(
                _get_or_create_edge(
                    db,
                    user_id=user_id,
                    edge_type=f"uses_{attribute['type']}",
                    from_node=strategy_node,
                    to_node=attribute_node,
                    evidence_chunk_ids=chunk_ids[:2],
                    confidence=_confidence(strategy_info),
                )
            )

        for technical in _technical_nodes(technical_profile):
            technical_node = _get_or_create_node(
                db,
                user_id=user_id,
                node_type="technical",
                label=technical["label"],
                properties={"category": technical["category"], "source_title": document.title},
                confidence=_confidence(strategy_info),
            )
            learned_nodes.append(technical_node)
            learned_edges.append(
                _get_or_create_edge(
                    db,
                    user_id=user_id,
                    edge_type="uses_technical",
                    from_node=strategy_node,
                    to_node=technical_node,
                    evidence_chunk_ids=chunk_ids[:2],
                    confidence=_confidence(strategy_info),
                )
            )

        for rule in _strategy_rules(strategy_info):
            rule_node = _get_or_create_node(
                db,
                user_id=user_id,
                node_type="rule",
                label=rule[:240],
                properties={"source_title": document.title},
                confidence=_confidence(strategy_info),
            )
            learned_nodes.append(rule_node)
            learned_edges.append(
                _get_or_create_edge(
                    db,
                    user_id=user_id,
                    edge_type="defines_rule",
                    from_node=strategy_node,
                    to_node=rule_node,
                    evidence_chunk_ids=chunk_ids[:2],
                    confidence=_confidence(strategy_info),
                )
            )

    for tag in tags:
        tag_node = _get_or_create_node(
            db,
            user_id=user_id,
            node_type="tag",
            label=tag,
            properties={"source_title": document.title},
            confidence=Decimal("0.75"),
        )
        learned_nodes.append(tag_node)
        learned_edges.append(
            _get_or_create_edge(
                db,
                user_id=user_id,
                edge_type="tagged_as",
                from_node=source_node,
                to_node=tag_node,
                evidence_chunk_ids=chunk_ids[:1],
                confidence=Decimal("0.75"),
            )
        )

    summary = {
        "chunk_count": len(chunk_ids),
        "node_count": len({node.id for node in learned_nodes}),
        "edge_count": len({edge.id for edge in learned_edges}),
        "strategy": strategy_node.label if strategy_node else None,
        "technical_count": len(_technical_nodes(technical_profile)),
        "map_labels": sorted({node.label for node in learned_nodes})[:24],
        "status": "learned",
    }
    document.source_metadata = {**metadata, "learned_memory": summary}
    db.flush()
    return summary


def delete_source_learning(db: Session, *, document_id: UUID, user_id: UUID) -> None:
    chunk_ids = list(
        db.scalars(
            select(MemoryChunk.id).where(
                MemoryChunk.user_id == user_id,
                MemoryChunk.source_type == "source_document",
                MemoryChunk.source_id == document_id,
            )
        )
    )
    source_node_ids = list(
        db.scalars(
            select(KgNode.id).where(
                KgNode.user_id == user_id,
                KgNode.source_table == "source_documents",
                KgNode.source_id == document_id,
            )
        )
    )
    if source_node_ids:
        for edge in db.scalars(
            select(KgEdge).where(
                KgEdge.user_id == user_id,
                (KgEdge.from_node_id.in_(source_node_ids) | KgEdge.to_node_id.in_(source_node_ids)),
            )
        ):
            db.delete(edge)
        for node in db.scalars(select(KgNode).where(KgNode.id.in_(source_node_ids))):
            db.delete(node)

    if chunk_ids:
        for chunk in db.scalars(select(MemoryChunk).where(MemoryChunk.id.in_(chunk_ids))):
            db.delete(chunk)


def _create_memory_chunks(
    db: Session,
    *,
    document: SourceDocument,
    user_id: UUID,
    text: str,
    tags: list[str],
    strategy_info: dict | None,
) -> list[UUID]:
    chunks = _chunk_text(text) or [document.title]
    chunk_ids: list[UUID] = []
    for index, chunk_text in enumerate(chunks):
        chunk = MemoryChunk(
            user_id=user_id,
            source_type="source_document",
            source_id=document.id,
            chunk_index=index,
            text=chunk_text,
            embedding=None,
            chunk_metadata={
                "source_title": document.title,
                "tags": tags,
                "strategy": _strategy_name(document.title, strategy_info),
            },
            token_count=len(chunk_text.split()),
        )
        db.add(chunk)
        db.flush()
        chunk_ids.append(chunk.id)
    return chunk_ids


def _get_or_create_node(
    db: Session,
    *,
    user_id: UUID,
    node_type: str,
    label: str,
    properties: dict,
    confidence: Decimal,
    source_table: str | None = None,
    source_id: UUID | None = None,
) -> KgNode:
    query = select(KgNode).where(
        KgNode.user_id == user_id,
        KgNode.node_type == node_type,
        KgNode.label == label,
    )
    if source_table and source_id:
        query = query.where(KgNode.source_table == source_table, KgNode.source_id == source_id)
    node = db.scalar(query)
    if node:
        # Merge, don't overwrite: a shared node (tag/setup/technical/rule keyed
        # by label) can be supported by several sources. Accumulate the set of
        # contributing sources and keep the strongest confidence so re-importing
        # one document never erases what the others established.
        merged = {**(node.properties or {}), **properties}
        merged["source_titles"] = _merge_source_titles(node.properties, properties)
        node.properties = merged
        node.confidence = _max_confidence(node.confidence, confidence)
        return node

    node = KgNode(
        user_id=user_id,
        node_type=node_type,
        source_table=source_table,
        source_id=source_id,
        label=label[:240],
        properties={**properties, "source_titles": _merge_source_titles(None, properties)},
        confidence=confidence,
        created_by="source_learning",
    )
    db.add(node)
    db.flush()
    return node


def _get_or_create_edge(
    db: Session,
    *,
    user_id: UUID,
    edge_type: str,
    from_node: KgNode,
    to_node: KgNode,
    evidence_chunk_ids: list[UUID],
    confidence: Decimal,
) -> KgEdge:
    edge = db.scalar(
        select(KgEdge).where(
            KgEdge.user_id == user_id,
            KgEdge.edge_type == edge_type,
            KgEdge.from_node_id == from_node.id,
            KgEdge.to_node_id == to_node.id,
        )
    )
    if edge:
        # Accumulate evidence across sources instead of replacing it, so an edge
        # supported by multiple documents keeps every provenance chunk.
        combined = list(edge.evidence_chunk_ids or [])
        for chunk_id in evidence_chunk_ids:
            if chunk_id not in combined:
                combined.append(chunk_id)
        edge.evidence_chunk_ids = combined[:24]
        edge.confidence = _max_confidence(edge.confidence, confidence)
        edge.properties = {"source": "source_learning"}
        return edge

    edge = KgEdge(
        user_id=user_id,
        edge_type=edge_type,
        from_node_id=from_node.id,
        to_node_id=to_node.id,
        properties={"source": "source_learning"},
        confidence=confidence,
        evidence_chunk_ids=evidence_chunk_ids,
        created_by="source_learning",
    )
    db.add(edge)
    db.flush()
    return edge


def _merge_source_titles(existing: dict | None, incoming: dict) -> list[str]:
    titles: set[str] = set()
    for blob in (existing or {}, incoming or {}):
        for title in blob.get("source_titles", []) or []:
            if str(title).strip():
                titles.add(str(title).strip())
        single = blob.get("source_title")
        if isinstance(single, str) and single.strip():
            titles.add(single.strip())
    return sorted(titles)


def _max_confidence(current: Decimal | None, incoming: Decimal | None) -> Decimal | None:
    values = [value for value in (current, incoming) if value is not None]
    return max(values) if values else None


def _chunk_text(text: str) -> list[str]:
    compact = " ".join(text.split())
    if not compact:
        return []
    return [
        compact[index : index + MAX_CHUNK_CHARS].strip()
        for index in range(0, len(compact), MAX_CHUNK_CHARS)
        if compact[index : index + MAX_CHUNK_CHARS].strip()
    ]


def _metadata_tags(metadata: dict) -> list[str]:
    return sorted(
        {
            str(tag).strip().lower()
            for tag in [
                *(metadata.get("tags") or []),
                *(metadata.get("aiTags") or []),
                *(metadata.get("generated_tags") or []),
                *(metadata.get("technical_tags") or []),
            ]
            if str(tag).strip()
        }
    )


def _strategy_info(metadata: dict) -> dict | None:
    value = metadata.get("strategyInfo") or metadata.get("strategy_info")
    return value if isinstance(value, dict) else None


def _technical_profile(metadata: dict, strategy_info: dict | None) -> dict[str, list[str]]:
    profile: dict[str, list[str]] = {}
    sources = (
        metadata.get("technical_profile"),
        (strategy_info or {}).get("technical_profile"),
    )
    for source in sources:
        if not isinstance(source, dict):
            continue
        for category, labels in source.items():
            if not isinstance(labels, list):
                continue
            profile[category] = sorted(
                {
                    *profile.get(category, []),
                    *[str(label).strip() for label in labels if str(label).strip()],
                }
            )
    return profile


def _strategy_name(title: str, strategy_info: dict | None) -> str:
    if not strategy_info:
        return title
    name = strategy_info.get("name") or strategy_info.get("setup") or title
    return str(name).strip() or title


def _confidence(strategy_info: dict | None) -> Decimal:
    if not strategy_info:
        return Decimal("0.65")
    try:
        return Decimal(str(strategy_info.get("confidence", 0.65))).quantize(Decimal("0.0001"))
    except Exception:
        return Decimal("0.65")


def _strategy_attributes(strategy_info: dict) -> list[dict[str, str]]:
    attributes: list[dict[str, str]] = []
    for indicator in strategy_info.get("indicators") or []:
        if str(indicator).strip():
            attributes.append({"type": "indicator", "label": str(indicator).strip()})
    for key in ("market", "timeframe"):
        value = strategy_info.get(key)
        if isinstance(value, str) and value.strip():
            attributes.append({"type": key, "label": value.strip()})
    return attributes


def _technical_nodes(profile: dict[str, list[str]]) -> list[dict[str, str]]:
    nodes: list[dict[str, str]] = []
    for category, labels in profile.items():
        for label in labels:
            if label.strip():
                nodes.append({"category": category, "label": label.strip()})
    return nodes


def _strategy_rules(strategy_info: dict) -> list[str]:
    rules: list[str] = []
    for key in ("entry_rules", "exit_rules", "risk_rules"):
        for rule in strategy_info.get(key) or []:
            if str(rule).strip():
                rules.append(str(rule).strip())
    return rules[:12]
