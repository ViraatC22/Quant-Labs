# AI Trading Intelligence OS — Developer Implementation Plan

**Working product name:** Trading Intelligence OS
**Primary product thesis:** Build a local-first, AI-powered trading memory system that learns from the trader’s trades, routines, mistakes, research, strategies, market regimes, and journal entries. TradingView, Alpaca, market-data APIs, and MCP servers should be adapters around the core product, not the core product itself.


---

## Developer dependency and setup protocol

Before implementation begins, developers must maintain a living setup checklist named `SETUP_REQUESTS.md`. This checklist should tell the founder exactly which third-party accounts, API keys, OAuth apps, billing toggles, local software, credentials, or product decisions are needed.

For every external service, the checklist must include:

```text
Service name
Why it is needed
Required account tier, if known
Whether a free tier/free API key is available
Exact credentials needed, for example API key, secret, OAuth client ID, webhook secret
Whether payment method is required
Whether the integration is optional or blocking
Local setup steps, if any
Security notes
Who owns setup: founder, developer, or both
Date last verified
```

Developers must notify the founder whenever they need something that cannot be created safely inside the codebase, including but not limited to:

```text
market-data API keys
broker/paper-trading accounts
TradingView webhook setup
Alpaca paper-trading keys
FRED API key
Alpha Vantage key
Twelve Data key
Financial Modeling Prep key
CoinGecko key, if needed
GitHub OAuth app
Figma file/plugin access
Supabase project credentials, if Supabase is used
Sentry/observability credentials
cloud storage bucket credentials
email provider credentials
local Ollama model installation
Docker Desktop or local Postgres setup
```

No developer should hardcode personal credentials, use shared secrets in source control, or proceed with a third-party integration without documenting the required setup. All credentials must go through encrypted environment variables, local `.env` files excluded from Git, or the app's encrypted credential vault.

---

## 1. Strategic build order

Build in this order:

1. **Learning Vault** — trades, notes, screenshots, articles, PDFs, broker imports, strategy documents, emotions, routines, metadata.
2. **Knowledge Graph + Vector Memory** — Obsidian-style graph, semantic search, entity extraction, source provenance.
3. **GraphRAG Chat** — evidence-backed chat over trades, routines, articles, rules, and strategies.
4. **Strategy Creator / Compiler** — ingest complex articles and papers, extract strategy rules, compare with personal metadata, create personalized strategy versions.
5. **Backtest + Paper Lab** — internal simulator, strategy variants, overfitting checks, paper experiments.
6. **Provider Mesh + Integrations** — free/free-start market-data APIs, fallback routing, TradingView webhook/Pine/chart adapter, Alpaca paper trading, optional LEAN.
7. **Autonomous Paper Agent** — shadow trader, paper-only execution, approval gates, risk limits, kill switches.

Do **not** build live autonomous trading in the first version. Keep MVP paper-only and research/journaling focused.

---

## 2. Recommended architecture

### 2.1 High-level architecture

```text
apps/web
  Next.js + TypeScript + Tailwind + shadcn/ui
  Graph UI, journal UI, strategy builder, chat, dashboards

services/api
  FastAPI + Pydantic
  Auth, vault, trades, graph, RAG, provider mesh, strategy APIs

services/worker
  Celery/RQ/Arq workers
  File parsing, embeddings, entity extraction, backtests, strategy compilation

services/mcp-server
  Custom Trading Vault MCP server
  Exposes safe tools to Claude/Codex/other MCP clients

services/paper-engine
  Internal paper simulator and optional broker adapters

services/provider-mesh
  Market data provider registry, cache, health checks, fallback router

infra
  Docker Compose for local-first mode
  Terraform/Fly/Render/AWS/GCP deployment later
```

### 2.2 Local-first deployment target

The first developer milestone should run entirely locally using Docker Compose:

```text
Postgres + pgvector
Redis
MinIO or local object storage
FastAPI API
Worker
Next.js web app
Ollama optional
```

Cloud deployment should be the same containers with managed Postgres, Redis, and object storage.

### 2.3 Recommended stack

**Frontend**

- Next.js with TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Query
- Zustand or Jotai for local UI state
- React Flow for early graph UI; evaluate Cytoscape/Sigma.js later for large graphs
- Lightweight Charts for internal financial charts
- Monaco Editor for Pine/Python/strategy DSL editing

**Backend**

- FastAPI
- Pydantic models for all AI extraction outputs and API schemas
- SQLAlchemy 2 or SQLModel
- Alembic migrations
- Celery/RQ/Arq worker queue
- Redis for queue/cache
- Postgres + pgvector for structured data and vector search
- Optional later: Neo4j for advanced graph analytics

**AI layer**

- Provider abstraction for OpenAI, Anthropic, local Ollama, llama.cpp server, and embedding providers
- JSON-schema extraction for strategy ingestion
- GraphRAG retrieval pipeline
- Evaluation harness for hallucination, extraction quality, and recommendation quality

**Data/storage**

- Postgres tables for users, trades, strategies, graph nodes/edges, sources, chunks, embeddings, paper trades, backtests, provider data
- Object storage for screenshots, PDFs, broker import files, generated reports
- pgvector for embeddings
- JSONB for flexible metadata, but do not let JSONB replace strongly typed critical fields

