# Quant Labs

Research and experiments for quantitative finance ideas.

## Trading Intelligence OS

This repository is the local-first implementation of a personal trading
intelligence operating system: a vault, trade journal, knowledge graph, and
paper-trading research lab that treats TradingView and broker/data APIs as
adapters around the core memory system.

## Documentation

Start with [`docs/README.md`](docs/README.md) for the full documentation hub,
including architecture, setup requests, environment variables, UI-system notes,
repository map, and imported product planning files.

## Local Development

```bash
cp .env.example .env
docker compose up --build
```

Services:

- Web app: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001

Current app functionality:

- Cover **indices, commodities, FX, and crypto** on one desk. Index and
  commodity futures (ES, NQ, YM, RTY, GC, SI, CL, NG, HG) resolve through
  broker-style aliases (`US500`, `NAS100`, `US30`, `GOLD`, `OIL`, `BRENT`,
  `COPPER`, …), and the futures leg is preferred over cash indices because the
  upstream feed publishes volume for `=F` contracts and none for `^` cash
  indices — so Flow and the participation signal actually work on ES/NQ/GC
  where they stay dark on FX. A CME Globex session (18:00→17:00 ET, Sun–Fri,
  with the daily maintenance break) sits alongside the London/NY/Sydney/Tokyo
  clocks, so index futures no longer read "closed" on a Sunday evening.
  Capital flow ranks cross-asset; currency strength stays FX-only, since an
  index has no second currency to decompose into.
- Open on a Dashboard with per-instrument macro bias cards whose direction and
  confidence are computed from market data (trend vs. ATR, path efficiency,
  RSI tilt, volume as confirmation-only), never asserted by a model. Every
  card exposes its signals and the exact confidence arithmetic, states its
  price basis (top-of-book / last trade / indicative mid), and declares proxy
  instruments (spot gold is served by GC=F futures with the basis caveat
  shown). An optional AI provider may rephrase the explanation but is rejected
  if it invents news or contradicts the derived direction.
- Show London/New York/Sydney/Tokyo session phases with DST-correct countdowns,
  a "For You" briefing summarizing the desk with genuine bias-change detection
  backed by persisted snapshots (a change is only reported when a stored prior
  reading materially differs), currency-strength decomposition across 17 FX
  pairs, a capital-flow ranking, and an FMP news rail that reports itself
  unavailable rather than showing placeholder headlines.
- Chart tab embedding TradingView's free widget beside Quant Labs' own quote
  (the only price the trade ticket uses), with divergence warnings where the
  two feeds show different instruments, and a one-click handoff that prefills
  the trade form at the current quote.
- Economic calendar from the ForexFactory weekly feed (UTC-verified,
  windows-1252-safe): impact tiers, consensus forecasts, previous/actual
  values, currency and impact filters, and a within-the-hour highlight for
  imminent high-impact events.
- Per-instrument deep dive wiring a TradingView chart, Flow/Bearing/Pulse, the
  full indicator table, the bias derivation, per-instrument headlines, a
  derived market-conditions score, a cross-asset Risk-On/Off mood gauge
  (descriptive, sign-correct on yen/franc havens), and the trade-record Edge
  Factor (explicitly labelled as scoring your record, not market conditions).
- Generate an idempotent Daily Report per day — instrument outlooks, today's
  events with consensus, currency strength, caveats — stored so the archive is
  a record, plus **verifiable grading of prior desk calls**: each graded
  verdict compares the stored call-time price against the price now, and calls
  that cannot be graded say why instead of being scored.
- Show per-instrument headlines on bias cards (retrieved data, never invented);
  an optional AI provider may weave ONLY retrieved headlines into the card
  prose — fabrication-marker terms are admitted solely when they appear in a
  supplied headline, and direction contradictions are still rejected.
- Visualize the journal: performance heatmap, P&L by weekday, a six-axis trade
  quality radar measured from stored fields only, and deterministic focus
  actions naming best/worst symbol/strategy/state groups with 3+ closed trades.
