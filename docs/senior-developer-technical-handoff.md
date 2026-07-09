# Quant Labs Senior Developer Technical Handoff

This file is for a senior developer who has never seen Quant Labs before and
needs enough project context to implement a large feature correctly.

Read this first, then inspect the linked files for the exact implementation.
The project is moving quickly, so treat this document as a map of the current
architecture and invariants, not as a replacement for reading the code.

## Executive Summary

Quant Labs is a local-first AI trading intelligence OS. It combines a learning
vault, journal, trade log, paper-trading workflow, strategy recommendations,
routine generation, insights, and a visual Strategy Atlas.

The product thesis is that the trader's durable asset is not a chart or a
broker connection. It is the trader's memory graph: sources, rules, trades,
setups, emotions, routines, tags, outcomes, and evidence. TradingView, market
data, broker paper APIs, and AI providers should be adapters around that memory
system.

The MVP is research, journaling, strategy analysis, and paper-only
experimentation. Do not implement real-money autonomous trading without a new
safety design, explicit approval UX, broker-paper staging, audit logs, and hard
risk limits.

## Current Product Surface

The app currently supports:

- Vault imports from URLs/files, including richer arXiv paper handling.
- Local semantic extraction of trading technicals and optional cloud AI
  enrichment through provider routing.
- Persistent source learning into memory chunks, graph nodes, and graph edges.
- Journal entries with emotion, tags, and routine completion.
- Trade logging for equities, options, futures, crypto, and forex.
- Live quote lookup through a server-side market-data adapter.
- Live paper-trade placement from the ticket, open position marking, and closing
  at current quote.
- Account Guard for buying-power/collateral checks on open paper trades.
- Trade recommendations from learned strategy sources and trade history.
- Plain-English strategy evaluation with technical tags and journal logging.
- Optimal strategy synthesis from current knowledge-base contents.
- Routine tab that converts strategy rules into setup/execution/risk review
  guidance.
- Strategy Atlas galaxy view that connects sources, strategies, setups, tags,
  trades, symbols, states, and journal entries.
- Local-first persistence with API sync when available and localStorage queue
  replay when offline.

## Safety And Privacy Invariants

These are non-negotiable.

- The app is paper-first. Do not imply or implement live autonomous execution as
  an MVP behavior.
- AI outputs are decision support, not truth. Strategy recommendations must be
  treated as evidence-informed drafts, not guarantees.
- Cloud AI enrichment is opt-in. The default `AI_ENRICHMENT_MODE=local` keeps
  source text on the machine.
- User-supplied URLs go through SSRF validation before fetching.
- The current `x-user-id` header is a local-dev identity skeleton only. It is
  ignored unless `TRUST_USER_HEADER=true`.
- Any future broker integration should begin with broker paper accounts and
  require explicit user consent, risk checks, kill switches, and audit logs.
- Paper-trade realism matters. Respect buying-power/collateral checks and
  contract multipliers.
- Never commit credentials, `.env`, private trading records, or exported
  browser data.

## Fast Orientation

Start here:

| File | Why it matters |
| --- | --- |
| `README.md` | GitHub-facing overview and local run commands. |
| `docs/architecture.md` | Product thesis, build order, safety boundaries. |
| `docs/repository-map.md` | High-level file map. |
| `docs/environment.md` | Environment variables and secret handling. |
| `docs/handoff-ai-map-trade-log-2026-07-06.md` | Recent implementation history for AI, map, trade log, routine, and paper trading. |
| `apps/web/src/components/WorkspaceApp.tsx` | Main workspace UI and most derived state. |
| `apps/web/src/lib/api.ts` | Browser API client and DTO mapping. |
| `apps/web/src/lib/sync.ts` | Offline mutation queue and replay logic. |
| `apps/web/src/lib/types.ts` | Shared frontend domain types. |
| `apps/web/src/lib/tradeGuards.ts` | Paper account buying-power/collateral rules. |
| `services/api/app/api/v1/vault.py` | Vault import, AI router status, documents, journal routes. |
| `services/api/app/api/v1/trades.py` | Trade CRUD, quotes, recommendations, strategy evaluation. |
| `services/api/app/models/domain.py` | SQLAlchemy database model definitions. |
| `services/api/app/services/source_learning.py` | Source-to-memory-chunks and graph projection. |
| `services/api/app/services/technical_extraction.py` | Local technical tag/profile extraction. |
| `services/api/app/services/trade_recommendations.py` | Source-backed recommendation generation. |
| `services/api/app/services/strategy_evaluation.py` | Plain-English strategy evaluation and optimal strategy synthesis. |
| `services/api/app/services/market_data.py` | Quote adapter and server-side quote cache. |

