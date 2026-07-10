from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import KgEdge, KgNode, MemoryChunk, SourceDocument
from app.services import claim_extraction, claims_store, embeddings, entity_resolution
from app.services.chunking import chunk_text as _boundary_chunks


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

    # Claims: atomic subject–predicate–object assertions with evidence, plus
    # conflict detection against everything already known about the subject.
    claim_subject = strategy_node or source_node
    extracted_claims = claim_extraction.extract_claims(
        subject_label=claim_subject.label,
        strategy_info=strategy_info,
        text=text,
    )
    persisted_claims = claims_store.persist_claims(
        db,
        user_id=user_id,
        subject_node=claim_subject,
        document_id=document.id,
        extracted=extracted_claims,
        chunk_ids=chunk_ids,
    )
    new_conflicts = claims_store.detect_conflicts_for_subject(
        db, user_id=user_id, subject_node_id=claim_subject.id
    )

    summary = {
        "chunk_count": len(chunk_ids),
        "node_count": len({node.id for node in learned_nodes}),
        "edge_count": len({edge.id for edge in learned_edges}),
        "strategy": strategy_node.label if strategy_node else None,
        "technical_count": len(_technical_nodes(technical_profile)),
        "claim_count": len({claim.id for claim in persisted_claims}),
        "new_conflicts": new_conflicts,
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

    _delete_claims_for_document(db, document_id=document_id, user_id=user_id)


def _delete_claims_for_document(db: Session, *, document_id: UUID, user_id: UUID) -> None:
    """Drop this document's claim evidence; remove any claim left with none, and
    conflicts referencing removed claims."""
    from app.models.domain import Claim, ClaimConflict, ClaimEvidence

    affected_claim_ids = set(
        db.scalars(
            select(ClaimEvidence.claim_id).where(
                ClaimEvidence.source_document_id == document_id
            )
        )
    )
    for evidence in db.scalars(
        select(ClaimEvidence).where(ClaimEvidence.source_document_id == document_id)
    ):
        db.delete(evidence)
    db.flush()

    for claim_id in affected_claim_ids:
        remaining = db.scalar(
            select(ClaimEvidence.id).where(ClaimEvidence.claim_id == claim_id)
        )
        if remaining is not None:
            continue
        for conflict in db.scalars(
            select(ClaimConflict).where(
                ClaimConflict.user_id == user_id,
                (ClaimConflict.claim_a_id == claim_id) | (ClaimConflict.claim_b_id == claim_id),
            )
        ):
            db.delete(conflict)
        claim = db.get(Claim, claim_id)
        if claim is not None:
            db.delete(claim)
    db.flush()


def _create_memory_chunks(
    db: Session,
    *,
    document: SourceDocument,
    user_id: UUID,
    text: str,
    tags: list[str],
    strategy_info: dict | None,
) -> list[UUID]:
    chunks = _boundary_chunks(text)
    if not chunks:
        chunks = _fallback_chunk(document.title)
    chunk_ids: list[UUID] = []
    for index, chunk in enumerate(chunks):
        embedding = embeddings.embed_text(chunk.text)
        memory_chunk = MemoryChunk(
            user_id=user_id,
            source_type="source_document",
            source_id=document.id,
            chunk_index=index,
            text=chunk.text,
            embedding=embedding,
            chunk_metadata={
                "source_title": document.title,
                "tags": tags,
                "strategy": _strategy_name(document.title, strategy_info),
                "embedding_provider": embeddings.settings.embedding_provider if embedding else None,
            },
            token_count=chunk.token_count,
        )
        db.add(memory_chunk)
        db.flush()
        chunk_ids.append(memory_chunk.id)
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
        return _merge_into_node(node, properties, confidence)

    # Concept nodes (no source_id) go through embedding-similarity resolution so
    # a synonym of an existing entity reuses its node instead of forking a
    # duplicate. Source nodes are unique per document and skip this.
    is_concept = not (source_table and source_id)
    label_embedding: list[float] | None = None
    if is_concept:
        label_embedding = entity_resolution.embed_label(label, node_type)
        resolution = entity_resolution.resolve_entity(
            db,
            user_id=user_id,
            node_type=node_type,
            label=label,
            label_embedding=label_embedding,
        )
        if resolution.node is not None:
            merged = _merge_into_node(resolution.node, properties, confidence)
            if resolution.node.label_embedding is None and label_embedding is not None:
                resolution.node.label_embedding = label_embedding
            if resolution.is_possible_duplicate:
                aka = set(merged.properties.get("aka", []))
                aka.add(label)
                merged.properties = {
                    **merged.properties,
                    "aka": sorted(aka),
                    "needs_dedupe_review": True,
                }
            return merged

    node = KgNode(
        user_id=user_id,
        node_type=node_type,
        source_table=source_table,
        source_id=source_id,
        label=label[:240],
        properties={**properties, "source_titles": _merge_source_titles(None, properties)},
        confidence=confidence,
        label_embedding=label_embedding,
        created_by="source_learning",
    )
    db.add(node)
    db.flush()
    return node


def _merge_into_node(node: KgNode, properties: dict, confidence: Decimal | None) -> KgNode:
    # Merge, don't overwrite: a shared node (tag/setup/technical/rule keyed by
    # label or resolved by similarity) can be supported by several sources.
    # Accumulate the set of contributing sources and keep the strongest
    # confidence so re-importing one document never erases what others established.
    merged = {**(node.properties or {}), **properties}
    merged["source_titles"] = _merge_source_titles(node.properties, properties)
    node.properties = merged
    node.confidence = _max_confidence(node.confidence, confidence)
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


def _fallback_chunk(title: str):
    """A document with no body still gets one chunk (its title) so it is
    retrievable and can anchor graph provenance."""
    from app.services.chunking import Chunk, estimate_tokens

    return [Chunk(text=title, token_count=estimate_tokens(title))]


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
