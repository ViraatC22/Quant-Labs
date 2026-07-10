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
- Review richer insight cards covering net edge, strategy leaks, source-backed
  validation gaps, routine effect, and AI-router status.
- Keep source technicals concise in the UI by prioritizing essential tags,
  read-more sections for long generated content, compact source details, and
  short entry/exit/risk evidence.
- Import/export the local workspace as JSON.
- Ask questions of your trading memory on the `/research` page and get answers
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
(`POST /api/v1/research/ask`, and the `/research` page) answers questions from
that memory only — every claim is cited and a **trust score** shows the share
of the answer backed by real evidence; it refuses rather than fabricate when it
has none. Semantic search over chunks ships too (`GET /api/v1/research/search`).
A read-only MCP server (`services/mcp`) exposes the same tools to other
assistants. Embeddings default to a dependency-free local provider so all of
this runs offline; set `EMBEDDING_PROVIDER=ollama` for full neural embeddings
(see [`docs/architecture.md`](docs/architecture.md) and
[`docs/lattice-merge-plan.md`](docs/lattice-merge-plan.md)).

The MVP is research, journaling, and paper-only experimentation. Live
autonomous trading is intentionally out of scope.

## Development

```bash
# API (from services/api): lint, type-check, test
ruff check app tests && pyright app && pytest

# Web (from apps/web): lint, type-check, unit tests, build
npm run lint && npm run typecheck && npm test && npm run build
```

CI runs these on every push, plus a PostgreSQL job that applies the Alembic
migrations and checks the ORM models for schema drift.
