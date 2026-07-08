# Quant Labs — Project Evaluation & Implementation Plan v3

**Date:** 2026-07-08
**Scope:** Full-repo review of `apps/web`, `services/api`, `services/worker`, infra, CI, and docs.
**Audience:** Development team. Every finding cites the file so you can jump straight to it.
**Supersedes nothing:** `docs/implementation-plan-v2.md` remains the product vision; this document is the engineering audit and the corrective/expansion plan.

---

## Part 1 — What is genuinely good (keep these)

Before the criticism: several decisions are right and should survive the refactor.

- **Local-first with a zero-dependency dev path.** SQLite fallback (`services/api/app/core/config.py`) means the API runs with nothing installed. Keep this.
- **Provenance thinking.** `KgEdge.evidence_chunk_ids`, confidence columns, and the "every AI claim links back to evidence" rule in `docs/architecture.md` are the correct core thesis. The product's moat is the memory graph, not the adapters — this framing is right.
- **Opt-in cloud AI.** `AI_ENRICHMENT_MODE=local` by default protects private trading notes. Correct default.
- **Safety boundary: paper-only.** No live trading in the MVP. Keep it a hard boundary.
- **Test isolation.** `tests/conftest.py` pointing tests at a temp SQLite DB before app import is done correctly.
- **Docs discipline.** The docs folder is unusually complete for a project at this stage. `SETUP_REQUESTS.md` protocol is a good idea.
- **Clean Pydantic schema layer** and a real Alembic setup for Postgres.

---

## Part 2 — Critical defects (correctness & data integrity)

These are bugs, not style issues. They are ordered by severity. **Phase 1 of the plan fixes all of them.**

### C1. The "offline fallback" silently destroys data
`WorkspaceApp.tsx` → `persistCreate()` (~line 1720):

```ts
try { stored = await create(local); } catch { setApiOnline(false); }
```

Any error — including an HTTP 400/422 validation rejection — flips the whole app into "offline" mode. From then on every record is saved only to `localStorage`. On the next page load, if the API is reachable, `load()` (~line 1099) sets state **entirely from the server**, discarding everything created during the "offline" window. There is no outbound sync queue, no dirty flag, no reconciliation. The offline-first promise is currently a data-loss mechanism.

**Fix:** distinguish network failure (offline) from server rejection (surface the error to the user, keep the record in a retry queue). Maintain a persisted `pendingWrites` queue in localStorage; on reconnect, replay it before hydrating from the server; merge instead of overwrite.

### C2. Server P&L and client P&L disagree for futures/options
- Server: `_compute_pnl` in `services/api/app/api/v1/trades.py:98` = `(exit − entry) × quantity × direction − fees`. **No contract multiplier.**
- Client: `tradePnl` in `WorkspaceApp.tsx:570` multiplies by `tradeContractMultiplier` (option = 100, futures per-symbol).

The `pnl_amount` stored in the database is wrong for every non-equity trade, and any future server-side analytics will contradict the UI. `contractMultiplier` lives only in the untyped `metadata` JSON blob the server never reads.

**Fix:** promote `contract_multiplier` to a real column, compute P&L in exactly one place (server), and have the client display server values. Backfill existing rows.

### C3. Trade timestamps are fabricated
`apps/web/src/lib/api.ts:170` sends `entry_time: ${entryDate}T00:00:00Z` and sets `exit_time` to the *entry* date. Actual execution times are discarded. This silently poisons the product's own core value proposition: session analysis (`session`, `timeframe` columns), time-of-day insights, and any future regime tagging are built on midnight-UTC fiction.

**Fix:** capture real datetimes in the ticket (default = now), send them through, and render exit time from the server. Migration note: existing rows have date-resolution only — flag them (`metadata.time_resolution = "date"`).

### C4. PATCH /trades clobbers manually set P&L
`update_trade` (`trades.py:303`) does `trade.pnl_amount = payload.pnl_amount` unconditionally — omitting the field sets it to `None` and triggers recompute, discarding any explicitly recorded P&L (e.g. broker-adjusted numbers). Use `model_fields_set` to distinguish "omitted" from "null".

### C5. `side`, `asset_class`, and `status` are unvalidated free text
`TradeCreate.side` is `str` (`schemas/trades.py:13`). `_compute_pnl` treats anything ≠ `"long"` as short — a client sending `"Long"` silently computes inverted P&L. **Fix:** `Literal["long","short"]` / enums for side, asset_class, document kind, decision, etc., at the Pydantic layer, mirrored in shared TS types.