---

## 3. Core modules

## 3.1 Vault module

Purpose: store all user knowledge.

Must support:

- Manual journal entries
- Markdown notes
- Uploaded PDFs/articles
- Screenshots
- Strategy docs
- Broker CSV imports
- Trade screenshots
- Voice/transcript imports later
- Tags, backlinks, source provenance

Minimum entities:

```text
SourceDocument
SourceChunk
JournalEntry
Attachment
Tag
Backlink
UserAnnotation
```

Required behavior:

- Every source gets a canonical `source_document_id`.
- Every parsed chunk gets source spans, page/paragraph offsets if available, and embedding.
- Every AI-created claim, rule, or graph node must link back to source chunks.
- All user-visible AI answers must be able to cite vault evidence.

---

## 3.2 Trade journal module

Purpose: capture trade behavior and metadata.

Must support:

- Manual trade entry
- CSV import from brokers
- Trade legs
- Screenshots before/during/after trade
- Strategy tag
- Setup tag
- Rule adherence score
- Routine checklist
- Emotional state
- Market regime
- Time-of-day/session metadata
- Outcome in R and dollars
- Mistake classification

Minimum entities:

```text
Trade
TradeLeg
TradeScreenshot
TradeNote
TradeMetric
MistakeTag
EmotionTag
RoutineEntry
```

MVP trade fields:

```text
id
user_id
symbol
asset_class
side
entry_time
exit_time
entry_price
exit_price
quantity
fees
pnl_amount
pnl_r
strategy_version_id
setup_id
timeframe
session
market_regime_id
planned_risk_amount
actual_risk_amount
rule_adherence_score
emotional_state_before
emotional_state_after
journal_summary
created_at
updated_at
```

---

## 3.3 Metadata taxonomy module

Purpose: make trades machine-readable.

Create a configurable taxonomy system:

```text
Strategy
Setup
Rule
Indicator
MarketRegime
MistakeType
Emotion
RoutineChecklistItem
Session
AssetClass
Timeframe
```

The user should be able to define custom tags, but core tags should be normalized.

Example normalized mistake types:

```text
late_entry
early_entry
stop_moved
oversized
revenge_trade
no_plan
ignored_news
strategy_not_in_playbook
low_volume_breakout
chased_extension
premature_exit
invalid_setup
```

Example market regimes:

```text
trend_day
range_day
gap_and_go
gap_fade
high_vol_chop
low_volume_drift
macro_event_day
earnings_day
news_driven_move
```

---

## 3.4 Knowledge graph module

Purpose: Obsidian-style graph that shows relations between the trader, strategies, trades, losses, routines, sources, and market regimes.

### Node types

```text
trade
strategy
strategy_version
setup
rule
indicator
market_regime
mistake
emotion
routine
source_document
source_chunk
claim
hypothesis
experiment
backtest_run
paper_trade
asset
session
timeframe
provider_data_point
```

### Edge types

```text
USED_STRATEGY
VIOLATED_RULE
FOLLOWED_RULE
OCCURRED_DURING
ASSOCIATED_WITH
SUPPORTED_BY
CONTRADICTS
DERIVED_FROM
IMPROVED_BY
FAILED_IN_REGIME
WORKED_IN_REGIME
BACKTESTED_AS
PAPER_TRADED_AS
REPLACED_BY_VERSION
SIMILAR_TO
CAUSES_SUSPECTED
CORRELATED_WITH
```

### MVP graph storage

Use Postgres tables first:

```sql
create table kg_nodes (
  id uuid primary key,
  user_id uuid not null,
  node_type text not null,
  source_table text,
  source_id uuid,
  label text not null,
  properties jsonb not null default '{}',
  confidence numeric,
  created_by text not null default 'system',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table kg_edges (
  id uuid primary key,
  user_id uuid not null,
  edge_type text not null,
  from_node_id uuid not null references kg_nodes(id),
  to_node_id uuid not null references kg_nodes(id),
  properties jsonb not null default '{}',
  confidence numeric,
  evidence_chunk_ids uuid[] not null default '{}',
  created_by text not null default 'system',
  created_at timestamptz not null default now()
);

create index kg_nodes_user_type_idx on kg_nodes(user_id, node_type);
create index kg_edges_user_type_idx on kg_edges(user_id, edge_type);
create index kg_edges_from_idx on kg_edges(from_node_id);
create index kg_edges_to_idx on kg_edges(to_node_id);
```

Later, sync this to Neo4j if graph traversal and algorithms become a performance bottleneck.

---

## 3.5 Vector memory module

Purpose: semantic retrieval across trades, notes, imported sources, strategies, and journal entries.

MVP table:

```sql
create extension if not exists vector;

create table memory_chunks (
  id uuid primary key,
  user_id uuid not null,
  source_type text not null,
  source_id uuid not null,
  chunk_index int not null,
  text text not null,
  embedding vector(1536), -- adjust to embedding provider
  metadata jsonb not null default '{}',
  token_count int,
  created_at timestamptz not null default now()
);

create index memory_chunks_user_source_idx
  on memory_chunks(user_id, source_type, source_id);

create index memory_chunks_embedding_hnsw_idx
  on memory_chunks using hnsw (embedding vector_cosine_ops);
```