## Local Development

Full stack:

```bash
cp .env.example .env
docker compose up --build
```

Key local URLs:

- Web app: `http://localhost:3000`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- MinIO console: `http://localhost:9001`

Standalone API and web:

```bash
# API
cd services/api
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn app.main:app --port 8000

# Web, in another terminal
npm --prefix apps/web install
npm --prefix apps/web run dev
```

Useful checks:

```bash
# Web
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run test
npm --prefix apps/web run build

# API
cd services/api
ruff check app tests
pyright app
pytest

# PostgreSQL migration path
cd services/api
alembic upgrade head
python -m app.db.drift_check
```

## Runtime Architecture

```text
Browser / Next.js app
  |
  | localStorage workspace + offline sync queue
  |
  v
FastAPI API
  |
  | SQLAlchemy models and services
  |
  v
SQLite in standalone dev/test
PostgreSQL + pgvector in Docker/CI/production path

Optional local stack:
  Redis placeholder for future jobs/cache
  MinIO placeholder for vault uploads/reports
  Worker placeholder for future ingestion/backtests

External adapters:
  arXiv metadata/page import
  Yahoo chart quote adapter
  Optional AI providers: OpenRouter, Groq, Gemini, Cerebras
```

The frontend is intentionally local-first. When the API is online, it is the
source of truth. When offline, the UI remains usable through localStorage and a
durable mutation queue.

## Repository Structure

```text
apps/web
  Next.js app, React workspace, UI components, typed API client, local domain
  helpers, sync queue, analytics, CSV import, trade guards.

services/api
  FastAPI app, SQLAlchemy models, Pydantic schemas, REST routes, source
  extraction, graph learning, AI routing, recommendations, strategy evaluation,
  market data adapter, tests, Alembic migrations.

services/worker
  Placeholder worker service. Do not assume heavy background work is already
  implemented here.

infra/postgres
  Local Postgres/pgvector init.

docs
  Product/architecture/handoff/setup documentation.
```

## Frontend Architecture

### Main App

`apps/web/src/components/WorkspaceApp.tsx` is the main workspace. It currently
contains tabs, local state, API hydration, source import flows, journal entry
flows, trade ticket, paper-trade placement, routine generation, insights,
recommendation cards, and Strategy Atlas rendering.

Important state keys:

- `activeTab`: current tab (`vault`, `journal`, `trades`, `routine`, `insights`,
  `graph`).
- `state`: `WorkspaceState` with `vault`, `journal`, and `trades`.
- `hydrated`: prevents SSR/client localStorage mismatches.
- `apiOnline`: API health indicator.
- `syncNotice` and `pendingWrites`: offline queue status.
- `aiRouterStatus`: provider mode and configured providers.
- `tradeRecommendations`: source-backed paper-trade recommendations.
- `optimalStrategy`: synthesized best current strategy.
- `quoteBySymbol`: local quote cache for open paper marks.
- `strategyEvaluation`: plain-English strategy idea result.
- `paperAccountSize`: local account size used by Account Guard.
- `selectedGraphNodeId`, `graphMotionPaused`, `graphView`: Strategy Atlas
  interaction state.

Large derived models in `WorkspaceApp.tsx`:

- `viewState`: workspace data plus quote-marked open trades.
- `openPaperTrades`, `openPaperPnl`, `openPaperNotional`, `paperAccount`.
- `sourceStrategySignals`: normalized strategy evidence from vault sources.
- `strategyStats`: strategy scoreboard combining sources and trades.
- `recommendedRoutine`: routine/playbook derived from strategies, sources, and
  journal/trade context.
- `graph`: Strategy Atlas model built from workspace state.