### C6. Dual camelCase/snake_case metadata is a standing bug factory
Every metadata blob is written twice (`strategyInfo` + `strategy_info`, `technicalTags` + `technical_tags`…) — see `vault.py:_apply_import_to_document`, `api.ts:createDocument`. Every reader does a `??` cascade. The two copies **will** drift (some code paths already update only one).

**Fix:** one canonical wire format (snake_case, since Pydantic owns it), one conversion at the client boundary, a one-time migration to normalize stored blobs, then delete every fallback read.

### C7. Client IDs are not UUIDs
`newId()` (`WorkspaceApp.tsx:435`) returns `${Date.now()}-${random}`. Server IDs are UUIDs. Offline-created records can therefore never be replayed against UUID-validated endpoints. Use `crypto.randomUUID()` and let the API accept a client-supplied ID for idempotent replay (unique per user).

---

## Part 3 — Security findings

The app is local-first today, but the code will outlive that assumption. None of these are acceptable to carry into any hosted deployment, and two matter even locally.

### S1. SSRF in the URL importer (matters even locally)
`POST /vault/import-url` (`vault.py:1078`) fetches any http(s) URL with `urllib.urlopen`, follows redirects, no address filtering. A malicious page or pasted link can make the API request `http://localhost:9001` (MinIO console), cloud metadata endpoints, or anything on the LAN, and the extracted text is stored and shown. **Fix:** resolve DNS, reject private/loopback/link-local ranges (also on each redirect hop), cap redirect count, enforce content-type allowlist, and set a total-time budget.

### S2. Identity is a spoofable header
`get_current_user_id` (`core/security.py`) trusts `x-user-id` from the client. Any caller is any user. Fine as a placeholder — but it's wired into every endpoint as if it were auth. **Fix (phased):** short-term, bind the demo user server-side and ignore the header; medium-term, session auth (even single-user with a local token) so the day this touches a network there is a real boundary.

### S3. No rate limiting or budget on fan-out endpoints
`/trades/quotes/{symbol}`, `/vault/import-url`, and AI enrichment all trigger outbound calls with no throttle, cache, or concurrency cap. One misbehaving tab (the UI already polls quotes every 30s per symbol) or one bulk import multiplies into upstream abuse and Yahoo/provider bans.

---

## Part 4 — Architecture critique

### A1. GET endpoints that write
`GET /vault/documents` (`vault.py:1167`) runs `_refresh_document_if_supported` on every listed document: it may call arXiv over the network, delete and rebuild graph learning, mutate rows, and commit — inside a list request. This makes reads slow, non-idempotent, un-cacheable, and means an arXiv outage degrades *listing your own vault*. "Repair on read" is the wrong pattern.
**Fix:** move repair to an explicit `POST /vault/documents/{id}/refresh` and a background sweep job.

### A2. Heavy work in the request path while a worker sits idle
The compose stack runs Redis, MinIO, and a worker whose entire job is `time.sleep(5)` (`services/worker/app/main.py`). Meanwhile the API does, synchronously per request: URL fetch, HTML parse, regex NLP, up to 4 sequential AI provider calls at 18s timeout each (worst case > 70s in `_enriched_import`), double strategy evaluation with two quote fetches (`trades.py:optimal_strategy` / `evaluate_strategy`). You pay the operational cost of a job infrastructure without using it, and pay the latency cost of not using it.
**Fix:** imports return fast with extracted text + local tags; enrichment/learning become jobs (arq or RQ on the existing Redis) with a `status` field the UI polls. Either that, or delete Redis/MinIO/worker from compose until needed — running dead infrastructure is the worst of both.

### A3. "Vector memory" does not exist
`MemoryChunk.embedding` is always `None` (`source_learning.py:266`), the pgvector 1536-dim column is provisioned but never written or queried, `token_count` is a word count, and chunking is fixed 1600-char slices of whitespace-collapsed text with no boundary awareness. All "semantic" matching in recommendations/evaluation is regex keyword matching. The README/architecture docs claim semantic search; the code does not deliver it. This is the single largest gap between stated thesis and implementation.
**Fix:** Phase 4 below. Until then, adjust README wording — do not ship claims the code can't back.

### A4. Knowledge-graph provenance is last-write-wins
`_get_or_create_node` (`source_learning.py:280`) keys strategy/tag/technical nodes by label and **overwrites** properties and confidence with the latest source; `_get_or_create_edge` **replaces** `evidence_chunk_ids` instead of accumulating. Re-importing one document erases what other sources contributed. There are also no DB unique constraints backing the get-or-create, so concurrent imports create duplicates.
**Fix:** append/merge properties per source, accumulate evidence, add `(user_id, node_type, label)` and `(user_id, edge_type, from, to)` unique indexes with upsert.

