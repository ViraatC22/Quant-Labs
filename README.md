# Quant Labs

Research and experiments for quantitative finance ideas.

## Trading Intelligence OS

This repository is the local-first implementation of a personal trading
intelligence operating system: a vault, trade journal, knowledge graph, and
paper-trading research lab that treats TradingView and broker/data APIs as
adapters around the core memory system.

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

- Capture vault notes, articles, strategy notes, and tagged sources.
- Log journal entries, emotional state, and routine completion.
- Log closed trades and calculate P&L / win-rate metrics.
- View a lightweight strategy graph snapshot from local records.
- Import/export the local workspace as JSON.

Browser-entered records are stored in local browser storage until the database
persistence path is wired into the UI.

The MVP is research, journaling, and paper-only experimentation. Live
autonomous trading is intentionally out of scope.