Search should always filter by `user_id` before returning results.

Hybrid retrieval score:

```text
score =
  0.40 * vector_similarity
+ 0.20 * full_text_score
+ 0.15 * graph_proximity_score
+ 0.10 * recency_score
+ 0.10 * source_quality_score
+ 0.05 * user_pin_or_playbook_priority
```

---

## 3.6 GraphRAG chat module

Purpose: evidence-weighted chat that understands trades, routines, research, strategies, losses, and graph relations.

### Query flow

```text
1. User asks question.
2. Classify intent:
   - trade_analysis
   - strategy_question
   - source_question
   - performance_pattern
   - graph_exploration
   - paper_experiment
   - indicator_generation
3. Extract entities:
   symbols, strategy names, setups, date ranges, emotions, routines, indicators.
4. Run structured SQL queries for metrics.
5. Run vector search over memory_chunks.
6. Map retrieved chunks to graph nodes.
7. Expand graph neighborhood 1-2 hops.
8. Rerank evidence.
9. Generate answer with evidence, confidence, caveats, and suggested next action.
10. Store conversation and discovered insights back into the vault.
```

### Answer format

Every analytical answer should include:

```text
Answer
Evidence
Confidence
What may be wrong
Recommended experiment or next action
```

Example:

```text
Your VWAP pullback losses are mostly connected to low-volume regimes and late entries.
Evidence: 17 matching trades, 11 losses, 8 with RVOL < 1.2, 7 after 10:45 AM.
Confidence: Medium. The sample is still small.
Next experiment: paper-test VWAP Pullback v4 with RVOL > 1.5 and no entries after 10:45 for 30 trades.
```

---

## 3.7 Strategy Creator / Strategy Compiler

Purpose: ingest complex strategy articles/papers and convert them into structured, personalized, testable strategy objects.

### Ingestion pipeline

```text
upload/import source
  -> parse text
  -> chunk source
  -> extract metadata
  -> extract claims
  -> extract strategy rules
  -> extract assumptions
  -> extract indicators
  -> extract examples
  -> link to existing user strategies/rules
  -> detect contradictions
  -> create strategy draft
  -> personalize using user history
  -> generate test plan
  -> optionally generate Pine/Python/LEAN draft
```

### Extraction schema

```python
class ExtractedStrategy(BaseModel):
    source_document_id: UUID
    title: str
    summary: str
    asset_classes: list[str]
    timeframes: list[str]
    indicators: list[IndicatorSpec]
    setup_rules: list[RuleSpec]
    entry_rules: list[RuleSpec]
    exit_rules: list[RuleSpec]
    invalidation_rules: list[RuleSpec]
    risk_rules: list[RuleSpec]
    market_regime_assumptions: list[str]
    avoid_conditions: list[str]
    examples: list[TradeExample]
    claims: list[ClaimSpec]
    source_quality_score: float
    implementation_notes: list[str]
```

Each rule must include provenance:

```python
class RuleSpec(BaseModel):
    rule_text: str
    normalized_rule_type: str
    required: bool
    confidence: float
    source_chunk_id: UUID
    source_quote_span: dict | None
    machine_readable_expression: dict | None
```

### Personalization step

After extraction, compare the new strategy with the user’s graph:

```text
New rule: “Take first opening range breakout.”
User history: first ORB breakout has negative expectancy unless RVOL > 2.0.
Personalized adaptation: require RVOL > 2.0 and no trade after first failed breakout.
```

### Strategy status workflow

```text
research_imported
  -> draft_strategy
  -> personalized_draft
  -> backtest_ready
  -> backtested
  -> paper_test_required
  -> paper_testing
  -> limited_live_candidate
  -> archived/rejected/core_playbook
```

MVP should stop at `paper_testing`; do not build live execution yet.

---

## 3.8 Strategy Genome Compiler

Represent every strategy as a composable genome:

```json
{
  "strategy_name": "VWAP Pullback",
  "entry_gene": ["price_above_vwap", "pullback_to_vwap", "bullish_reclaim"],
  "filter_gene": ["rvol_gt_1_5", "market_trend_aligned"],
  "risk_gene": ["stop_below_reclaim", "max_loss_0_5R"],
  "exit_gene": ["partial_at_1R", "trail_higher_low"],
  "avoid_gene": ["no_trade_after_11_30", "avoid_fomc_day"]
}
```

Required features:

- Create strategy variants.
- Track lineage from source article and prior strategy version.
- Compare variants using backtest/paper-test metrics.
- Promote only when sample size and robustness checks pass.

Variant generation should create testable hypotheses, not direct recommendations.

---

## 3.9 Backtest and paper lab

### Internal backtesting MVP

Start with a simple event-driven backtester in Python:

- OHLCV bars
- Market/limit/stop orders
- Bracket orders
- Fees
- Slippage
- Spread
- Partial exits
- Position sizing
- R-multiple tracking
- Equity curve
- Drawdown
- Trade list export

### Backtest run record

