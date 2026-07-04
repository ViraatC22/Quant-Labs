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

The MVP is research, journaling, and paper-only experimentation. Live
autonomous trading is intentionally out of scope.