For a heavy feature, prefer moving reusable logic into `apps/web/src/lib/*` or
smaller components instead of making `WorkspaceApp.tsx` larger unless the change
is directly UI orchestration.

### Frontend Domain Types

Defined in `apps/web/src/lib/types.ts`.

Core types:

- `VaultItem`: local vault record with source details, technical tags, strategy
  info, and learning summary.
- `JournalEntry`: date, emotion, routine completion, body, tags.
- `TradeEntry`: local trade shape with asset class, quote metadata, option and
  futures fields, risk fields, strategy/setup/emotion/notes.
- `TradeRecommendation`: source-backed recommendation plus trade draft.
- `StrategyEvaluation`: idea/optimal-strategy evaluation and trade draft.
- `WorkspaceState`: `{ vault, journal, trades }`.

If a feature adds durable data, update:

1. Backend SQLAlchemy model and migration if persisted.
2. Backend Pydantic schema.
3. Frontend `types.ts`.
4. `api.ts` DTO mapping.
5. Sync queue types if offline mutation support is required.
6. Tests and docs.

### API Client

`apps/web/src/lib/api.ts` maps API DTOs to frontend domain types.

Important details:

- `ApiError` distinguishes server rejection from network failure.
- Network failure or 5xx means retryable/offline.
- 4xx server rejection should be surfaced, not silently queued forever.
- Trade metadata carries many fields not first-class in backend columns:
  strategy, setup, notes, status, quote provider/time/symbol, order type, option
  params, futures params, leverage, and `timeResolution`.
- Client UUIDs are sent for trades so offline replay is idempotent.
- The frontend works with numbers/strings while the API often uses Decimal
  strings. Preserve conversion carefully.

### Offline Sync

`apps/web/src/lib/sync.ts` defines the durable mutation queue.

Supported collections:

- `trades`
- `journal`
- `vault`

Supported mutation types:

- create
- update
- delete

Behavior:

- Mutations are optimistically applied to local UI state.
- If the API cannot be reached, the mutation is queued in localStorage.
- On API recovery, queued ops replay in order before the UI hydrates from the
  server.
- Retryable failures keep the remaining queue.
- Permanent server rejections are dropped and surfaced.
- A 409 on idempotent replay is a benign duplicate.

If a heavy feature adds a new persisted collection, decide whether it must be
offline-first. If yes, extend `SyncCollection`, `SyncOp`, `SyncHandlers`,
dispatch, local state, and merge-pending logic.

### Paper Account Guard

`apps/web/src/lib/tradeGuards.ts` enforces paper-trade realism:

- Long equities/crypto reserve notional plus fees.
- Long options reserve premium times multiplier.
- Covered calls reserve 100 underlying shares per contract.
- Cash-secured puts reserve strike/reference times 100 per contract.
- Naked short calls are blocked.
- Options and futures require whole contract quantities.
- Existing open trades reduce buying power.

`WorkspaceApp.tsx` calls the guard before:

- quick-trade open logs
- structured manual open logs
- live paper trade placement

Closed historical trades are allowed because they are records, not new open risk.

Any future order-placement feature must use the same guard or a stricter server
equivalent. Do not create a new path that bypasses buying-power checks.

## Backend Architecture

### App Entry

`services/api/app/main.py` creates the FastAPI app, adds CORS, initializes DB for
SQLite dev/test, and includes `/api/v1` routers.

The current identity system is temporary:

- `services/api/app/core/security.py`
- `DEMO_USER_ID = 00000000-0000-0000-0000-000000000001`
- `x-user-id` is only trusted when `TRUST_USER_HEADER=true`.
- Non-local deployment must ignore caller-controlled user ids until real auth
  exists.

### Database Models

Defined in `services/api/app/models/domain.py`.

Key tables:

- `users`: placeholder user table.
- `source_documents`: vault documents, content, and metadata.
- `journal_entries`: journal records, emotions, tags, metadata.
- `trades`: trade records, open/closed status via nullable `exit_price`,
  contract multiplier, P&L, risk fields, journal summary, metadata.
- `taxonomy_items`: future taxonomy support.
- `kg_nodes`: knowledge graph nodes.
- `kg_edges`: knowledge graph edges with evidence chunk ids.
- `memory_chunks`: chunked source memory with optional embeddings.