```text
BacktestRun
  id
  user_id
  strategy_version_id
  symbols
  timeframe
  date_range
  market_data_provider
  parameters
  slippage_model
  commission_model
  metrics
  trades_json
  equity_curve_uri
  created_at
```

### Overfitting guardrails

Do not promote a strategy unless it passes:

```text
minimum sample size
walk-forward test
out-of-sample test
parameter sensitivity test
regime diversity check
outlier dependence check
provider disagreement check
source provenance check
manual user approval
```

### Paper lab

MVP paper engine should simulate:

```text
order lifecycle
fills
slippage
fees
position state
daily risk limit
max concurrent positions
strategy whitelist
audit log
```

External paper trading should be an adapter after the internal simulator is stable.

---

## 3.10 Provider Mesh

Purpose: route market-data requests across free/free-start providers, cache results, and fall back when a provider fails.

### Mandatory API-provider research sprint

Before building adapters, developers must do a dedicated research sprint to create a comprehensive provider matrix. The goal is to find the strongest possible list of free, free-start, no-key, and user-key market-data sources, then route between them intelligently when a provider fails, hits quota, becomes stale, or lacks a capability.

Create and maintain:

```text
docs/provider_matrix.md
docs/provider_matrix.csv
docs/provider_setup_requests.md
```

The provider matrix must track:

```text
provider_name
official_docs_url
supported_asset_classes
supported_geographies
supported_endpoints
free_tier_available
no_key_available
api_key_required
OAuth_required
monthly_limit
daily_limit
per_minute_limit
per_second_limit
historical_depth
intraday_depth
real_time_or_delayed
websocket_support
fundamentals_support
news_support
economic_data_support
filings_support
technical_indicators_support
paper_trading_support
live_trading_support, only for future evaluation
license_terms_summary
allowed_use_summary
commercial_use_notes
redistribution_restrictions
status_page_url
SDK_quality
API_response_quality
timezone_behavior
adjusted_price_support
corporate_actions_support
data_delay
known_failure_modes
fallback_priority
implementation_complexity
founder_action_required
date_last_verified
```

The first research pass should include at least:

```text
Alpha Vantage
Twelve Data
Financial Modeling Prep
SEC EDGAR
FRED
CoinGecko
Marketstack
Alpaca
Polygon/Massive, optional paid-quality comparison
NASDAQ Data Link, if useful
Stooq, if license allows
Yahoo Finance alternatives only if legal/ToS-safe
IEX Cloud or successors, if available
Tiingo, if available
Finnhub, if available
EOD Historical Data, if available
OpenFIGI for symbol mapping
Exchange calendars / market-hours sources
Broker-provided paper-market-data sources
```

Important rule: routing across providers must improve reliability, but must **not** be used to evade rate limits, abuse free tiers, bypass terms of service, or scrape sources that disallow the intended use. The router should prefer official APIs, user-provided keys, local cache, and clear license compatibility.

### Free-key and fallback routing requirements

The provider mesh must support:

```text
multiple providers for the same capability
optional multiple keys per provider, only where allowed by the provider terms
per-provider quota tracking
per-key quota tracking
per-user credential storage
global app credential storage, if legally allowed
provider health checks
provider circuit breakers
automatic failover
stale-cache fallback
manual provider disable/enable
provider priority override
license-aware routing
source disagreement detection
```

Provider state enum:

```text
available
degraded
rate_limited
quota_depleted
auth_failed
invalid_credentials
network_failed
provider_down
license_blocked
disabled_by_user
not_configured
```

Routing behavior:

```text
1. Check local cache first.
2. If cache is fresh enough, return cached data with provenance.
3. If cache is stale, choose the highest-scoring available provider.
4. If provider is rate-limited or quota-depleted, mark it and route to the next compatible provider.
5. If credentials are missing, return a setup request instead of failing silently.
6. If all providers fail, return the best stale cached data only if marked as stale.
7. If providers disagree materially, return a data-disagreement warning and store the discrepancy.
8. Never silently mix data from different providers without provenance.
```

Add a setup-request object whenever credentials or third-party configuration are required:

```json
{
  "type": "third_party_setup_required",
  "service": "Alpha Vantage",
  "needed_for": "daily and intraday equity bars fallback",
  "required_from_founder": ["free API key"],
  "blocking": false,
  "fallback_available": true,
  "developer_notes": "Store as ALPHA_VANTAGE_API_KEY or in encrypted credential vault."
}
```

### Provider interface

```python
class MarketDataProvider(Protocol):
    name: str
    capabilities: set[str]

    async def health_check(self) -> ProviderHealth: ...
    async def get_bars(self, request: BarsRequest) -> BarsResponse: ...
    async def get_quote(self, request: QuoteRequest) -> QuoteResponse: ...
    async def get_fundamentals(self, request: FundamentalsRequest) -> FundamentalsResponse: ...
    async def get_news(self, request: NewsRequest) -> NewsResponse: ...
    async def get_macro_series(self, request: MacroRequest) -> MacroResponse: ...
```

### Provider router scoring

```text
provider_score =
  0.25 * capability_match
+ 0.20 * freshness
+ 0.15 * remaining_quota
+ 0.15 * historical_success_rate
+ 0.10 * latency_score
+ 0.10 * cost_score
+ 0.05 * license_compatibility
- 0.30 * recent_error_penalty
```

