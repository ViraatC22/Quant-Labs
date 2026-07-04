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