Postgres uses Alembic migrations. SQLite dev/test uses `init_db()` and an
idempotent `_SQLITE_ADDED_COLUMNS` patch path for columns added after initial
create.

If adding persisted columns:

1. Update `models/domain.py`.
2. Add Alembic migration under `services/api/migrations/versions`.
3. Update SQLite patch path if the column must appear in existing local SQLite
   dev databases.
4. Update Pydantic schemas.
5. Update frontend DTO mapping if surfaced in UI.
6. Add tests and run drift check against Postgres.

### API Routes

Base API router: `services/api/app/api/v1/router.py`.

Vault routes in `vault.py`:

- `GET /api/v1/vault/ai/providers`
- `GET /api/v1/vault/ai/providers/self-test`
- `POST /api/v1/vault/import-url`
- `POST /api/v1/vault/import-file`
- `POST /api/v1/vault/documents`
- `GET /api/v1/vault/documents`
- `PATCH /api/v1/vault/documents/{document_id}`
- `DELETE /api/v1/vault/documents/{document_id}`
- `POST /api/v1/vault/journal-entries`
- `GET /api/v1/vault/journal-entries`
- `PATCH /api/v1/vault/journal-entries/{entry_id}`
- `DELETE /api/v1/vault/journal-entries/{entry_id}`

Trade routes in `trades.py`:

- `POST /api/v1/trades`
- `GET /api/v1/trades`
- `GET /api/v1/trades/quotes/{symbol}`
- `GET /api/v1/trades/recommendations`
- `GET /api/v1/trades/strategy/optimal`
- `POST /api/v1/trades/strategy/evaluate`
- `PATCH /api/v1/trades/{trade_id}`
- `DELETE /api/v1/trades/{trade_id}`

Graph routes:

- `POST /api/v1/graph/nodes`
- `GET /api/v1/graph/nodes`
- `POST /api/v1/graph/edges`
- `GET /api/v1/graph/edges`

Taxonomy routes:

- `POST /api/v1/taxonomy/items`
- `GET /api/v1/taxonomy/items`

### Vault Import And Learning Flow

High-level import flow:

```text
User submits URL/file
  -> vault.py import-url/import-file
  -> safe fetch or file read
  -> arXiv-specific parser if arXiv URL
  -> generic bytes/html/text importer
  -> local semantic extraction and optional AI enrichment
  -> frontend saves returned import as SourceDocument
  -> create_document stores SourceDocument
  -> learn_from_source_document creates memory chunks + graph nodes/edges
  -> document metadata gets learned_memory summary
  -> frontend displays source details, tags, strategy info, learning summary
```

Important implementation points:

- `safe_fetch.py` rejects loopback, LAN, link-local, metadata, and bad schemes.
- arXiv PDF URLs are converted to metadata-rich paper records where possible.
- Local semantic extraction is deterministic and always available.
- Cloud AI extraction only runs in `AI_ENRICHMENT_MODE=auto` with provider keys.
- Saved source edits re-run learning after deleting old learning artifacts.
- Deleting a source deletes its source-specific memory chunks and graph links.

### Technical Extraction

`services/api/app/services/technical_extraction.py` defines local pattern-based
technical extraction.

Current categories:

- indicators
- price_action
- market_structure
- setups
- risk
- sessions
- markets
- timeframes

The functions return:

- `extract_technical_profile(text)`: category -> labels
- `technical_tags_from_profile(profile)`: normalized tags
- `extract_technical_tags(text)`: combined tags
- `is_technical_tag(value)`: known technical tag check

If a feature depends on technical tags, prefer extending this service and the
frontend's matching extraction vocabulary together.

### Source Learning And Graph

`services/api/app/services/source_learning.py` turns a saved source into memory:

- chunks content into `memory_chunks`
- creates or reuses a `source` graph node
- creates a `strategy` node when strategy evidence exists
- creates `setup`, strategy attribute, technical, rule, and tag nodes
- creates edges such as `supports_strategy`, `has_setup`, `uses_technical`,
  `defines_rule`, and `tagged_as`
- stores a `learned_memory` summary in source metadata