### Data provenance contract

Every market-data result must include:

```json
{
  "provider": "alpha_vantage",
  "symbol": "AAPL",
  "timeframe": "1d",
  "retrieved_at": "2026-07-04T14:31:00-04:00",
  "license_scope": "personal_research",
  "staleness_seconds": 15,
  "confidence": 0.91,
  "raw_response_hash": "..."
}
```

### API key vault and setup request workflow

Implement an encrypted API key vault that supports both application-level and user-level keys. User-level keys should override application-level keys when the user connects their own account.

Credential records should include:

```text
provider_name
credential_type
owner_scope: app | workspace | user
encrypted_secret_reference
created_at
last_used_at
last_validated_at
validation_status
quota_remaining_estimate
rate_limit_reset_at
permission_scope
notes_for_user
```

When a feature needs a missing key, the app should surface a clear message:

```text
This feature needs a FRED API key for macro data. Add it in Provider Settings, or disable macro context for this strategy test.
```

Developers must keep `docs/provider_setup_requests.md` updated with exact founder actions for every integration.

### Initial provider registry

Implement adapters in this order:

1. Alpha Vantage — broad free-start coverage.
2. Twelve Data — market data + indicators; useful fallback.
3. SEC EDGAR — no-key official U.S. filings and XBRL facts.
4. FRED — macro series.
5. CoinGecko — crypto REST data.
6. Financial Modeling Prep — fundamentals/profiles/news.
7. Marketstack — end-of-day fallback if useful.
8. Alpaca — paper trading and market data where user has account.
9. Polygon/Massive or paid providers later.

Avoid unofficial scraping as a core product dependency.

---

## 3.11 TradingView adapter

TradingView should be an adapter, not the core execution system.

Build:

- Webhook receiver for TradingView alerts
- Alert normalization
- Pine indicator/strategy export
- Chart screenshot attachment workflow
- Optional Charting Library datafeed integration only if licensing allows
- Lightweight Charts internal charting as the default fallback

Webhook endpoint:

```http
POST /api/integrations/tradingview/webhook/:user_token
Content-Type: application/json
```

Payload example:

```json
{
  "source": "tradingview",
  "symbol": "AAPL",
  "timeframe": "5m",
  "alert_name": "VWAP Reclaim",
  "strategy_id": "vwap_pullback_v3",
  "price": 225.14,
  "timestamp": "2026-07-04T14:31:00Z",
  "message": "VWAP reclaim candidate"
}
```

Security requirements:

- Unique secret URL per user.
- Optional HMAC in JSON body.
- Rate limiting.
- IP allowlisting if practical.
- Never accept credentials in webhook payload.
- Webhook alerts should create events, not automatically place orders in MVP.

---

## 3.12 Alpaca adapter

Purpose: paper-trading automation after internal simulator works.

Build:

- Account connection
- Paper account mode only by default
- Order preview
- User approval gate
- Max daily paper loss
- Max trades/day
- Strategy whitelist
- Audit log
- Kill switch

External order flow:

```text
strategy signal
  -> risk validator
  -> order preview
  -> user approval or paper-auto policy check
  -> place paper order
  -> store broker order id
  -> monitor fill
  -> update paper_trade record
  -> add graph edges
```

Never allow live trading without a separate legal/compliance process and explicit user unlock.

---

## 3.13 Custom Trading Vault MCP server

Build your own MCP server so external agents can query and act on the trading vault safely.

### MCP tools

```text
search_trades
search_notes
search_sources
get_strategy_graph
get_strategy_version
classify_loss
create_strategy_variant
run_backtest
create_paper_experiment
generate_pine_script
generate_python_backtest
log_trade
get_market_context
```

### Tool safety levels

```text
read_only
write_draft
write_confirmed
paper_trade_requires_approval
live_trade_forbidden
```

### MCP permissions

- Default all tools to read-only.
- User must approve write tools.
- Paper-trade placement requires explicit confirmation unless user has created a paper-only policy.
- No live trading tools in MVP.
- Log every MCP request and result.

---

## 4. Database schema outline

Use UUIDs. Every user-owned table must include `user_id` and indexes.

### Core tables

```text
users
accounts
api_keys_encrypted
source_documents
source_chunks
memory_chunks
journal_entries
attachments
trades
trade_legs
trade_notes
routine_entries
strategies
strategy_versions
rules
indicators
claims
hypotheses
experiments
backtest_runs
paper_accounts
paper_orders
paper_trades
kg_nodes
kg_edges
provider_configs
provider_health_events
market_bars_cache
chat_threads
chat_messages
ai_insights
audit_events
```

### Strategy version table

