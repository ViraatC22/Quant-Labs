# Setup Requests

This checklist tracks third-party accounts, local software, API keys, billing
toggles, OAuth apps, and founder decisions needed by the Trading Intelligence OS.

## Current Sprint Dependency Summary

| Category | Status |
| --- | --- |
| What we can build without external setup | Monorepo, local Docker stack, FastAPI API, Next.js shell, schema/migrations, vault/trade/journal CRUD, graph storage skeleton |
| What needs a free key | Alpha Vantage, FRED, Twelve Data, Financial Modeling Prep, CoinGecko Demo if/when provider mesh starts |
| What needs a paid account or billing card | None for Phase 0/1; optional later for premium market data, cloud hosting, observability |
| What needs OAuth/app approval | GitHub OAuth only if product auth uses GitHub later |
| What needs local software installed | Docker Desktop for full local stack; optional Ollama for local LLM mode later |
| What is optional | Alpaca paper keys, TradingView webhook setup, Figma access, Sentry, Ollama |
| What is currently blocking implementation | Nothing for Phase 0/1 local-first scaffold |

## Docker Desktop

```text
Service name: Docker Desktop
Why it is needed: Runs the local Postgres + pgvector, Redis, MinIO, API, worker, and web app stack.
Required account tier, if known: Free desktop install is sufficient for local development.
Whether a free tier/free API key is available: No API key required.
Exact credentials needed: None.
Whether payment method is required: No.
Whether the integration is optional or blocking: Blocking for one-command local stack; not blocking for code scaffolding.
Local setup steps, if any: Install Docker Desktop and start the Docker daemon before running `docker compose up --build`.
Security notes: Do not mount directories containing private credentials into containers unless explicitly needed.
Who owns setup: Founder.
Date last verified: 2026-07-04.
```

## Postgres + pgvector

```text
Service name: Postgres + pgvector
Why it is needed: Stores tenant-scoped trades, journal entries, vault documents, knowledge graph records, and vector memory chunks.
Required account tier, if known: Local Docker image for MVP.
Whether a free tier/free API key is available: No API key required locally.
Exact credentials needed: Local database username/password from `.env`.
Whether payment method is required: No.
Whether the integration is optional or blocking: Blocking for full API persistence.
Local setup steps, if any: Provided by Docker Compose using `pgvector/pgvector`.
Security notes: Use development-only credentials locally; never commit `.env`.
Who owns setup: Developer for local config; founder for any future managed database account.
Date last verified: 2026-07-04.
```

## Redis

```text
Service name: Redis
Why it is needed: Queue/cache foundation for ingestion, embeddings, extraction, and backtest workers.
Required account tier, if known: Local Docker image for MVP.
Whether a free tier/free API key is available: No API key required locally.
Exact credentials needed: None for local MVP.
Whether payment method is required: No.
Whether the integration is optional or blocking: Optional for current API scaffold; blocking for async worker jobs.
Local setup steps, if any: Provided by Docker Compose.
Security notes: Do not expose Redis publicly without auth/network controls.
Who owns setup: Developer locally.
Date last verified: 2026-07-04.
```

## MinIO / Object Storage

```text
Service name: MinIO local object storage
Why it is needed: Stores uploaded PDFs, screenshots, broker CSV imports, and generated reports in local-first mode.
Required account tier, if known: Local Docker image for MVP.
Whether a free tier/free API key is available: Local access keys are generated in `.env`.
Exact credentials needed: MINIO_ROOT_USER, MINIO_ROOT_PASSWORD.
Whether payment method is required: No.
Whether the integration is optional or blocking: Optional for metadata-only vault routes; blocking for actual file upload persistence.
Local setup steps, if any: Provided by Docker Compose.
Security notes: Use local development credentials only; rotate any shared cloud object-storage keys.
Who owns setup: Developer locally; founder for future cloud bucket.
Date last verified: 2026-07-04.
```

## OpenAI / Anthropic / Local LLM Providers

```text
Service name: AI model providers
Why it is needed: Later phases need structured extraction, embeddings, GraphRAG chat, strategy compilation, and insight generation.
Required account tier, if known: Provider-dependent; local Ollama can be used without cloud API keys.
Whether a free tier/free API key is available: Provider-dependent.
Exact credentials needed: OPENAI_API_KEY, ANTHROPIC_API_KEY, or local Ollama base URL when enabled.
Whether payment method is required: Provider-dependent; not required for Phase 0/1 scaffold.
Whether the integration is optional or blocking: Optional until embeddings/GraphRAG phases.
Local setup steps, if any: Optional Ollama installation and model pull.
Security notes: Never commit model API keys; require explicit user consent before sending private vault data to cloud LLMs.
Who owns setup: Founder for paid keys; developer for provider abstraction.
Date last verified: 2026-07-04.
```

## Alpaca Paper Trading

```text
Service name: Alpaca paper trading
Why it is needed: Later paper-order preview and sandbox broker adapter.
Required account tier, if known: Paper trading account.
Whether a free tier/free API key is available: Paper trading is available without live trading setup.
Exact credentials needed: ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL for paper endpoint.
Whether payment method is required: Not expected for paper-only mode, but founder should verify account requirements.
Whether the integration is optional or blocking: Optional; not blocking for Phase 0-5 internal simulator.
Local setup steps, if any: Create Alpaca account, enable paper trading, store keys in `.env` or credential vault.
Security notes: Treat paper keys as secrets; never enable live endpoints by default.
Who owns setup: Founder.
Date last verified: 2026-07-04.
```

## TradingView Webhooks

```text
Service name: TradingView webhooks
Why it is needed: Later adapter for alert ingestion and manual chart workflow.
Required account tier, if known: TradingView plan must support webhooks.
Whether a free tier/free API key is available: No API key; account feature availability must be verified.
Exact credentials needed: Signed webhook secret generated by the app; TradingView alert webhook URL.
Whether payment method is required: Plan-dependent.
Whether the integration is optional or blocking: Optional adapter; not core platform.
Local setup steps, if any: Configure an alert to POST to the app webhook endpoint once implemented.
Security notes: Use signed webhook URLs and never auto-place orders from webhooks in MVP.
Who owns setup: Founder for TradingView account; developer for receiver.
Date last verified: 2026-07-04.
```