Shared graph nodes should accumulate provenance. Tests currently cover this:
the same tag from multiple sources should remember all contributing source
titles rather than last-write-wins.

### AI Router

`services/api/app/services/ai_router.py` handles optional cloud extraction.

Providers:

- OpenRouter
- Groq
- Gemini
- Cerebras

Mode:

- `local`: deterministic local extraction, default
- `auto`: try configured providers in `AI_PROVIDER_ORDER`
- `off`: no AI enrichment

Provider self-test endpoint exists so setup problems are visible:

```text
GET /api/v1/vault/ai/providers/self-test
```

If a heavy feature sends private text to a provider, it must honor this opt-in
model and document what leaves the machine.

### Market Data

`services/api/app/services/market_data.py` is the quote adapter.

Current provider:

- Yahoo chart endpoint, delayed, no API key.

Behavior:

- normalizes symbols
- maps aliases such as `ES -> ES=F`, `BTC -> BTC-USD`
- caches quotes for `QUOTE_CACHE_TTL_SECONDS` (default 20)
- serves stale cache up to `QUOTE_STALE_MAX_SECONDS` (default 900) if upstream
  fails
- marks stale quotes with `stale=True`

The adapter is intentionally isolated. Replace or extend it for broker quotes,
dedicated market data, options chains, futures chains, or historical bars.

### Trades And P&L

Trade persistence is in `services/api/app/api/v1/trades.py`.

Important:

- `exit_price = null` means open trade.
- P&L is computed server-side when possible.
- P&L uses `contract_multiplier`.
- Short direction is handled by multiplying by `-1`.
- PATCH must not clobber manually supplied P&L unless `pnl_amount` is explicitly
  present.
- Client-supplied UUIDs support offline replay.

Current P&L formula:

```text
(exit_price - entry_price) * quantity * contract_multiplier * direction - fees
```

Frontend also computes live display P&L for open paper positions using current
marks. Keep server and frontend formulas aligned when adding instruments.

### Recommendations And Strategy Evaluation

`services/api/app/services/trade_recommendations.py` builds source-backed paper
recommendations:

- filters source documents for strategy info or technical tags
- avoids turning generic bare articles into trade recommendations
- matches learned sources against related trade history
- weights confidence by source confidence, related trades, and P&L
- emits recommendation cards and draft trade inputs

`services/api/app/services/strategy_evaluation.py` handles:

- `evaluate_strategy_idea`
- `build_optimal_strategy`
- `evaluation_journal_body`

Evaluation uses:

- local technical extraction from the idea
- matched learned sources
- related trade history
- average related P&L
- losing conflicts
- quote-backed entry/exit draft when available

It returns:

- title
- decision (`beneficial`, `observe`, `needs-structure`, `weakens-edge`)
- score and confidence
- rationale
- technical tags/profile
- included and excluded evidence
- trade draft

When `save_journal=true`, the API writes the evaluation into the journal.

## UI Tabs And Feature Areas

### Vault

Primary jobs:

- import URL/file
- show title/source/body/tags
- show source details such as paper metadata
- show concise technical tags/profile
- show strategy info and learned memory summary
- support edit/delete

Main files:

- `WorkspaceApp.tsx`
- `api.ts`
- `vault.py`
- `source_learning.py`
- `technical_extraction.py`

### Journal

Primary jobs:

- log daily journal entries
- capture emotion/state, tags, routine completion
- feed Strategy Atlas and routine/insights calculations

Main files:

- `WorkspaceApp.tsx`
- `api.ts`
- `vault.py`

### Trades

Primary jobs:

- quick-trade parsing
- structured ticket for multiple asset classes
- live quote fill
- live paper trade placement
- open positions panel
- close at live quote
- Account Guard
- recommendation cards
- plain-English strategy evaluator
- collapsible trade history

Main files:

- `WorkspaceApp.tsx`
- `api.ts`
- `tradeGuards.ts`
- `trades.py`
- `market_data.py`
- `trade_recommendations.py`
- `strategy_evaluation.py`

### Routine

Primary jobs:

- generate recommended routine from learned strategies, source evidence, trades,
  and journal context
- show how to trade, setup criteria, execution timing, risk/review steps

Main file:

- `WorkspaceApp.tsx`, especially `buildRecommendedRoutine`

