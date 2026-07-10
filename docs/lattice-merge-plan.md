# Lattice → Quant Labs: Comprehensive Merging Plan

**Date:** 2026-07-10
**Source project:** *Lattice: A Knowledge-Graph Engine for Grounded, Relationship-Aware Research* (Rebanto Nath) — analyzed from the project poster.
**Target project:** Quant Labs — Trading Intelligence OS (`apps/web` Next.js, `services/api` FastAPI, `services/worker`, Postgres + pgvector, Redis, MinIO).
**Relationship to existing docs:** This plan *extends* `docs/evaluation-and-implementation-plan-v3.md` (referred to below as **v3**). Where a Lattice capability overlaps a v3 task, this plan absorbs it and says so explicitly, so the two documents never compete.

---

## Implementation status (2026-07-10)

A first vertical slice of the core is **implemented, tested, and verified end to
end** (67 API tests green, ruff + pyright clean, web typecheck/lint clean, UI
driven in a browser). Shipped in this pass:

- **L-1 (partial):** boundary-aware overlapping chunking + real token counts
  (`app/services/chunking.py`); provider-abstracted embeddings, local default
  (`app/services/embeddings.py`), wired into source learning. *Not yet:* the
  arq/Redis job system with heartbeats — learning still runs inline.
- **L-2 (core):** embedding-similarity entity resolution
  (`app/services/entity_resolution.py`); deterministic claim extraction with
  clause-level polarity (`app/services/claim_extraction.py`); claims persisted
  with evidence (`app/services/claims_store.py`); unique indexes on concept
  nodes, edge triples, and claim tuples. *Not yet:* LLM extractor (fallback path
  is in place behind the same return shape).
- **Claims layer (Part 3):** `claims`, `claim_evidence`, `claim_conflicts`,
  `research_conversations` tables + migration `20260710_0003`.
- **L-3 (core):** router → hybrid retriever → grounded writer with trust score
  (`app/services/research/`), `POST /research/ask`, `GET /research/search`,
  conversation history, and the `/research` web page (`features/research/`).
- **L-4 (core):** conflict detection between opposing sources;
  `GET /research/conflicts`, `PATCH /research/conflicts/{id}`, claim timeline.
- **L-5 (API):** `GET /graph/neighborhood/{id}` and `GET /graph/search`. *Not
  yet:* the Atlas UI wiring.
- **L-6:** read-only MCP server (`services/mcp`) with five tools.

**Deferred (planned, not built here):** the async job system with heartbeats
(L-1.1), LLM entity/claim extractor (L-2.1), feed monitoring (L-4.3), Atlas
explorer UI (L-5 frontend), `GraphStore` protocol extraction (L-7), special
answer-element renderers (L-8), and workspaces / multi-agent mode (L-9). The
phase docs below remain the roadmap for those.

> Local embeddings are lexical-semantic (hashed n-grams + a trading synonym
> map), not neural — they make the pipeline run offline and hermetically. Set
> `EMBEDDING_PROVIDER=ollama` for full semantic embeddings.

---

## Part 0 — What Lattice is (feature inventory from the poster)

Lattice is a web app that answers hard research questions about any subject and shows its work. Every capability on the poster, enumerated so nothing is missed:

| # | Lattice capability | Poster section |
|---|---|---|
| L1 | Ingest arbitrary sources: research papers (arXiv), RSS/news feeds, web pages, user PDFs | Introduction / Architecture |
| L2 | Ingestion pipeline: fetch → split into **overlapping chunks** → **embed** → **LLM entity/relationship extraction** | System Architecture |
| L3 | **Entity resolution**: new entities matched against existing ones by embedding similarity so one thing never becomes two nodes | System Architecture |
| L4 | Facts written to **both** the knowledge graph and the vector index, each **tagged with the asserting source** | System Architecture |
| L5 | **Query router**: connection questions → knowledge graph; content questions → text search; hybrid questions → both, reconciled | How It Works |
| L6 | **Writer**: composes answers from retrieved facts only — every fact cited, the LLM never answers from memory | How It Works / Key Features |
| L7 | **Trust score**: what share of the answer is backed by retrieved evidence | Key Features |
| L8 | **Conflict detection**: when two sources disagree about the same claim, the contradiction is flagged side by side | Key Features |
| L9 | **Interactive graph explorer**: entities and their links on a live map | Key Features |
| L10 | **MCP server**: other assistants use the knowledge base as tools | Key Features |
| L11 | **Coordinator–worker ingestion** over gRPC with heartbeats; dead worker's batch automatically reassigned | Scale |
| L12 | **Replay-safe (idempotent) writes** — every write is safe to repeat | Scale |
| L13 | **Graph sharding** across several databases by hashing entity names, transparently re-joined at query time | Scale |
| L14 | **Special elements in query results**: stat tiles, timelines, structured visual blocks rendered inside answers | Screenshot panel |
| L15 | **Multi-agent research mode** and **self-correcting queries** | Conclusion |
| L16 | *Future:* source monitoring — surface when a new document reinforces/contradicts an existing claim | Future Directions |
| L17 | *Future:* turn detected gaps into concrete research questions | Future Directions |
| L18 | *Future:* temporal view tracking how support for a claim shifts over time | Future Directions |
| L19 | *Future:* linked workspaces so cross-field connections become visible | Future Directions |
| L20 | *Future:* extend MCP support to more assistants/agent frameworks | Future Directions |