```sql
create table strategy_versions (
  id uuid primary key,
  user_id uuid not null,
  strategy_id uuid not null,
  version_number int not null,
  name text not null,
  status text not null,
  description text,
  genome jsonb not null default '{}',
  rules jsonb not null default '[]',
  source_document_ids uuid[] not null default '{}',
  parent_strategy_version_id uuid,
  confidence numeric,
  promotion_score numeric,
  created_by text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

### Claims table

```sql
create table claims (
  id uuid primary key,
  user_id uuid not null,
  source_document_id uuid,
  source_chunk_id uuid,
  claim_text text not null,
  claim_type text not null,
  confidence numeric,
  supports_strategy_version_id uuid,
  contradicts_strategy_version_id uuid,
  properties jsonb not null default '{}',
  created_at timestamptz not null default now()
);
```

### Audit events

```sql
create table audit_events (
  id uuid primary key,
  user_id uuid not null,
  actor_type text not null, -- user, system, ai_agent, mcp_client
  actor_id text,
  action text not null,
  target_type text,
  target_id uuid,
  risk_level text not null default 'low',
  request jsonb,
  response jsonb,
  created_at timestamptz not null default now()
);
```

---

## 5. API contract outline

### Vault

```http
POST /v1/sources/upload
GET /v1/sources
GET /v1/sources/{id}
POST /v1/sources/{id}/reprocess
GET /v1/sources/{id}/chunks
```

### Trades

```http
POST /v1/trades
GET /v1/trades
GET /v1/trades/{id}
PATCH /v1/trades/{id}
POST /v1/trades/import
POST /v1/trades/{id}/classify-loss
```

### Graph

```http
GET /v1/graph/neighborhood?node_id=&depth=2
GET /v1/graph/search?q=&node_types=
POST /v1/graph/edges
GET /v1/graph/insights
```

### Chat

```http
POST /v1/chat/threads
POST /v1/chat/threads/{id}/messages
GET /v1/chat/threads/{id}
```

### Strategy Creator

```http
POST /v1/strategies/import-source
POST /v1/strategies/extract/{source_document_id}
POST /v1/strategies/{id}/personalize
POST /v1/strategies/{version_id}/generate-variant
POST /v1/strategies/{version_id}/generate-pine
POST /v1/strategies/{version_id}/generate-python
```

### Backtest/paper

```http
POST /v1/backtests/run
GET /v1/backtests/{id}
POST /v1/paper/experiments
POST /v1/paper/orders/preview
POST /v1/paper/orders/submit
POST /v1/paper/kill-switch
```

### Provider mesh

```http
GET /v1/providers
POST /v1/providers/{name}/connect
GET /v1/providers/health
GET /v1/market/bars?symbol=&timeframe=&start=&end=
GET /v1/market/quote?symbol=
```

---

## 6. UI screens

### MVP screens

1. **Dashboard**
   - Today’s plan
   - Alpha DNA summary
   - recent losses/wins
   - strategy confidence changes
   - active experiments

2. **Vault**
   - source documents
   - notes
   - article/PDF import
   - markdown editor
   - backlinks

3. **Trade Journal**
   - calendar/table
   - trade detail
   - screenshots
   - loss autopsy
   - rule adherence

4. **Graph**
   - graph canvas
   - node filters
   - edge filters
   - click node -> evidence panel
   - “show related losses”
   - “show contradictions”

5. **AI Chat**
   - evidence-backed chat
   - context inspector
   - source citations
   - action buttons: create experiment, create strategy variant, classify trade

6. **Strategy Creator**
   - upload article/PDF
   - extraction review
   - rule editor
   - contradiction radar
   - personalized strategy version
   - export Pine/Python

7. **Backtest/Paper Lab**
   - strategy variant tournament
   - metrics
   - equity curves
   - trades table
   - promotion score
   - overfitting warnings

8. **Integrations/Settings**
   - API provider keys
   - local/cloud AI settings
   - TradingView webhook URL
   - Alpaca paper connection
   - privacy mode

---

## 7. Signature features to implement

### 7.1 Personal Alpha DNA

Outputs:

```text
strongest edge
weakest setup
best time window
worst time window
most expensive mistake
most profitable routine
most damaging emotional state
best market regime
worst market regime
```

Data sources:

```text
trades
journal entries
routine entries
market regime classifications
strategy versions
rule violations
```

### 7.2 Loss Autopsy Engine

Classify each loss as:

```text
good_loss
execution_error
strategy_invalid
regime_mismatch
risk_sizing_error
emotional_trade
rule_violation
late_entry
early_exit
stop_moved
bad_data
news_shock
```

Output should include evidence and confidence.

### 7.3 Contradiction Radar

When importing new research, detect conflicts with:

```text
current playbook rules
historical user performance
existing imported sources
backtest evidence
paper-test evidence
```

### 7.4 Routine Drift Detector

Detect when current user behavior resembles prior bad clusters.

Inputs:

```text
routine completion
number of trades
time after prior loss
size after prior loss
journal sentiment
missed checklist items
sleep/prep fields if user logs them
```

Output:

```text
Your current behavior resembles your worst week cluster. Consider paper-only mode for the next 2 trades.
```

### 7.5 Shadow Trader

A paper-only agent that tracks what the user’s playbook would have done.

Outputs:

```text
trades user took vs shadow skipped
trades shadow took vs user missed
rule differences
performance delta
setup quality delta
```

### 7.6 Strategy Immune System

Before promoting a strategy, require:

```text
minimum sample size
positive expectancy not driven by one outlier
robustness across regimes
walk-forward stability
reasonable parameter sensitivity
paper-test evidence
no unreviewed contradictions
manual approval
```

---

## 8. AI implementation details

### 8.1 Model provider abstraction

```python
class LLMProvider(Protocol):
    async def complete(self, request: LLMRequest) -> LLMResponse: ...
    async def structured(self, request: StructuredRequest[T]) -> T: ...