### A5. Two divergent schema paths, only one tested
SQLite via `create_all` for dev/test; Postgres via Alembic for compose/prod. CI tests only SQLite. The pgvector column, `GUIDArray`, JSON variants, and the single migration (`20260704_0001_initial.py`) are never exercised in CI — schema drift between models and migration will be discovered at deploy time.
**Fix:** CI job with a Postgres service that runs `alembic upgrade head` + the test suite, plus a drift check (`alembic check` / compare metadata).

### A6. Market data: one hardcoded unofficial endpoint
`market_data.py` scrapes Yahoo's chart endpoint — undocumented, rate-limited at Yahoo's whim, ToS-grey. There is no provider interface, no server-side cache (every client polls straight through every 30s), no stale-quote fallback. The env file already lists Alpha Vantage / Twelve Data / FMP keys that nothing reads.
**Fix:** a `QuoteProvider` protocol + registry (same shape as the AI router), 15–30s server-side cache keyed by symbol, provider fallback order, and per-provider budgets. This is also the foundation the roadmap's "provider mesh" needs anyway.

### A7. AI router: silent failure, unverifiable providers
`extract_strategy_with_ai` swallows every exception with no logging. Compounding this, the Gemini integration (`endpoint=".../v1beta/interactions"`, custom `_gemini_text` parser) does not match the Gemini REST API's `models/{model}:generateContent` shape — if it's wrong, it has *never worked* and nothing would tell you. That is the real defect: a provider can be misconfigured forever, invisibly.
**Fix:** structured logging on every provider attempt (provider, status, latency), a `GET /ai/providers/self-test` that fires a canary prompt at each configured provider, and verification of the Gemini endpoint against current docs. Add optional local inference (Ollama) — it's the natural fit for the local-first thesis.

### A8. Router modules doing service work
`vault.py` is 1,248 lines: HTML parser classes, an arXiv client, regex NLP, enrichment orchestration, and metadata munging inside the HTTP layer. It's the second-largest file in the repo and untestable in isolation.
**Fix:** split into `services/importers/{web,arxiv,file}.py`, `services/enrichment.py`, and a thin router. Pure functions, unit-tested without the app.

### A9. The 4,894-line client component
`WorkspaceApp.tsx` holds ~30 `useState` hooks, all six tabs, the galaxy graph physics, every form, the sync engine, insights computation, and P&L math. Consequences: any state change re-renders the world (the graph animation tick re-renders everything ~continuously), no piece is testable, merge conflicts are guaranteed with >1 developer, and code review of changes to it is effectively impossible.
**Fix:** Phase 3 decomposition below. This is not cosmetic — it is the main obstacle to your team executing anything else in parallel.