**Lattice stack:** TypeScript, Python, FastAPI, gRPC, Neo4j, PostgreSQL, Redis, ChromaDB, Hugging Face, Docker.

---

## Part 1 — Where Quant Labs already stands, feature by feature

| Lattice | Quant Labs today | Gap |
|---|---|---|
| L1 ingestion of papers/pages/PDFs | ✅ Partial — `vault.py` imports URLs, arXiv (Atom + abs-page fallback), files; no RSS/feed *monitoring* | Feeds/watching missing (→ L16) |
| L2 chunk/embed/extract pipeline | ⚠️ Chunks exist (`source_learning.py`, fixed 1600-char slices, no overlap); **embeddings are always `None`** (v3 A3); extraction is regex + optional single LLM call for `strategy_info` | Overlapping boundary-aware chunks, real embeddings, LLM entity/relationship extraction |
| L3 entity resolution | ❌ Exact label match only (`_get_or_create_node`); "FVG" vs "fair value gap" become two nodes | Embedding-similarity entity matching |
| L4 dual-store facts w/ source tag | ⚠️ Graph edges carry `evidence_chunk_ids` and merged `source_titles` (good!); no vector index; no per-fact claim records | A first-class `claims` layer + vector index |
| L5 query router | ❌ No question-answering path at all (v3 5.1 is the placeholder) | Build it |
| L6 grounded writer w/ citations | ❌ | Build it |
| L7 trust score | ⚠️ Confidence columns exist on nodes/edges but are keyword-count arithmetic (v3 A12) | Real evidence-coverage scoring |
| L8 conflict detection | ❌ | Build it |
| L9 interactive graph | ✅ Partial — Strategy Atlas galaxy in `WorkspaceApp.tsx` (animated, freeze-on-select) | Add neighborhood expansion, edge/evidence inspection, claim overlays |
| L10 MCP server | ❌ (v3 5.8 planned) | Build it |
| L11 coordinator–worker ingestion | ❌ Worker is a `time.sleep(5)` loop (v3 A2) | Real job system w/ heartbeats + reassignment |
| L12 replay-safe writes | ⚠️ Client sync queue is idempotent via client UUIDs; server graph writes have **no unique constraints** (v3 A4) | Upserts + unique indexes everywhere the pipeline writes |
| L13 graph sharding | ❌ (single Postgres) | Deliberately deferred — see Part 2 decisions |
| L14 special answer elements | ❌ | Build with the chat UI |
| L15 multi-agent / self-correcting queries | ❌ | Late phase |
| L16 source monitoring / reinforce–contradict alerts | ❌ | Build on L8 + feeds |
| L17 gaps → research questions | ⚠️ "Validation gaps" insight cards exist (heuristic) | Upgrade to graph-derived gap detection |
| L18 temporal claim support | ❌ | Build on claims layer |
| L19 linked workspaces | ❌ Single implicit workspace per user | Workspace model |
| L20 broader MCP/agent support | ❌ | After L10 |

**Existing assets the merge builds on (do not replace):**
- `KgNode` / `KgEdge` / `MemoryChunk` models with provenance columns already in place ([domain.py](services/api/app/models/domain.py))
- pgvector 1536-dim `embedding` column already provisioned
- Merge-not-overwrite node/edge accumulation already implemented in [source_learning.py](services/api/app/services/source_learning.py)
- AI provider router with fallback order ([ai_router.py](services/api/app/services/ai_router.py))
- Redis + worker containers already in `docker-compose.yml`
- Offline-first client sync queue with idempotent client UUIDs

