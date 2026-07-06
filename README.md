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
- Learn each saved source into memory chunks and a knowledge graph of source,
  strategy, setup, indicator, market, timeframe, rule, and tag nodes.
- Route source enrichment through deterministic local rules by default, with
  opt-in provider routing for OpenRouter, Groq, Gemini, and Cerebras keys.
- Log journal entries, emotional state, and routine completion.
- Log closed trades through detailed fields or a compact one-line quick entry,
  then calculate P&L, win-rate, setup, state, and strategy metrics.
- Blend imported source insights into the current strategy scoreboard so new
  sources create research candidates and influence existing strategy nodes.
- Move through a dynamic strategy graph with pan, zoom, focus, node detail, and
  source/trade/journal/tag relationships.
- Review richer insight cards covering net edge, strategy leaks, source-backed
  validation gaps, routine effect, and AI-router status.
- Import/export the local workspace as JSON.

When the API is available, records persist to the local API database. If the API
is offline, the web app falls back to browser-local storage.

The MVP is research, journaling, and paper-only experimentation. Live
autonomous trading is intentionally out of scope.
