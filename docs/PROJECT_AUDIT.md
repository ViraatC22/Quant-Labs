# Quant Labs Project Audit

**Audit date:** 2026-07-29  
**Audited branch:** `automation/quant-labs-recovery`  
**Preserved pre-automation commit:** `2b23575cc385efbf7812592d34da8e06faee8923`

## 1. Project purpose

Quant Labs is a local-first trading intelligence workspace. Its coherent
current scope is research, evidence-backed question answering, a learning
vault, journaling, deterministic market-context analysis, a paper-trade log,
reports, and a provenance-aware knowledge graph. It is explicitly not a
live-money autonomous trading system.

The strongest sources of intent are the root README, `docs/architecture.md`,
`docs/evaluation-and-implementation-plan-v3.md`,
`docs/lattice-merge-plan.md`, and
`docs/senior-developer-technical-handoff.md`.

## 2. Existing architecture

- `apps/web`: Next.js 16, React, TypeScript, Tailwind, Vitest.
- `services/api`: FastAPI, Pydantic, SQLAlchemy, Alembic, SQLite for standalone
  development/tests, and PostgreSQL + pgvector for the container path.
- `services/mcp`: read-only access to the memory/research surface.
- `services/worker`: a deliberately inactive worker placeholder. No product
  flow currently relies on it.
- `docker-compose.yml`: PostgreSQL, Redis, MinIO, API, worker, and web services.
- `.github/workflows/ci.yml`: API lint/type/test, PostgreSQL migration and
  drift validation, and web lint/type/build/test.

The browser keeps a durable local mutation queue and replays idempotent writes
to the API. The API owns persistence, P&L calculations, market-data adapters,
research retrieval/writing, and desk analysis. AI import enrichment remains
opt-in; research writing validates citations and falls back to a deterministic
local writer.

## 3. Current functionality

Repository evidence and tests support the following completed scope:

- URL/file vault import, safe URL fetching, arXiv metadata recovery, chunking,
  embeddings, entity resolution, claims, conflicts, and semantic research.
- Cited research answers that refuse unsupported questions.
- Journal and paper-trade records, contract-aware P&L, buying-power guards,
  delayed quote adapters, trade recommendations, and strategy evaluation.
- Dashboard, chart, economic calendar, cross-asset strength, session desk,
  bias snapshots/calibration, daily reports, journal insights, and Atlas graph
  exploration.
- Secret-gated, idempotent TradingView webhooks that write records only and
  never place orders.
- Local and CI quality gates across Python and TypeScript.

## 4. Broken functionality

No locally reproducible product or build failure remains in the audited tree.
The first type-check invocation failed only because Pyright was launched
outside the Python virtual environment; the documented activated-environment
invocation completed with zero errors.

Live upstream market/news/calendar responses, cloud AI providers, Ollama, and
TradingView delivery were not exercised because they require network access,
local services, or credentials. Their deterministic boundaries and failure
states are covered by local tests.

## 5. Missing functionality

These are deliberate or optional gaps, not blockers for the coherent current
product:

- Real session authentication. Non-local deployments ignore the unauthenticated
  `x-user-id` header and bind requests to the demo user, but multi-user hosting
  is not ready.
- An async ingestion/backtest worker. The worker container remains a documented
  placeholder and no shipped flow depends on it.
- Broker execution and autonomous live trading. Both are explicitly outside
  the MVP safety boundary.
- Browser end-to-end automation for the principal workspace flow. Unit/API
  coverage and production compilation exist, but a repeatable E2E suite does
  not.

## 6. Build and runtime problems

No build problem is currently known. Verification on 2026-07-29 produced:

- API: Ruff passed; Pyright passed in the activated virtual environment;
  241 Pytest tests passed.
- Web: ESLint passed; TypeScript passed; 50 Vitest tests passed; Next.js
  production build passed.

The PostgreSQL container/migration path is enforced in CI but was not started
locally during this audit. A local one-command verification entry point is
missing and is the first recovery task.

## 7. Dependency problems

- The checked-in lockfile supports reproducible web installation with
  `npm ci`.
- The API has declared runtime and development dependencies in `pyproject.toml`
  but no committed Python lockfile. This is acceptable for the current pip/CI
  workflow, though exact transitive reproducibility remains weaker than the web.
- The local API virtual environment uses Python 3.13 while CI uses supported
  Python 3.12; the full API suite passes locally.

## 8. Security concerns

Verified protections:

- Real `.env` files and local databases are ignored.
- User-supplied URL imports use public-IP validation and validate redirects.
- Cloud import enrichment is opt-in.
- The TradingView webhook is disabled without a secret, uses constant-time
  comparison, and is idempotent.
- The unauthenticated user header is trusted only when explicitly enabled for
  local development.

Remaining security boundary:

- Quant Labs is a single-user local application until real authentication,
  authorization, production secret management, and hosted rate limits exist.
  It must not be represented as multi-user production-ready.

No secret signature was found in the preserved staged diff. Local `.env` files
were neither read nor staged.

## 9. Testing gaps

- No browser E2E suite covers the complete dashboard → research → paper-log
  principal flow.
- External provider contracts are mocked locally and need credentialed smoke
  checks before provider-specific deployment claims.
- PostgreSQL migration/drift checks run in CI rather than this local recovery
  session.
- The FastAPI test client emits one upstream deprecation warning.

## 10. Documentation gaps

The README, documentation hub, architecture, environment guide, plans, and
technical handoff are substantial and current. Missing recovery-specific
documents were this audit, an executable completion plan, and a final status.
The README also lacks a single canonical local verification command.

## 11. Deployment gaps

- Docker Compose defines a reproducible local stack; no production hosting
  target is declared.
- Deployment would require real authentication, external secret management,
  persistent storage/backups, health/observability policy, and explicit
  provider configuration.
- The worker is not production functionality and should remain described as a
  placeholder until a real queued workload lands.

## 12. Accessibility and usability gaps

The web build and unit tests pass, and feature panels include explicit
unavailable/unknown states. This audit did not include assistive-technology or
keyboard-only browser testing. A future E2E milestone should include axe,
focus-order, dialog, and reduced-motion checks.

## 13. Completion definition

The current coherent scope is complete when:

1. Intentional pre-automation work is preserved on a recovery branch.
2. API lint, type checks, tests and web lint, type checks, tests, and production
   build pass through one documented command.
3. Unrelated local academic artifacts remain preserved but do not pollute Git
   status.
4. README, completion plan, and final status accurately describe commands,
   verified scope, deferred scope, Git state, and external limitations.
5. The tested recovery branch is pushed to the configured owner repository.

## 14. Prioritized implementation plan

1. Add the canonical repository verification command and document it.
2. Add precise ignore rules for the unrelated local academic artifacts without
   deleting them.
3. Run the full canonical gate and Docker Compose configuration validation.
4. Publish final status and push the tested recovery branch.
5. Future: browser E2E + accessibility; production authentication; async worker
   only when a real queued workload requires it.

## 15. Known blockers and assumptions

- No blocker prevents local completion.
- Credentialed external-provider behavior remains a manual deployment check.
- Production hosting is deferred because the repository contains no selected
  deployment target and real multi-user authentication is absent.
- `CS_Beekman_Chauhan.pdf`, `deepfake-poster/`, and `images/` are treated as
  unrelated local academic artifacts based on the existing v3 audit and their
  content/location. They will be preserved on disk and ignored, not deleted.

