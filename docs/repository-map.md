# Repository Map

This map lists the important files and folders for the current Quant Labs implementation.

## Root

| Path | Purpose |
| --- | --- |
| `README.md` | Short GitHub-facing project overview and local development entry point. |
| `AGENTS.md` | Agent instructions for this workspace. |
| `SETUP_REQUESTS.md` | Root copy of the setup checklist for quick access. Canonical docs copy: `docs/setup-requests.md`. |
| `.env.example` | Safe local environment template. |
| `docker-compose.yml` | Local stack for Postgres, Redis, MinIO, API, worker, and web. |
| `package.json` | npm workspace root. |
| `.github/workflows/ci.yml` | CI checks. |

## Web App

| Path | Purpose |
| --- | --- |
| `apps/web/src/app/page.tsx` | Main app route and health-aware shell. |
| `apps/web/src/app/layout.tsx` | Root layout and theme hydration boundary. |
| `apps/web/src/app/globals.css` | Tailwind base styles, CSS variables, light/dark tokens. |
| `apps/web/src/components/WorkspaceApp.tsx` | Main local-first trading workspace: vault, journal, trades, insights, and map. |
| `apps/web/src/components/ui/` | Owned shadcn-style primitives. |
| `apps/web/src/components/magic/` | Owned animated/special-effect components. |
| `apps/web/src/components/shell/` | App shell components such as header and theme toggle. |
| `apps/web/src/lib/utils.ts` | Shared `cn()` class helper. |
| `apps/web/components.json` | shadcn/ui configuration. |
| `apps/web/tailwind.config.ts` | Tailwind theme configuration. |
| `apps/web/package.json` | Web scripts and dependencies. |

## API

| Path | Purpose |
| --- | --- |
| `services/api/app/main.py` | FastAPI app factory and root health route. |
| `services/api/app/api/v1/vault.py` | Vault document, journal, URL import, file import, generated tags, and strategy extraction routes. |
| `services/api/app/api/v1/trades.py` | Trade routes. |
| `services/api/app/api/v1/graph.py` | Graph routes. |
| `services/api/app/models/domain.py` | SQLAlchemy domain models. |
| `services/api/app/schemas/` | Pydantic schemas. |
| `services/api/migrations/` | Alembic migrations. |
| `services/api/tests/` | API tests. |
| `services/api/pyproject.toml` | API dependencies and tool config. |

## Worker And Infrastructure

| Path | Purpose |
| --- | --- |
| `services/worker/app/main.py` | Placeholder worker entry point for future ingestion/extraction/backtest jobs. |
| `services/worker/pyproject.toml` | Worker package metadata. |
| `infra/postgres/init.sql` | Local Postgres/pgvector initialization. |

## Documentation

| Path | Purpose |
| --- | --- |
| `docs/README.md` | Documentation index. |
| `docs/project-overview.md` | Product summary and current behavior. |
| `docs/architecture.md` | Architecture thesis, build order, stack, and safety boundaries. |
| `docs/implementation-plan-v2.md` | Long-form developer implementation plan imported into the repo. |
| `docs/tradingview-adapter-thesis.md` | Product decision note on TradingView as an adapter. |
| `docs/setup-requests.md` | Full setup checklist. |
| `docs/provider_setup_requests.md` | Provider-specific setup tracker. |
| `docs/environment.md` | Environment variable reference. |
| `docs/UI-LIBRARY-IMPLEMENTATION.md` | UI system documentation. |
