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
- Log closed or in-progress trades through detailed fields or a compact
  one-line quick entry, then calculate realized and live-marked P&L, win-rate,
  setup, state, and strategy metrics.
- Fetch delayed live quotes through the market-data adapter to fill entry/target
  exits, mark open trades, and close in-progress trades from the trade table.
- Place live paper trades from the ticket at the latest quote, keep them open
  in an active positions panel, refresh marks while they are in progress, and
  close them at the current quote.
- Generate trade recommendations from uploaded strategies, extracted
  technicals, learned source memory, and matching closed-trade history.
- Fill the trade form from a source-backed recommendation draft, including
  symbol, side, strategy, setup, quote-backed entry/exit prices, quantity, fees,
  emotion, and notes.
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
- Move through the Strategy Atlas with spaced source, strategy, setup, trade,
  journal, tag, state, and market groups plus pan, zoom, focus, and node detail.
- Review richer insight cards covering net edge, strategy leaks, source-backed
  validation gaps, routine effect, and AI-router status.
- Keep source technicals concise in the UI by prioritizing essential tags,
  compact source details, and short entry/exit/risk evidence.
- Import/export the local workspace as JSON.

When the API is available, records persist to the local API database. If the API
is offline, the web app falls back to browser-local storage.

The MVP is research, journaling, and paper-only experimentation. Live
autonomous trading is intentionally out of scope.