- Attach derived context lines to calendar events (consensus vs previous,
  actual vs consensus once printed, session-open proximity, current currency
  strength) with no invented per-event confidence.
- **Learn from its own record**: every bias call is graded exactly once, 8–48h
  later, against what price actually did; once a bucket accumulates 20+ graded
  calls, the displayed confidence is blended toward the measured hit rate
  (evidence-weighted shrinkage, capped, neutral calls exempt). Snapshots store
  the raw engine confidence so calibration never feeds on its own output, and
  the dashboard Track Record panel shows hit rates per bucket next to a
  coin-flip luck baseline computed on the same graded windows.
- Accept TradingView alert webhooks (`POST /api/v1/webhooks/tradingview`) that
  create and close trade **records** with computed P&L — never orders. The
  endpoint is disabled until `TRADINGVIEW_WEBHOOK_SECRET` is set, compares
  secrets constant-time, and deduplicates retried deliveries by alert id.
- Run an evidence-aware Session Desk across pre-session briefs, a grounded macro
  desk, manually confirmed catalyst planning, instrument deep dives, a
  decomposable Edge Factor, behavior coaching, and daily reports. Missing live
  feeds remain explicitly unknown instead of being replaced with fabricated
  market narratives.
- Calculate delayed market context from hourly bars: RSI(14), ATR%, Bollinger
  width, volume percentile, trend efficiency, and derived Flow/Bearing/Pulse
  states with provider, timestamp, sample size, and limitations shown.
- Preserve verified catalysts and daily report snapshots on-device, show four
  global session clocks, and review weekday P&L plus six-axis trade-record
  completeness without mislabelling coverage as trading skill.
- Capture vault records from links or file uploads with title, type, source,
  body, tags, strategy fields, and AI-router metadata auto-filled.
- Resolve arXiv PDF links into paper title, authors, abstract, subject,
  comments, implementation notes, and source detail cards instead of storing
  opaque PDF placeholders. If the arXiv Atom feed misses a fresh paper, imports
  fall back to the paper's abs page and saved placeholders/noisy records are
  repaired on vault load.
- Extract trading technicals such as VWAP, FVG, liquidity sweeps, order blocks,
  support/resistance, sessions, risk rules, and timeframe context from sources.
- Learn each saved source into memory chunks and a knowledge graph of source,
  strategy, setup, indicator, market, timeframe, rule, and tag nodes.
- Route source enrichment through deterministic local rules by default, with
  opt-in provider routing for OpenRouter, Groq, Gemini, and Cerebras keys.
- Log journal entries, emotional state, and routine completion.
- Log closed or in-progress equity, option, futures, crypto, and forex trades
  through a compact ticket with an advanced parameters dropdown or a one-line
  quick entry, then calculate realized and live-marked P&L using contract
  multipliers, win-rate, setup, state, and strategy metrics.
- Fetch delayed live quotes through the market-data adapter to fill entry/target
  exits, mark open trades by display or quote symbol, and close in-progress
  trades from collapsible trade history rows.
- Place live paper trades from the ticket at the latest quote, keep them open
  in an active positions panel, refresh marks while they are in progress, and
  close them at the current quote.
- Generate trade recommendations from uploaded strategies, extracted
  technicals, learned source memory, matching closed-trade history, and market
  compatibility tags such as options-ready, futures-ready, or not
  options-specific.
- Fill the trade form from a source-backed recommendation draft, including
  symbol, asset class, quote symbol, side, strategy, setup, quote-backed
  entry/exit prices, quantity, fees, risk/stop/target, option/futures
  parameters, emotion, and notes.
- Evaluate plain-English strategy ideas against the current knowledge base,
  assign technical tags, explain included/excluded evidence, fill a trade draft
  when useful, and log the AI evaluation into the journal.
- Generate an optimal knowledge-base strategy card with an included/excluded
  rationale dropdown and a trade-draft handoff.
- Use a dedicated Routine tab that turns extracted strategy rules into a
  recommended routine, how-to-trade plan, setup criteria, execution timing, and
  risk/review steps.
