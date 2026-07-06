# Handoff: AI Map And Trade Log Upgrade

Date: 2026-07-06

## Implemented

- Added opt-in AI enrichment routing in the API with provider priority order:
  OpenRouter, Groq, Gemini, Cerebras.
- Added `/api/v1/vault/ai/providers` so the UI can show mode, configured
  providers, active provider, model, priority, and protocol.
- Kept local semantic extraction as the default. Vault source text is not sent
  to cloud providers unless `AI_ENRICHMENT_MODE=auto` and a provider key are set.
- Extended import metadata with `enrichment_method` and `ai_router` details.
- Blended imported strategy sources into the strategy scoreboard, insights, and
  graph. Sources can now create research-only strategy candidates or attach to
  existing strategies by overlapping strategy/setup/tag labels.
- Added persistent source learning: every saved source is chunked into
  `memory_chunks` and projected into `kg_nodes` / `kg_edges` for source,
  strategy, setup, indicator, market, timeframe, rule, and tag relationships.
- Added source-card memory summaries in the UI so users can see how many chunks,
  nodes, and edges the personal AI learned from each source.
- Upgraded the map with pan, zoom, recenter, focus selected, click-to-focus
  nodes, and connection-driven traversal.
- Added quick trade logging from one-line text, with live parse preview and
  source/history-backed strategy and setup suggestions.
- Updated README and environment docs.

## Verification

Run from repo root unless noted:

```bash
services/api/.venv/bin/pytest
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
```

All passed on 2026-07-06.

## AI Router Notes

- Default mode: `AI_ENRICHMENT_MODE=local`.
- Cloud mode: set `AI_ENRICHMENT_MODE=auto`, at least one provider key, and
  optionally reorder `AI_PROVIDER_ORDER`.
- Provider endpoint shapes were checked against official docs:
  - OpenRouter chat completions: `https://openrouter.ai/api/v1/chat/completions`
  - Groq OpenAI-compatible chat completions: `https://api.groq.com/openai/v1/chat/completions`
  - Google Gemini Interactions API: `https://generativelanguage.googleapis.com/v1beta/interactions`
  - Cerebras chat completions: `https://api.cerebras.ai/v1/chat/completions`

## Next Work

- Add persisted graph nodes/edges from imported sources instead of deriving the
  graph entirely in the browser. Source ingestion now writes KG facts; the next
  step is to hydrate the frontend map directly from `/api/v1/graph/*`.
- Add a trade ticket parser endpoint so quick trade parsing can become shared
  API behavior and eventually accept screenshots/broker exports.
- Add source-to-strategy review controls for accepting, merging, or rejecting
  generated strategy hypotheses.
- Add provider health checks and rate-limit/error telemetry once real keys are
  configured.
- Add a consent modal before switching AI enrichment into cloud mode from the UI.