### A10. No pagination, O(N×M) recompute per request
Every list endpoint returns all rows. `/trades/recommendations` and `/trades/strategy/optimal` re-run regex extraction over every source body × every trade on each GET. Fine at 20 documents; visibly slow at 500.
**Fix:** `limit/offset` (or cursor) on list endpoints; cache extraction results in `source_metadata` at write time (they're already computed then) instead of recomputing at read time.

### A11. Missing basic CRUD
Journal entries and documents cannot be edited — create/delete only (`vault.py`). A journaling product without edit is a real product gap, and it also forces the UI into delete-recreate patterns that break provenance (new IDs orphan graph nodes).

### A12. Pseudo-precision presented as intelligence
Confidence numbers are arithmetic on keyword counts (`0.25 + signals×0.08` in `vault.py:_strategy_info`; `source_confidence + 0.04×trades ± 0.12` in `trade_recommendations.py`). `targetExitPrice` hardcodes 1.2%/0.8%/1% targets by tag (`WorkspaceApp.tsx:581`). "Optimal strategy" is argmax keyword-score over source texts. As UX these read as statistical claims; they are not.
**Fix:** label heuristic outputs as heuristics in the UI ("rule-based estimate"), and where real samples exist (matched closed trades), show the actual n, win rate, and average R instead of a synthetic confidence scalar. Trust is the product; fabricated precision spends it.

---

## Part 5 — Quality infrastructure gaps

| Gap | Detail | Fix |
|---|---|---|
| No typecheck in CI | Web CI runs `npm run lint` only — `tsc --noEmit` never runs; type errors ship | Add typecheck + `next build` steps |
| Zero frontend tests | No test runner configured at all | Vitest + React Testing Library; cover P&L math, sync queue, reducers first |
| Backend tests happy-path only | 4 files; no failure-mode tests (validation, 404 ownership, offline providers, SSRF guard) | Grow alongside each Phase 1 fix — every fix lands with a regression test |
| No Postgres in CI | See A5 | Postgres service container + alembic upgrade in CI |
| `npm install` in CI | Non-reproducible builds | `npm ci` |
| No error tracking/logging | API has zero logging config; exceptions swallowed in ai_router, importers | Structured logging (structlog), request IDs; Sentry optional later |
| No Python type checking | mypy/pyright absent from dev deps | Add pyright basic mode to CI |
| Repo hygiene | `CS_Beekman_Chauhan.pdf`, `deepfake-poster/`, `images/`, `tmp/` at root; `quant_labs_dev.db` not gitignored (no `*.db` pattern); `uv.lock` present but the workflow uses pip; poster assets in `docs/` | Move non-product artifacts out (or `archive/`), add `*.db` to .gitignore, pick uv **or** pip and delete the other |
| Half-monorepo | Root `package.json` declares workspaces but scripts use `npm --prefix`; web has its own lockfile | Commit to npm workspaces properly, or drop the workspaces field |
| `target: "es5"` in tsconfig | Anachronistic for Next 14+; slower/larger output where it applies | `"target": "ES2022"` |

---

## Part 6 — The implementation plan

Phases are ordered by dependency, not preference. Phases 0–2 are sequential; 3 can run in parallel with 2 by a second developer; 4–5 follow. Each task lists acceptance criteria (AC).

### Phase 0 — Guardrails & hygiene (≈ 1 week, do first)

0.1 **CI hardening.** Add `tsc --noEmit`, `next build`, `npm ci`, pyright, a Postgres-service test job running `alembic upgrade head` + pytest.
 AC: CI fails on type errors, on Alembic/model drift, and on Postgres-only breakage.

0.2 **Repo cleanup.** Relocate `deepfake-poster/`, `images/`, `tmp/`, personal PDFs out of the product repo; `.gitignore` gets `*.db`; delete `uv.lock` or migrate fully to uv.
 AC: fresh clone contains only product code + docs.

0.3 **Logging.** Structured logging in the API (request ID, route, duration); every swallowed exception in `ai_router.py` and importers becomes a logged warning.
 AC: a failed provider call is visible in logs with provider ID and reason.

0.4 **Test scaffolding for web.** Vitest + RTL wired into CI with the first test (P&L math).

### Phase 1 — Correctness & data integrity (≈ 2 weeks)

1.1 **Sync engine rewrite (C1, C7).** Persisted `pendingWrites` queue; network errors → queue + retry with backoff; 4xx → user-visible error, no offline flip; hydration merges server state with pending queue; `crypto.randomUUID()` client IDs accepted by the API for idempotent replay.
 AC: create 3 records with API stopped → restart API → reload → all 3 exist server-side; a validation error shows a message and does not disable persistence.

1.2 **Single-source P&L (C2, C4).** `contract_multiplier` becomes a column; server computes P&L with it; PATCH uses `model_fields_set`; client renders server values (keeps local calc only for live-mark preview). Backfill migration for existing rows.
 AC: a 2-lot MES trade shows identical P&L in DB, API response, and UI; PATCH without `pnl_amount` leaves a manually set value untouched.

1.3 **Real timestamps (C3).** Ticket captures entry/exit datetimes; wire format is full ISO; old rows flagged `time_resolution: "date"`.
 AC: session/time-of-day insight reads true entry times for new trades.

1.4 **Enum validation (C5).** Literals/enums for side, asset_class, status, document kind across Pydantic + TS.
 AC: `side="Long"` returns 422, not inverted P&L.

1.5 **Metadata normalization (C6).** Snake_case canonical; one-time migration normalizes stored blobs; all dual writes and `??`-cascade reads removed.
 AC: grep for `strategyInfo` in the API returns zero hits; round-trip test proves no field loss.

1.6 **Edit endpoints (A11).** `PATCH /vault/documents/{id}`, `PATCH /vault/journal-entries/{id}` + UI edit affordances, preserving IDs and graph links.

1.7 **SSRF guard (S1) + server-side demo identity (S2).**
 AC: import of `http://169.254.169.254/` and `http://localhost:9001` rejected with 400; redirects re-validated; `x-user-id` header ignored.

### Phase 2 — Backend architecture (≈ 3 weeks)

2.1 **Extract the import/enrichment services (A8).** `vault.py` router shrinks to endpoint definitions; importers/enrichment become pure, unit-tested modules.

2.2 **Async enrichment pipeline (A2).** Adopt the existing Redis with arq/RQ: import returns immediately (`enrichment_status: pending`), worker runs AI extraction + source learning, UI polls or receives status on next fetch. Kill the sleep-loop placeholder. Decision point: if the team prefers deferring job infra, the fallback is FastAPI `BackgroundTasks` + status column — but then **remove** Redis/MinIO from compose until used.
 AC: URL import responds < 2s regardless of AI provider latency; enrichment lands asynchronously.

2.3 **Read-path cleanup (A1, A10).** No writes in GETs; explicit refresh endpoint + background sweep; pagination on all list endpoints; recommendations read cached extraction from write time.
 AC: `GET /vault/documents` does zero outbound network calls; p95 < 200ms at 1,000 documents.

2.4 **Quote provider mesh + cache (A6, S3).** Provider protocol, Yahoo + one keyed provider (Alpha Vantage or Twelve Data — keys already scaffolded in `.env.example`), 15–30s server cache, rate budget, stale-with-timestamp fallback.
 AC: 50 clients polling one symbol produce ≤ 2 upstream calls/30s; Yahoo outage degrades to stale quotes, not 502s.

2.5 **AI router observability (A7).** Per-attempt logging, `/ai/providers/self-test`, verify/fix the Gemini endpoint, add optional Ollama provider for fully-local enrichment.
 AC: self-test reports pass/fail per configured provider in the UI's AI-router status card.

2.6 **Graph integrity (A4).** Merge-not-overwrite node properties, accumulate edge evidence, unique constraints + upsert.
 AC: importing two sources supporting one strategy yields one node with both provenance entries; re-import doesn't erase the other's evidence.

### Phase 3 — Frontend decomposition (≈ 3 weeks, parallelizable with Phase 2)

3.1 **Feature-folder split.** `WorkspaceApp.tsx` →
```
features/vault/       VaultTab, ImportForm, SourceCard, ReadMore
features/journal/     JournalTab, EntryForm
features/trades/      TradesTab, TradeTicket, QuickEntry, PositionsPanel, TradeHistory
features/routine/     RoutineTab
features/insights/    InsightsTab, StrategyScoreboard
features/atlas/       AtlasTab (galaxy graph, isolated so its animation re-renders only itself)
lib/domain/           pnl.ts, trades.ts, insights.ts  ← pure functions, unit-tested
lib/sync/             queue.ts, hydrate.ts            ← the Phase 1.1 engine
```
 AC: no file > 500 lines; graph animation no longer re-renders other tabs (verify with React profiler).

3.2 **Server state via TanStack Query.** Replace hand-rolled fetch orchestration/polling with queries + mutations (optimistic updates feed the offline queue). Health check becomes a query with refetch — fixes "API came online but UI never notices."

3.3 **Shared API types.** Generate the TS client from FastAPI's OpenAPI schema (`openapi-typescript`) so the DTO layer in `api.ts` can't drift from Pydantic.
 AC: changing a Pydantic field breaks web typecheck in CI.

3.4 **Forms with schema validation.** Replace `FormData` string-mining with react-hook-form + zod mirrors of the API enums.

3.5 **Honest heuristics UI (A12).** Confidence chips get a "rule-based" label + tooltip; where matched trades exist, show `n`, win rate, avg R instead of synthetic confidence; remove hardcoded target-% suggestions or label them explicitly as placeholders.

### Phase 4 — Make the memory real (≈ 3 weeks)

4.1 **Embeddings, actually.** Worker computes embeddings per chunk (default local via Ollama `nomic-embed-text` to honor local-first; optional cloud provider). Store in the pgvector column; SQLite path uses a brute-force cosine fallback (fine at personal scale).
4.2 **Boundary-aware chunking.** Sentence/paragraph chunking with overlap; real token counts.
4.3 **Semantic search endpoint + ⌘K.** `GET /search?q=` across chunks, trades, journal (vector + keyword hybrid); global command palette in the UI.
4.4 **Retrieval-backed recommendations.** Recommendations/evaluation retrieve nearest chunks as evidence (replacing regex-only matching) and cite them — this is the first true "GraphRAG" increment and directly enables the chat feature below.
 AC: searching "liquidity sweep before London open" returns relevant chunks that share no exact keywords with the query.

### Phase 5 — Feature expansion (prioritized backlog)

Ordered by leverage-to-effort; 5.1–5.4 are the recommended next quarter.

5.1 **"Ask my memory" chat (GraphRAG).** Chat over the vault/trades/journal with citations to chunks and trades (Phase 4 retrieval + AI router). This is build-order step 3 in your own architecture doc and the single most differentiating feature. Paper-only, evidence-cited, refuses to answer without evidence.

5.2 **Broker CSV import.** The `broker_import` kind already exists. Parsers for TradingView paper, IBKR Flex, and Webull exports; dedupe by (symbol, time, qty, price); auto-match to strategies via existing tags. Instantly turns the journal from manual-entry into a real record. *(Cool factor: drag a CSV, watch the atlas grow.)*

5.3 **Risk & expectancy dashboard.** `pnl_r` and `planned_risk_amount` columns exist but are never populated. Compute R per trade from stop distance; show R-distribution, expectancy, profit factor, max drawdown, exposure by asset class, and a position-size calculator (account size + risk% → quantity, using real contract multipliers from 1.2).

5.4 **Daily review autopilot.** A worker job at market close: summarize the day's trades vs. extracted strategy rules, populate `rule_adherence_score` (column exists, unused), correlate emotion tags with outcomes, and write a draft journal entry the user confirms/edits. Turns the journal from a chore into a habit loop.

5.5 **TradingView webhook adapter.** `docs/tradingview-adapter-thesis.md` already argues for it. Webhook endpoint (HMAC-signed) → paper trade or alert log → auto-links to strategy. First external adapter, validates the "adapters around memory" thesis.

5.6 **Market-regime tagging.** `market_regime_id` column exists, unused. Nightly job labels each day (SPY trend bucket × VIX bucket) via the provider mesh; trades inherit the regime at entry; insights split per regime ("your ORB setup: 68% win in trend-up, 31% in chop") — the single most actionable analytics upgrade for a discretionary trader.

5.7 **Pre-trade checklist gate.** The routine tab already generates rules. Make the trade ticket optionally require ticking the strategy's checklist before it unlocks; log adherence with each trade; insights compare checklist-on vs. checklist-off performance. Behavioral guardrail — very cheap, very sticky.

5.8 **Read-only MCP server.** Expose vault search, trade history, and graph queries as MCP tools so Claude/other agents can answer over the user's trading memory. Aligns exactly with the architecture doc's step 6 and makes the product composable with the user's AI tooling. Read-only, local transport first.

5.9 **Trade screenshots.** Attach chart images to trades — finally a real use for MinIO. Thumbnails in trade history and the atlas.

5.10 **Lesson flashcards (spaced repetition).** Mistakes and lessons tagged in journal entries resurface on a review schedule on the dashboard ("2 weeks ago you paid $312 to relearn: no entries in the first 5 minutes"). The memory system, pointed at the trader.

5.11 **Backtest + Paper Lab** (build-order step 5). Deterministic bar-replay simulator over daily/intraday data for extracted strategies; equity curve, drawdown, per-setup stats; walk-forward split to flag overfitting. Larger effort — schedule after 5.1–5.4 have hardened the data layer it depends on.

5.12 **Weekly report export.** PDF/HTML weekly summary (P&L, R stats, rule adherence, best/worst, lessons) — shareable artifact, doubles as the ISEF/demo asset.

---

## Part 7 — Sequencing summary for the team

| Phase | Duration | Can parallelize with | Outcome |
|---|---|---|---|
| 0 Guardrails | 1 wk | — | CI catches regressions before the refactor starts |
| 1 Correctness | 2 wks | — | No more silent data loss; numbers are trustworthy |
| 2 Backend arch | 3 wks | Phase 3 | Fast reads, async enrichment, provider mesh, honest graph |
| 3 Frontend decomp | 3 wks | Phase 2 | Reviewable codebase; team can work in parallel |
| 4 Real memory | 3 wks | 5.2/5.3 prep | Semantic search; the thesis becomes true |
| 5 Features | ongoing | — | Chat, broker import, risk dashboard, review autopilot first |

**Definition of done for every task:** regression test included, no new file > 500 lines, logging on failure paths, docs updated in the same PR.

**Two rules going forward:**
1. Nothing new lands in `WorkspaceApp.tsx` — new UI goes into feature folders even before the big split.
2. README/docs may not claim capabilities the code doesn't have (current offender: "semantic search / vector memory"). Docs describe the shipped state; the roadmap holds the rest.