### Insights

Primary jobs:

- show strategy performance
- expose routine effects
- show state/setup leaks and validation gaps
- surface AI-router status

Main files:

- `WorkspaceApp.tsx`
- `apps/web/src/components/insights/PerformancePanel.tsx`
- `apps/web/src/lib/analytics.ts`

### Strategy Atlas

Primary jobs:

- visualize memory as a galaxy
- connect source, strategy, setup, trade, symbol, journal, state, and tag nodes
- support pan/zoom/recenter/focus
- drift nodes until selected
- pause motion when a node is selected

Main file:

- `WorkspaceApp.tsx`, especially `buildGraphModel`, graph rendering state, and
  node inspector helpers.

Note: the graph UI is named Strategy Atlas. Avoid copyright-sensitive naming
borrowed from other products.

## Testing And CI

### Web Tests

Current web tests:

- `apps/web/src/lib/analytics.test.ts`
- `apps/web/src/lib/csvImport.test.ts`
- `apps/web/src/lib/sync.test.ts`
- `apps/web/src/lib/tradeGuards.test.ts`

Run:

```bash
npm --prefix apps/web run test
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
```

### API Tests

Current API tests cover:

- health endpoint
- persistence
- pagination
- trade correctness
- vault import
- vault edit/relearning
- extraction quality
- recommendation quality
- graph integrity
- market cache/stale fallback
- AI router self-test
- SSRF and identity security

Run:

```bash
cd services/api
ruff check app tests
pyright app
pytest
```

### CI

`.github/workflows/ci.yml` has three jobs:

- API lint/type/test on Python 3.12.
- API Postgres migration + drift check using pgvector Postgres.
- Web lint/type/build/test on Node 22.

If a heavy feature changes persistence, CI must continue passing both SQLite
tests and Postgres migration/drift checks.

## Heavy Feature Implementation Playbook

Use this as the checklist for any large new feature.

### 1. Define The Feature Contract

Before coding, answer:

- What user workflow does this feature enable?
- Is it research-only, paper-trading, or broker-adjacent?
- What data must persist?
- Does it need offline support?
- Does it use external network calls?
- Does it send private source/journal/trade text to AI?
- Does it affect paper risk, buying power, or account state?
- What should happen when the API is offline?
- What should happen when a provider is down or rate-limited?
- What evidence should the feature cite?

### 2. Choose The Right Data Boundary

For ephemeral UI state:

- keep it in component state or a frontend lib
- no API migration needed

For durable user data:

- add backend model/schema/route/migration
- add frontend type and DTO mapping
- decide whether to support offline queue replay

For derived intelligence:

- prefer deterministic local/server services
- store provenance and source evidence
- keep generated text concise in UI and use read-more for detail

For external integrations:

- isolate provider-specific code behind an adapter
- add cache/fallback behavior where appropriate
- document required env vars
- add tests with mocked providers

### 3. Backend Steps

Typical backend sequence:

1. Add or extend SQLAlchemy models in `models/domain.py`.
2. Add Pydantic schemas under `schemas/`.
3. Add or extend route module under `api/v1/`.
4. Put domain logic in `services/`, not directly in route handlers.
5. Add Alembic migration.
6. Update SQLite compatibility path if needed.
7. Add tests.
8. Update docs and environment references.

Keep route handlers thin. They should validate identity, load data, call service
functions, persist, and return schemas.

### 4. Frontend Steps

Typical frontend sequence:

1. Add or extend domain types in `lib/types.ts`.
2. Add DTO mapping and API calls in `lib/api.ts`.
3. Add offline queue support in `lib/sync.ts` if durable/offline.
4. Add UI state and derived selectors.
5. Prefer new `lib/*` helpers and smaller components for complex logic.
6. Add guardrails for loading/error/empty/offline states.
7. Add tests for pure logic.
8. Verify layout at desktop and mobile widths if UI changes are substantial.

Avoid adding another large block to `WorkspaceApp.tsx` if the feature can be
cleanly isolated.

### 5. Trading And Risk Steps

If a feature can create, suggest, size, or execute a paper trade:

