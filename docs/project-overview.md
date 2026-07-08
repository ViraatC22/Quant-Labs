# Project Overview

Quant Labs is a local-first Trading Intelligence OS: a personal trading memory system that connects research, journal entries, trade logs, strategy rules, emotions, routines, vault sources, and graph relationships.

The product thesis is that the durable system is the trader's memory graph. TradingView, broker APIs, market-data providers, and future MCP tools are adapters around that core.

## Local Development

Full stack (Postgres + Redis + MinIO + API + worker + web) via Docker:

```bash
cp .env.example .env
docker compose up --build
```

Without Docker, the API and web app run standalone. The API defaults to a local
SQLite database (created automatically), so no external services are required:

```bash
# API — http://localhost:8000 (schema auto-created on first run)
cd services/api
python -m venv .venv && .venv/bin/pip install -e .
.venv/bin/uvicorn app.main:app --port 8000

# Web — http://localhost:3000 (in a second terminal)
npm --prefix apps/web install
npm --prefix apps/web run dev
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

Persistence is offline-first. When the API is reachable ("API online" in the
header) trades, journal entries, and vault documents are persisted server-side
(Postgres in Docker, SQLite standalone) and are the source of truth on load.
When the API is unreachable, writes are applied optimistically and recorded in a
durable local queue; a periodic health check replays that queue in order the
moment the API returns, before re-reading server state, so nothing created
offline is lost. Records carry client-generated UUIDs so a replay is idempotent
(a duplicate is a no-op). A server rejection is surfaced to the user rather than
silently dropping the app into offline mode. Export/import JSON works in both
modes.

P&L is computed server-side (the single source of truth) and includes the
contract multiplier, so futures and options are correct; the UI renders the
server's value. Market quotes are cached server-side for a short window and fall
back to the last good value if the upstream provider is down.

Note on "memory": saved sources are chunked and linked into a keyword- and
graph-based knowledge map today. Embedding-based semantic search and GraphRAG
chat are on the roadmap (see [architecture.md](architecture.md)), not yet
shipped — the map does not do vector similarity yet.

The MVP is research, journaling, and paper-only experimentation. Live autonomous trading is intentionally out of scope.
