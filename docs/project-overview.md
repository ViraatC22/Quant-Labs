# Project Overview

Quant Labs is a local-first Trading Intelligence OS: a personal trading memory system that connects research, journal entries, trade logs, strategy rules, emotions, routines, vault sources, and graph relationships.

The product thesis is that the durable system is the trader's memory graph. TradingView, broker APIs, market-data providers, and future MCP tools are adapters around that core.

## Local Development

```bash
cp .env.example .env
docker compose up --build
```

Current local URLs:

- Web app: `http://localhost:3000`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- MinIO console: `http://localhost:9001`

## Current App Functionality

- Capture vault records from links or file uploads.
- Auto-fill vault title, type, source, extracted body, generated tags, and strategy information.
- Log journal entries, emotional state, tags, and routine completion.
- Log closed trades and calculate P&L / win-rate metrics.
- View derived trading insights based on strategies, trades, setups, states, routines, and vault sources.
- Explore an Obsidian-style map linking trades, strategies, symbols, setups, emotions, journal entries, vault sources, and tags.
- Import/export the browser-local workspace as JSON.
- Use the shadcn-style UI foundation, dark mode, and restrained animated shell.

Browser-entered records are stored in local browser storage until the database persistence path is wired into the UI.

The MVP is research, journaling, and paper-only experimentation. Live autonomous trading is intentionally out of scope.