class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

Support:

```text
OpenAI
Anthropic
local Ollama
local llama.cpp OpenAI-compatible server
```

### 8.2 Required AI guardrails

- Never return strategy recommendations without evidence and uncertainty.
- Do not claim a strategy works unless backed by user data or test results.
- For execution-related actions, return an order preview, not a direct order.
- Store all AI outputs with model, prompt hash, context chunk IDs, and timestamp.
- Use strict JSON schemas for extraction tasks.
- Use evals for source extraction quality and hallucination rate.

### 8.3 Insight lifecycle

```text
detected_insight
  -> needs_review
  -> accepted
  -> rejected
  -> promoted_to_rule
  -> archived
```

Do not silently mutate a user’s strategy. All modifications should be shown as proposed diffs.

---

## 9. Testing plan

### Unit tests

- Trade PnL calculations
- R-multiple calculations
- Rule evaluation
- Provider adapter parsing
- Graph edge creation
- Strategy schema validation
- Backtest order lifecycle

### Integration tests

- Upload PDF -> chunks -> embeddings -> graph nodes
- Import trades -> classify losses -> graph updates
- Chat query -> evidence retrieval -> cited answer
- Strategy article -> extracted rules -> personalized draft
- Backtest run -> metrics -> experiment record
- TradingView webhook -> normalized alert event

### E2E tests

Use Playwright:

- onboarding
- trade import
- journal entry
- article import
- strategy extraction review
- graph exploration
- chat evidence answer
- backtest run
- paper order preview

### AI evals

Create gold datasets for:

- rule extraction from known strategy articles
- contradiction detection
- trade classification
- hallucination checks
- source citation accuracy
- strategy personalization quality

---

## 10. Security, privacy, and compliance

### Security requirements

- Encrypt API keys at rest.
- Do not log secrets.
- Per-user tenant isolation.
- Audit all AI actions and MCP tool calls.
- Rate limit upload, chat, webhooks, provider calls.
- Malware scan uploads if cloud-hosted.
- Signed webhook URLs.
- Optional local-only mode.
- Clear user consent before sending private vault data to cloud LLMs.

### Compliance positioning for MVP

MVP should be positioned as:

```text
trading journal
research assistant
backtesting/paper simulation
education and analytics
```

Avoid positioning as:

```text
registered advisor
live signal service
guaranteed profitable strategy generator
autonomous live trading advisor
```

Include legal review before:

- personalized buy/sell recommendations
- live broker integration
- paid signal features
- copy-trading
- asset-management-like features
- performance marketing claims

---

## 11. Development roadmap

### Phase 0 — Setup, architecture, design system

Deliverables:

- Monorepo
- Docker Compose local stack
- Postgres + pgvector
- Redis
- Next.js app shell
- FastAPI service
- Worker service
- Basic auth
- shadcn design system
- Playwright E2E setup
- CI pipeline

Acceptance criteria:

- Developer can run full stack locally with one command.
- User can sign in and see empty dashboard.
- Database migrations run cleanly.

### Phase 1 — Vault and trade journal MVP

Deliverables:

- Manual trades
- CSV import
- Journal entries
- Strategy/setup/routine tags
- Attachments
- Basic dashboards

Acceptance criteria:

- User can import trades and see PnL/R metrics.
- User can attach notes/screenshots.
- Metadata is stored cleanly and queryable.

### Phase 2 — Embeddings and graph MVP

Deliverables:

- Source uploads
- Chunking
- Embeddings
- Graph nodes/edges
- Graph UI
- Semantic search

Acceptance criteria:

- Uploaded article appears in vault and search.
- Trades, strategies, mistakes, and sources appear as graph nodes.
- Clicking graph nodes shows evidence.

### Phase 3 — GraphRAG chat

Deliverables:

- Chat UI
- Retrieval pipeline
- Evidence panel
- Structured analytics tools
- Source citations

Acceptance criteria:

- Chat can answer questions about user trades with evidence.
- Chat can find relationships across notes, trades, and sources.
- Chat refuses unsupported claims or labels confidence as low.

### Phase 4 — Strategy Creator

Deliverables:

- Article/PDF strategy extraction
- Rule extraction review UI
- Strategy genome object
- Contradiction Radar
- Personalized strategy diff
- Pine/Python draft generator

Acceptance criteria:

- User can upload a complex article and get extracted setup/entry/exit/risk rules.
- User sees source provenance for each rule.
- App identifies at least simple contradictions with existing playbook.
- App creates a personalized draft strategy without overwriting the old one.

### Phase 5 — Backtest and paper lab

Deliverables:

- Internal backtesting engine
- Backtest UI
- Strategy variants
- Paper experiment records
- Promotion score
- Overfitting checks

Acceptance criteria:

- User can run a backtest on a strategy version.
- App stores trades, metrics, equity curve, and provenance.
- App blocks promotion when sample size or robustness is insufficient.