---

## Part 2 — Architecture decisions (adopt the concept, adapt the tech)

Lattice's *concepts* transfer; three of its *technology choices* should be adapted to Quant Labs' local-first, single-user reality. Each decision below states the recommendation, the rationale, and the escape hatch if scale demands the literal Lattice choice later.

### D1. Graph store: Postgres (`kg_nodes`/`kg_edges`) — not Neo4j
**Recommendation:** Keep the graph in Postgres.
**Why:** The graph tables, Alembic migrations, provenance columns, and drift-check CI already exist. A personal trading graph is thousands of nodes, not millions; recursive CTEs handle 2–3-hop traversals fine at that scale. Adding Neo4j doubles the operational surface (backup, auth, drift) of a local-first app for zero user-visible gain.
**Escape hatch:** Phase L-7 defines a `GraphStore` protocol so a Neo4j adapter can be swapped in behind the same interface if multi-hop query latency ever becomes real.

### D2. Vector index: pgvector — not ChromaDB
**Recommendation:** Use the pgvector column that already exists on `memory_chunks`; add an HNSW index. SQLite dev path uses brute-force cosine (fine at personal scale, matches v3 4.1).
**Why:** One database, transactional consistency between a chunk, its embedding, and the graph edges citing it — which Lattice needs two systems and careful ordering to guarantee.

### D3. Worker coordination: Redis job queue with heartbeats — not gRPC
**Recommendation:** Implement Lattice's coordinator–worker *semantics* (heartbeats, lease/reassignment of dead workers' batches, replay-safe writes) on **arq/RQ over the existing Redis**, absorbing v3 2.2.
**Why:** gRPC earns its keep when workers are separate deployables on separate machines. Here the coordinator is the API process and workers are one container; Redis delivers the same guarantees (job leases with TTL heartbeats, atomic requeue on expiry) with a fraction of the code. The *properties* on the poster — "if a worker dies mid-job its batch is reassigned; every write is safe to repeat" — are requirements in this plan's acceptance criteria, independent of transport.
**Escape hatch:** the job payload schema is defined as plain dataclasses/Pydantic; a gRPC transport could carry the same messages later.

### D4. Graph sharding (L13): explicitly deferred
Hash-sharding entities across databases solves a multi-tenant, multi-million-node problem Quant Labs does not have. **Do not build it.** What we *do* keep from L13 is its precondition: all graph access goes through one `GraphStore` interface (Phase L-7), so sharding remains a pure infrastructure change if ever needed. Documented here so the deferral is a decision, not an omission.

### D5. Embedding model: local-first
Default to a local embedding model via Ollama (`nomic-embed-text`, 768-dim) per v3 4.1, with optional cloud embedding providers through the existing AI router pattern. **Schema note:** the provisioned column is `vector(1536)`; migration in Phase L-1 changes it to the chosen dimension (or adds a `model` + `dim` discriminator) before any embeddings are written — cheap now, painful later.

### D6. Domain mapping: "research entities" → "trading entities"
Lattice extracts people/papers/organizations/ideas. Quant Labs' entity ontology is already defined and keeps working: `source, strategy, setup, indicator, market, timeframe, rule, technical, tag, trade, symbol`. The LLM extraction prompt (Phase L-2) targets this ontology **plus** free-form entities (`person`, `organization`, `concept`) so imported papers still yield author/institution/idea nodes like Lattice.

---

## Part 3 — New core concept: the Claims layer

Almost half of Lattice (L4, L7, L8, L16, L17, L18) rests on one primitive Quant Labs lacks: a **claim** — an atomic factual statement extracted from a source, linked to the graph and to its evidence. This is the single most important schema addition.

```
claims
  id              UUID PK
  user_id         UUID          (index)
  workspace_id    UUID NULL     (Phase L-9)
  subject_node_id UUID FK kg_nodes
  predicate       TEXT          e.g. "works_best_in", "requires", "contradicts_when"
  object_node_id  UUID NULL FK kg_nodes   (nullable: claim may be about a literal)
  object_literal  TEXT NULL
  statement_text  TEXT          normalized natural-language form of the claim
  embedding       vector        (for conflict detection & dedupe)
  polarity        TEXT          "supports" | "refutes" | "neutral"
  confidence      NUMERIC
  created_at / updated_at

claim_evidence
  id              UUID PK
  claim_id        UUID FK claims
  source_document_id UUID FK source_documents
  chunk_id        UUID FK memory_chunks
  stance          TEXT          "supports" | "contradicts"
  quote           TEXT          the extracted span
  asserted_at     TIMESTAMPTZ   (when the source asserted it → powers L18 temporal view)

claim_conflicts
  id              UUID PK
  claim_a_id / claim_b_id  UUID FK claims
  detected_at     TIMESTAMPTZ
  status          TEXT          "open" | "resolved" | "dismissed"
  resolution_note TEXT NULL
```