- Blend imported source insights into the current strategy scoreboard so new
  sources create research candidates and influence existing strategy nodes.
- Move through the Strategy Atlas as an abstract galaxy: Trading Memory is the
  core, sources, strategies, setups, trades, symbols, states, and tags drift on
  orbital rings, and selecting a node freezes motion for stable inspection.
  Learned entities expand lazily by 1–3 hops; edge inspection shows source
  chunks and confidence, conflict badges mark disputed nodes, evidence density
  can color edges, and ⌘K entity results focus the Atlas directly.
- Review richer insight cards covering net edge, strategy leaks, source-backed
  validation gaps, routine effect, and AI-router status.
- Keep source technicals concise in the UI by prioritizing essential tags,
  read-more sections for long generated content, compact source details, and
  short entry/exit/risk evidence.
- Import/export the local workspace as JSON.
- Ask questions of your trading memory in the Research tab and get answers
  assembled only from your saved sources and trades, with a citation on every
  claim, a trust score for how much of the answer is evidence-backed, and an
  explicit refusal when there is no evidence rather than a fabricated answer.
- Search sources semantically (embedding + keyword hybrid), collapse the same
  entity written different ways ("FVG" and "fair value gap") into one graph
  node, and surface conflicts side by side when two sources disagree about the
  same claim.
- Expose the same memory (search, ask, entities, conflicts) to other assistants
  through a read-only MCP server (`services/mcp`).

When the API is available, records persist to the local API database. If the API
is offline, writes go to a durable local queue and are optimistically shown;
the app auto-recovers and replays the queue in order when the API returns, so no
offline work is lost (records use client UUIDs, so replay is idempotent). P&L is
computed server-side including the contract multiplier and rendered from the
server, and quotes are cached server-side with a stale-value fallback.

Saved sources are chunked (boundary-aware, overlapping) and embedded, then
linked into a graph of strategies, setups, indicators, rules, and tags plus a
first-class **claims** layer (atomic subject–predicate–object assertions with
per-source evidence). Two facts about the same thing under different names are
resolved to one graph node by embedding similarity, and two sources that
disagree open a **conflict** you can review. A grounded research endpoint
(`POST /api/v1/research/ask`, and the Research tab) answers questions from
that memory only. Trade-review questions retrieve the matching journal row
before its playbook, and a configured API-key chat model writes a concise
answer whose citations are validated before display. Without a key—or when a
model response fails validation—the local grounded writer takes over. The
**evidence coverage** meter reports citation coverage, not truth or confidence;
the writer refuses rather than fabricate when it has none. Semantic search over
chunks ships too (`GET /api/v1/research/search`).
A read-only MCP server (`services/mcp`) exposes the same tools to other
assistants. Embeddings default to a dependency-free local provider so all of
this runs offline; set `EMBEDDING_PROVIDER=ollama` for full neural embeddings
(see [`docs/architecture.md`](docs/architecture.md) and
[`docs/lattice-merge-plan.md`](docs/lattice-merge-plan.md)).

The MVP is research, journaling, and paper-only experimentation. Live
autonomous trading is intentionally out of scope.

## Development

Install the API development dependencies into `services/api/.venv` and the web
dependencies with `npm ci --prefix apps/web`, then run the canonical local
quality gate from the repository root:

```bash
npm run verify
```

This runs API lint, type checking, and tests; web lint, type checking, tests,
and a production build; and validates the Compose file when Docker is
available. A missing Docker CLI is reported as an explicit local limitation;
CI independently exercises the PostgreSQL migration and drift path.

The individual commands remain:

```bash
# API (from services/api): lint, type-check, test
ruff check app tests && pyright app && pytest

# Web (from apps/web): lint, type-check, unit tests, build
npm run lint && npm run typecheck && npm test && npm run build
```

CI runs these on every push, plus a PostgreSQL job that applies the Alembic
migrations and checks the ORM models for schema drift.