### Phase 6 — Provider Mesh and integrations

Deliverables:

- Mandatory provider research sprint
- `docs/provider_matrix.md` and `docs/provider_matrix.csv`
- `docs/provider_setup_requests.md` for founder/API-key actions
- API key vault
- Provider router
- Per-provider and per-key quota tracking
- Circuit breaker and fallback system
- Alpha Vantage/Twelve Data/SEC/FRED/CoinGecko/FMP adapters
- TradingView webhook receiver
- Alpaca paper adapter
- MCP server read-only tools

Acceptance criteria:

- Developers deliver a verified provider matrix with free/free-start/no-key options and limits.
- Developers tell the founder exactly which keys/accounts are needed and which are optional.
- Missing credentials create setup requests instead of silent failures.
- Market data request can fail over to another provider.
- Quota exhaustion or rate limiting routes to the next legal compatible provider.
- All provider data has provenance.
- TradingView alert creates an event.
- Alpaca paper order preview works in sandbox mode.
- MCP client can query trades and strategies read-only.

### Phase 7 — Shadow Trader and controlled paper autonomy

Deliverables:

- Shadow Trader agent
- Paper-only policies
- Risk constraints
- Kill switch
- Audit log
- User approval flow

Acceptance criteria:

- Shadow Trader can simulate playbook trades.
- Paper agent cannot exceed max daily loss, max trades/day, or strategy whitelist.
- Every action is auditable.

---

## 12. Definition of done

A feature is done only if:

- It works locally via Docker Compose.
- It has API tests.
- It has at least one E2E test if user-facing.
- AI outputs are stored with model/context provenance.
- User data is tenant-scoped.
- It has error handling and observability.
- It has clear empty/loading/error UI states.
- It does not silently mutate strategy rules.
- It follows paper-only safety rules for execution.
- Third-party dependencies are documented in `SETUP_REQUESTS.md` or `docs/provider_setup_requests.md`.
- Missing API keys or external setup produce clear user/developer setup requests.
- Provider integrations document limits, fallback behavior, and license assumptions.

---

## 13. Immediate developer tasks

Create tickets for:

1. Create monorepo and Docker Compose stack.
2. Add Postgres + pgvector migration.
3. Implement user/auth skeleton.
4. Implement trade schema and manual trade CRUD.
5. Implement broker CSV import abstraction.
6. Implement source upload + object storage.
7. Implement text chunking pipeline.
8. Implement embedding provider abstraction.
9. Implement memory_chunks table and semantic search.
10. Implement kg_nodes/kg_edges tables.
11. Implement graph creation for trades/strategies/mistakes.
12. Implement graph UI MVP.
13. Implement GraphRAG retrieval pipeline.
14. Implement chat with evidence panel.
15. Implement strategy extraction schema.
16. Implement article-to-strategy extraction worker.
17. Implement strategy diff/personalization UI.
18. Implement provider mesh interface.
19. Run API-provider research sprint and create `docs/provider_matrix.md` + `.csv`.
20. Create `docs/provider_setup_requests.md` listing all founder-required keys/accounts/software.
21. Implement encrypted API key vault.
22. Implement provider quota/rate-limit ledger.
23. Implement provider fallback router and circuit breaker states.
24. Implement Alpha Vantage, SEC EDGAR, FRED, CoinGecko adapters.
25. Implement TradingView webhook receiver.
26. Implement internal backtest MVP.
27. Implement audit_events table and logging.
28. Implement MCP server read-only tools.
29. Implement Playwright E2E smoke tests.

---

## 14. Founder/developer handoff requirements

Developers must be proactive about telling the founder what they need. They should not wait until a feature is blocked to ask for access. At the start of every sprint, the team should provide a short dependency checklist:

```text
What we can build without external setup
What needs a free key
What needs a paid account or billing card
What needs OAuth/app approval
What needs local software installed
What is optional
What is currently blocking implementation
```

Example founder request format:

```text
Need: Alpha Vantage API key
Why: Fallback daily/intraday equities data
Priority: Useful but not blocking because SEC/FRED/CoinGecko/no-key sources can still be built
Where to put it: Provider Settings → Alpha Vantage, or .env as ALPHA_VANTAGE_API_KEY for local dev
Security: Do not send through Slack/plain text if avoidable; use password manager or app credential vault
```

Examples of likely founder-provided items:

```text
Figma design file access
GitHub repository access
market-data API keys
Alpaca paper-trading account and keys
TradingView account/webhook configuration
FRED key
Alpha Vantage key
Twelve Data key
FMP key
CoinGecko key if needed
cloud hosting account
object storage bucket
observability/Sentry account
email provider account
local Docker/Ollama setup approval
```

Each integration ticket must include a “Founder setup needed?” field with one of:

```text
none
optional_key
required_key
required_account
requires_paid_plan
requires_legal_or_license_review
requires_local_software
```

---

## 15. Final product principle

The durable moat is not TradingView automation. The durable moat is the user’s personal trading memory graph: how they think, what they trade, why they lose, what research they trust, which routines help, and which strategy variants actually survive evidence.

Build the memory and graph first. Then build autonomy around it.