- **L4** is satisfied because every claim row is tagged with its asserting source(s) via `claim_evidence`.
- **L7** trust score = share of answer sentences whose citations resolve to claim evidence.
- **L8** conflict detection = same subject+predicate (or high claim-embedding similarity) with opposing polarity/values.
- **L16** monitoring = on every new ingestion, match new claims against existing ones → reinforce (add evidence row) or contradict (open conflict).
- **L18** temporal view = `claim_evidence.asserted_at` timeline per claim.

Unique constraint: `(user_id, subject_node_id, predicate, coalesce(object_node_id), md5(coalesce(object_literal,'')))` with upsert — this is also the L12 replay-safety guarantee for pipeline writes.

---

## Part 4 — The phased implementation plan

Ordering respects dependencies and slots between/after v3 phases: **v3 Phases 0–3 (guardrails, correctness, backend arch, frontend decomposition) remain prerequisites** — especially 2.1 (service extraction), 2.2 (async pipeline, absorbed by L-1 here), 2.6 (graph integrity/unique constraints), and 3.1 (feature folders, so the new Research UI doesn't land in `WorkspaceApp.tsx`).

Effort estimates assume one developer; L-phases marked ∥ can parallelize.

### Phase L-1 — Real ingestion pipeline (absorbs v3 2.2, 4.1, 4.2) — ≈ 2 weeks

The Lattice ingestion shape (L2, L11, L12) on the existing stack.

1. **Job system.** arq (or RQ) on the existing Redis. Job types: `ingest_document`, `embed_chunks`, `extract_entities`, `extract_claims`, `resolve_conflicts`, `monitor_feeds`. Each job carries an idempotency key; workers renew a heartbeat key (`job:{id}:lease`, TTL 30s); a coordinator sweep (periodic task) requeues jobs whose lease expired. Replace the sleep-loop in [services/worker/app/main.py](services/worker/app/main.py) with the arq worker entrypoint.
   *AC:* kill the worker container mid-ingestion → job is re-run by a fresh worker within 60s → final DB state identical to an uninterrupted run (replay-safe, L11+L12).
2. **Boundary-aware overlapping chunking.** Sentence/paragraph-aware splitter, ~1,000 chars with ~15% overlap, real token counts. Re-chunk on demand via a `reindex_document` job.
3. **Embeddings, actually.** Embed every chunk (D5); write to pgvector; HNSW index migration; brute-force cosine fallback on SQLite. Backfill job for all existing chunks.
   *AC (from v3):* searching "liquidity sweep before London open" returns relevant chunks sharing no exact keywords.
4. **Import returns fast.** `POST /vault/import-url` responds < 2s with `enrichment_status: pending`; pipeline stages update `source_metadata.pipeline` (`fetched → chunked → embedded → extracted → learned`); UI shows a per-source pipeline status chip.
5. **Migration for embedding dimension** (D5) before any vectors are written.

### Phase L-2 — LLM entity & claim extraction + entity resolution — ≈ 2 weeks

The heart of Lattice's graph construction (L2-extraction, L3, L4).

1. **Entity/relationship extraction job.** For each chunk (batched), an AI-router call with a structured-output prompt extracts: entities (type from the D6 ontology + free-form types), relationships (typed edges with the supporting quote), and **claims** (subject, predicate, object/literal, polarity, quote). Deterministic local fallback = the current regex extraction, so `AI_ENRICHMENT_MODE=local` still produces a (coarser) graph — preserving the local-first default.
2. **Claims schema.** The Part 3 tables via Alembic; every extracted claim upserted with evidence rows.
3. **Entity resolution (L3).** New entity → embed its label+type → nearest-neighbor search over existing node-label embeddings (new `kg_nodes.label_embedding` column) → above threshold (~0.88 cosine) merge into the existing node (accumulate `source_titles`, keep max confidence — the merge machinery in `source_learning.py` already does this for exact matches); below threshold create a node; mid-band (0.80–0.88) create + record a `possible_duplicate_of` edge for later review.
   *AC:* importing one source saying "FVG" and another saying "fair value gap" yields **one** indicator node with both sources in provenance.
4. **Unique constraints + upserts** on `kg_nodes(user_id, node_type, label)` and `kg_edges(user_id, edge_type, from_node_id, to_node_id)` (absorbs v3 2.6; completes L12 on the server side).
5. **Extraction quality tests** extend `test_extraction_quality.py`: golden-file tests over 3–4 fixture documents (an arXiv abstract, a strategy write-up, a news page) asserting minimum entity/claim recall and zero duplicate nodes.

### Phase L-3 — Router → Retriever → Writer: grounded Q&A (absorbs v3 4.4 + 5.1) — ≈ 3 weeks

Lattice's answer path (L5, L6, L7), pointed at trading memory. This becomes the **"Ask my memory"** feature v3 5.1 promised.

1. **Router.** `services/api/app/services/research/router.py` — classifies a question as `connection` / `content` / `hybrid` / `analytics`. First implementation: small-LLM call with deterministic keyword fallback (patterns like "how is X related to Y" → connection; "what does source Z say" → content). `analytics` routes to existing computed stats (win rate, expectancy) so numeric questions use real trade math, not retrieval — a Quant-Labs-specific fourth branch Lattice doesn't need.
2. **Graph retriever.** Entity linking of question terms → node lookup (via label embeddings from L-2) → k-hop neighborhood expansion (recursive CTE, depth ≤ 3) → collect edges, claims, and their evidence chunks.
3. **Text retriever.** Hybrid vector + keyword search over `memory_chunks` (also over trades/journal text per v3 4.3). Reciprocal-rank-fusion merge for hybrid questions — Lattice's "run both and reconcile."
4. **Writer.** Answer composed **only** from retrieved facts. Prompt contract: every sentence must cite `[chunk:id]` / `[claim:id]` / `[trade:id]`; if evidence is insufficient, say so and list what's missing (feeds L17). Post-generation validation strips or flags uncited sentences.
5. **Trust score (L7).** `trust = cited_sentences_resolving_to_real_evidence / total_sentences`, displayed on every answer with a breakdown (n chunks, n claims, n sources). This replaces synthetic confidence with measured coverage — directly answering v3 A12's "fabricated precision" critique.
6. **API.** `POST /research/ask` → `{answer_markdown, citations[], trust_score, route, retrieved{nodes,edges,claims,chunks}, special_elements[]}`. Conversation persistence table for history.
7. **Web UI.** New `features/research/` folder (respecting v3 rule: nothing new in `WorkspaceApp.tsx`): question box, streaming answer, citation chips that open the source/chunk in the vault, trust-score meter, "show retrieved subgraph" toggle that highlights the answer's nodes in the Atlas.
   *AC:* a question with no supporting sources returns "no evidence" rather than a fluent hallucination; every citation chip resolves to a real chunk; trust score is 0 for an answer with no citations.

### Phase L-4 — Conflict detection & source monitoring (L8, L16, L18) — ≈ 2 weeks

1. **Conflict detection job.** After each ingestion's claims land: candidate pairs = same subject+predicate, or claim-embedding cosine > 0.85; LLM verdict (`agree / disagree / unrelated`, local heuristic fallback = opposing polarity on same subject+predicate); disagreements → `claim_conflicts` rows.
2. **Side-by-side conflict UI.** Vault "Conflicts" panel: claim A vs claim B, each with source, quote, and date; resolve/dismiss actions. The writer (L-3) must surface open conflicts inline: "Note: sources disagree — [A] says X, [B] says Y."
3. **Feed monitoring (L16).** `watched_sources` table (arXiv queries, RSS URLs — reuses the SSRF-guarded fetcher from v3 1.7); scheduled `monitor_feeds` job diffs new items, auto-ingests, then reports "new document reinforces/contradicts N existing claims" as a dashboard insight card.
4. **Temporal claim view (L18).** Per-claim timeline of `claim_evidence.asserted_at` with stance — "support for this claim over time" sparkline in the claim inspector.
   *AC:* importing two fixture docs with opposing statements about the same setup produces exactly one open conflict, visible in UI and mentioned by the writer when asked about that setup.

### Phase L-5 — Interactive graph explorer upgrade (L9) — ≈ 1.5 weeks ∥

The Strategy Atlas galaxy stays as ambience; add Lattice-style investigation:

1. Click node → neighborhood expansion (fetch k-hop, `GET /graph/neighborhood/{node_id}?depth=`), lazily growing the visible graph instead of rendering everything.
2. Edge inspector: edge type, confidence, evidence chunks (click-through to source text), contributing sources.
3. Claim overlay: nodes with open conflicts get a badge; toggle to color edges by evidence count.
4. Search-to-focus: ⌘K (v3 4.3) result can center the Atlas on a node.
5. Server: paginated/scoped graph endpoints replace the current fetch-everything `GET /graph/nodes` + `/edges` ([graph.py](services/api/app/api/v1/graph.py)).

### Phase L-6 — MCP server (L10, absorbs v3 5.8) — ≈ 1 week ∥

Read-only MCP server (`services/mcp/`, FastMCP over stdio first, HTTP later) exposing:
- `search_memory(query)` → hybrid retrieval (L-3.3)
- `ask_research(question)` → full router/writer answer with citations + trust score
- `get_entity(name)` / `get_neighborhood(name, depth)`
- `list_conflicts(status)`
- `get_trades(filters)` / `get_performance_stats()`
Read-only, local transport, single-user token. *AC:* Claude Code configured against it answers "which of my setups have conflicting evidence?" with real citations. (L20 — additional assistants/frameworks — is configuration once the server exists.)

### Phase L-7 — `GraphStore` interface & scale posture (L11–L13 closure) — ≈ 1 week

1. Extract all direct `KgNode`/`KgEdge`/`claims` SQL behind a `GraphStore` protocol (`get_or_create_node`, `upsert_edge`, `neighborhood`, `upsert_claim`, `find_conflicting_claims`, `entity_search`). Postgres implementation is the only one shipped.
2. Document (in `docs/architecture.md`) the deferred decisions D1/D3/D4 with their triggers: Neo4j if 3-hop p95 > 500ms at real data volume; gRPC/multi-machine workers if ingestion backlog exceeds single-worker throughput; sharding effectively never for single-user.
3. Load-test fixture: script that generates 50k nodes / 200k edges / 100k chunks and records retrieval latencies, so the triggers are measurable rather than vibes.

### Phase L-8 — Special answer elements & research UX polish (L14) — ≈ 1 week ∥

The poster screenshot shows answers containing stat tiles and timelines. Writer output gains typed blocks the UI renders natively:
- `stat_row` (e.g. "Total passages: 8 · First mention: 1950" → for us: "n trades matched: 14 · win rate: 64% · avg R: 1.3")
- `timeline` (evolution of a claim/strategy across sources/dates — reuses L-4.4 data)
- `conflict_callout`, `entity_card`, `citation_list`
Schema: `special_elements[]` in the `/research/ask` response; renderer components in `features/research/elements/`. Analytics-routed questions (L-3.1) should *default* to `stat_row` output.

### Phase L-9 — Workspaces & multi-agent research (L15, L17, L19) — ≈ 3 weeks, last

1. **Workspaces (L19).** `workspaces` table; `workspace_id` on documents/nodes/edges/claims/chunks (nullable → default workspace backfill). UI switcher. **Linked workspaces:** queries can opt into a workspace set; entity resolution runs within each workspace, plus a cross-workspace "same entity" link job so connections spanning fields (e.g. a *macro research* workspace and a *futures strategies* workspace) become visible without merging them.
2. **Gap → research questions (L17).** Job that inspects the graph for structural gaps — strategies with entry rules but no risk rules, claims with single-source evidence, setups with zero linked trades, mid-band duplicate candidates — and emits concrete queued questions ("Only one source supports 'ORB works in chop' — find corroborating or contradicting evidence"). Surfaced as a "Research queue" panel; one click either asks the question (L-3) or opens a watched-source suggestion (L-4.3).
3. **Multi-agent research mode + self-correcting queries (L15).** For a hard question: planner decomposes into sub-questions → each runs the full router/retriever/writer path → a reconciler composes the final answer, re-querying when sub-answers conflict or trust < threshold (the "self-correcting" loop: a low-trust draft triggers reformulated retrieval before the answer is shown). Budget-capped (max sub-queries, max provider calls) through the existing AI router. This is deliberately last: it is only as good as the retrieval and claims layers under it.

---

## Part 5 — Consolidated schema & API delta

**New tables:** `claims`, `claim_evidence`, `claim_conflicts`, `watched_sources`, `research_conversations`, `workspaces` (+ `workspace_id` columns).
**Altered:** `memory_chunks.embedding` dimension (D5) + HNSW index; `kg_nodes.label_embedding`; unique indexes on `kg_nodes` / `kg_edges`; pipeline status in `source_metadata`.

**New API surface:**
```
POST /research/ask                     L-3   grounded Q&A
GET  /research/conversations[...]      L-3
GET  /graph/neighborhood/{node_id}     L-5
GET  /graph/search?q=                  L-5
GET  /claims / /claims/{id}/timeline   L-4
GET/POST /claims/conflicts[...]        L-4
GET/POST /vault/watched-sources        L-4
GET  /search?q=                        L-1/L-3 (v3 4.3)
GET  /research/queue                   L-9 gap-derived questions
MCP  services/mcp (6 read-only tools)  L-6
```

**New env vars:** `EMBEDDING_PROVIDER` (ollama|openai|…), `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `OLLAMA_BASE_URL`, `RESEARCH_MAX_SUBQUERIES`, `CONFLICT_SIM_THRESHOLD`, `ENTITY_MATCH_THRESHOLD`, `FEED_POLL_INTERVAL_MINUTES` — all documented in `docs/environment.md` and `.env.example` in the same PR that introduces them.

---

## Part 6 — Sequencing, risks, and rules

### Sequencing (with v3 interleaved)

| Order | Phase | Depends on | Est. |
|---|---|---|---|
| 1 | v3 0–1 (guardrails, correctness) | — | 3 wks |
| 2 | v3 2.1/2.3–2.5 + **L-1** (L-1 replaces v3 2.2) | v3 0–1 | 3 wks |
| 3 | **L-2** (extraction + resolution; replaces v3 2.6) | L-1 | 2 wks |
| 4 | **L-3** (router/writer; replaces v3 4.3–4.4, 5.1) ∥ v3 3 (frontend decomp) | L-2 | 3 wks |
| 5 | **L-4** (conflicts + monitoring) | L-2, L-3 | 2 wks |
| 6 | **L-5** (graph explorer) ∥ **L-6** (MCP) ∥ **L-8** (elements) | L-3/L-4 | 2 wks combined |
| 7 | **L-7** (GraphStore + scale posture) | L-2..L-5 | 1 wk |
| 8 | **L-9** (workspaces, research queue, multi-agent) | everything | 3 wks |

v3 Phase 5 items untouched by Lattice (broker CSV import 5.2, risk dashboard 5.3, review autopilot 5.4, TradingView webhook 5.5, regime tagging 5.6, checklist gate 5.7, screenshots 5.9, flashcards 5.10, backtest lab 5.11, weekly report 5.12) keep their v3 ordering and can interleave after step 5.

### Top risks

1. **Extraction quality is the whole product.** A noisy entity/claim extractor poisons the graph, the router, conflicts, and trust scores simultaneously. Mitigation: golden-file extraction tests from day one (L-2.5), mid-band duplicate review queue instead of silent merges, and per-source "re-extract" action so prompt improvements are retroactively applicable.
2. **Local-first vs. LLM-hungry pipeline.** Entity/claim extraction per chunk is many LLM calls. Mitigation: batch chunks per call, cache by chunk hash, keep the deterministic fallback ontology extraction, and make cloud extraction opt-in exactly like today's `AI_ENRICHMENT_MODE`.
3. **Scope gravity.** L-9 multi-agent mode is demo-candy that tempts early building. It is gated last on purpose; the acceptance criteria for L-3 (refuse without evidence) deliver Lattice's core promise ("can't make things up") long before agents do.
4. **Two plans drifting.** Any future re-scoping edits **this file and v3 in the same PR**.

### Rules carried over (and extended) from v3

1. Nothing new lands in `WorkspaceApp.tsx` — research UI goes in `features/research/`.
2. Docs may not claim capabilities the code doesn't ship — the README's current "GraphRAG is a roadmap item" wording stays accurate until L-3 merges, then flips.
3. Every pipeline write is replay-safe (unique key + upsert) — this is now an acceptance criterion on *every* L-phase, honoring L12.
4. Every AI-produced statement shown to the user must carry a citation or an explicit "heuristic" label — Lattice's core discipline, applied to a trading product where trust is literally money.