- validate asset class
- validate quantity and multiplier
- validate stop/target/risk
- run Account Guard or a stricter equivalent
- make sure options/futures semantics are correct
- keep recommendations as drafts until user confirms
- persist enough metadata to audit why the draft was created
- expose risk notes and excluded reasons
- do not silently place trades from AI output

### 6. AI Steps

If the feature uses AI:

- respect `AI_ENRICHMENT_MODE`
- local/default behavior must still work without provider keys
- include provider status/error transparency
- constrain outputs to schemas
- cite source chunks/trades/journal evidence where possible
- avoid long generated content in the UI
- record journal/audit entries for important AI decisions
- add tests for no-key/local mode and malformed provider output

### 7. Source And Graph Steps

If the feature adds source-derived knowledge:

- update technical extraction if new terms/categories are needed
- update source learning if new node/edge types are needed
- preserve provenance on shared nodes
- delete/relearn source-specific graph data when a source changes
- expose compact UI tags and read-more detail
- add graph integrity tests

### 8. Verification Steps

Minimum before handing off:

```bash
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run test

cd services/api
ruff check app tests
pyright app
pytest
```

If persistence changed:

```bash
cd services/api
alembic upgrade head
python -m app.db.drift_check
```

If UI changed:

- run the app locally
- verify the affected tab manually
- check empty, loading, error, and offline states
- ensure text does not overflow compact cards/buttons

## Common Failure Modes

Watch for these:

- Adding persisted fields only on the frontend and losing them on API round trip.
- Adding API fields but not updating `api.ts` DTO mapping.
- Breaking offline replay by introducing a mutation that is not queued.
- Treating every API error as offline instead of distinguishing 4xx from network
  failure.
- Computing options/futures P&L without contract multiplier.
- Creating a paper trade path that bypasses Account Guard.
- Letting AI cloud mode send private source text while mode is `local` or `off`.
- Turning generic reference articles into actionable trade recommendations.
- Making source edits without relearning graph/memory.
- Replacing shared graph-node provenance instead of accumulating it.
- Adding external URL fetches without SSRF checks.
- Adding Postgres-only schema without SQLite dev/test compatibility.
- Letting long generated content stretch cards instead of using read-more.
- Reintroducing copyright-sensitive map naming.

## Current Limitations And Roadmap Context

Current limitations:

- Knowledge graph is relationship/keyword based today. Embedding-based semantic
  search and GraphRAG chat are roadmap items.
- The worker service is mostly a placeholder.
- Quote data is delayed and provider-dependent.
- Broker integration is not implemented.
- AI enrichment is optional and only as strong as configured providers.
- Recommendations need stronger statistical validation and backtesting before
  high-confidence use.
- Authentication is not production-grade yet.

Roadmap direction:

- Embeddings and semantic search over sources, trades, and journals.
- GraphRAG chat with evidence citations.
- Strategy compiler and contradiction detection.
- Internal backtest and paper simulation lab.
- Provider mesh for market data and broker paper APIs.
- Autonomous paper-only agent with approvals and kill switches.
- Stronger reporting and review workflows.

## Glossary

- Learning Vault: saved sources such as papers, notes, links, screenshots, or
  strategy documents.
- SourceDocument: backend persisted vault item.
- VaultItem: frontend local representation of a source.
- Memory chunk: chunk of source text stored for retrieval/provenance.
- KgNode/KgEdge: graph entities linking sources, strategies, setups, tags,
  trades, and rules.
- Strategy Atlas: frontend graph/galaxy visualization.
- Account Guard: frontend paper-trading buying-power/collateral validator.
- AI Router: optional provider layer for source enrichment.
- Local semantic rules: deterministic technical extraction without cloud AI.
- Trade draft: suggested paper-trade form payload generated by recommendations
  or strategy evaluation.
- Open paper trade: trade with `exitPrice`/`exit_price` null.

## Final Advice For The Senior Developer

Do not start by adding code in the biggest file. Start by identifying the
feature's data contract and persistence boundary. Then add backend service logic
and tests, wire DTO mapping, and finally build the UI. The most important
project invariants are local-first sync, paper-trading safety, provenance, and
privacy. If the feature preserves those, it will fit the project. If it bypasses
any of them, it will probably create regressions that are hard to see in the UI.
