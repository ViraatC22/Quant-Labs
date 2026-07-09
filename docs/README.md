# Quant Labs Documentation

This folder is the project knowledge base. Keep product plans, architecture, setup requirements, UI-system notes, and repository maps here so the important context travels with the codebase.

## Start Here

- [Project Overview](project-overview.md) — concise product summary, local development, and current app behavior.
- [Presentation Demo Guide](presentation-demo-guide.md) — project brief, video script, demo flow, talking points, and likely Q&A.
- [Repository Map](repository-map.md) — where the important source, config, and documentation files live.
- [Architecture](architecture.md) — product thesis, build order, stack, and safety boundaries.
- [Implementation Plan v2](implementation-plan-v2.md) — original long-form developer plan imported from Downloads.
- [TradingView Adapter Thesis](tradingview-adapter-thesis.md) — decision note explaining why TradingView is an adapter, not the core platform.

## Setup And Operations

- [Setup Requests](setup-requests.md) — founder/developer checklist for accounts, credentials, local software, and future integrations.
- [Provider Setup Requests](provider_setup_requests.md) — concise provider-specific setup tracker.
- [Environment Variables](environment.md) — documented `.env.example` values and security notes.
- [AI Map And Trade Log Handoff](handoff-ai-map-trade-log-2026-07-06.md) — current implementation notes for the dynamic map, source-backed insights, AI routing, and quick trade logging.

## UI System

- [UI Library Implementation](UI-LIBRARY-IMPLEMENTATION.md) — shadcn-style primitives, Tailwind tokens, animated components, and verification notes.

## Maintenance Rules

- Put durable project context in this folder.
- Keep root `README.md` short and GitHub-friendly.
- Do not commit real secrets, private account credentials, exported browser data, or personal trading records.
- When a new important doc is added, link it from this index.
