# Trading Intelligence OS Architecture

## Product Thesis

The durable product is the trader's personal memory graph: trades, mistakes,
routines, research, strategy rules, market regimes, journal entries, and paper
experiments with provenance. TradingView, Alpaca, market-data APIs, and MCP
servers are adapters around that memory system.

## Build Order

1. Learning Vault: documents, notes, journal entries, screenshots, CSV imports,
   strategy documents, tags, and provenance.
2. Knowledge Graph + Vector Memory: semantic search, source chunks, graph nodes,
   graph edges, and evidence links.
3. GraphRAG Chat: evidence-backed answers over trades, routines, research,
   strategies, and graph context.
4. Strategy Compiler: source ingestion, rule extraction, contradictions, and
   personalized strategy drafts.
5. Backtest + Paper Lab: internal simulator, strategy variants, overfitting
   checks, paper experiments.
6. Provider Mesh + Integrations: API provider router, TradingView webhook
   adapter, Alpaca paper adapter, read-only MCP tools.
7. Autonomous Paper Agent: paper-only shadow trader with approvals, risk limits,
   audit logs, and kill switches.

## Phase 0 Stack

```text
apps/web          Next.js + TypeScript + Tailwind app shell
services/api      FastAPI + Pydantic + SQLAlchemy API
services/worker   Async job placeholder for ingestion/extraction/backtests
infra/postgres    Local Postgres + pgvector initialization
docker-compose    Postgres, Redis, MinIO, API, worker, web
```

## Safety Boundaries

- The MVP is a trading journal, research assistant, and paper simulation tool.
- No live autonomous trading in the MVP.
- Every AI-created claim or strategy rule must eventually link back to source
  chunks, user trades, backtests, or paper experiments.
- Missing external credentials must create setup requests instead of silent
  failures.
- Provider routing must improve reliability, not evade terms, quotas, or rate
  limits.

## Grounded Research Layer (Lattice merge)

The knowledge graph is now backed by a retrieval + grounded-answer stack (see
[`lattice-merge-plan.md`](lattice-merge-plan.md) for the full plan). Shipped:

- **Embeddings & semantic search.** Chunks and claims carry embeddings
  (`app/services/embeddings.py`). The default `local` provider is deterministic
  and needs no network; `ollama`/`openai` are opt-in. Vector search is
  brute-force cosine in Python so it is identical on SQLite and Postgres.
- **Claims layer.** `claims` / `claim_evidence` / `claim_conflicts` store atomic
  assertions with per-source evidence, powering trust scores, conflict
  detection, and the temporal claim view.
- **Entity resolution.** New concept nodes are matched to existing ones by
  label-embedding similarity before a duplicate is created.
- **Router → Retriever → Writer.** `app/services/research/` classifies a
  question, retrieves graph + text + claim evidence, and composes a cited answer
  with a measured trust score, refusing when evidence is absent.
- **Read-only MCP server.** `services/mcp` exposes search/ask/entity/conflict
  tools to other assistants.

### Scale posture (deferred decisions & their triggers)

These were adapted from Lattice's stack to Quant Labs' local-first, single-user
reality. Each is a decision with an explicit trigger, not an omission:

- **Graph store: Postgres, not Neo4j.** All graph access is funnelled through a
  small set of service functions so a `GraphStore` adapter could swap in.
  *Revisit if* 3-hop retrieval p95 exceeds ~500ms at real data volume.
- **Vector index: pgvector, not ChromaDB.** One database, transactional
  consistency between a chunk, its embedding, and the edges citing it. An HNSW
  index exists for a future native `<=>` query path.
- **Worker coordination: Redis job leases, not gRPC.** Adopt the coordinator–
  worker *semantics* (heartbeats, dead-worker reassignment, replay-safe writes)
  without a second transport. *Revisit if* workers become multi-machine.
- **Graph sharding: not built.** Solves a multi-tenant, multi-million-node
  problem this product does not have. Effectively never for single-user.
