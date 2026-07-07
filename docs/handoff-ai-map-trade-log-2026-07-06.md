# Handoff: AI Map And Trade Log Upgrade

Date: 2026-07-06

Follow-up: 2026-07-07

## Implemented

- Added opt-in AI enrichment routing in the API with provider priority order:
  OpenRouter, Groq, Gemini, Cerebras.
- Added `/api/v1/vault/ai/providers` so the UI can show mode, configured
  providers, active provider, model, priority, and protocol.
- Kept local semantic extraction as the default. Vault source text is not sent
  to cloud providers unless `AI_ENRICHMENT_MODE=auto` and a provider key are set.
- Extended import metadata with `enrichment_method` and `ai_router` details.
- Added arXiv PDF link resolution: `/pdf/...` imports are converted through
  arXiv metadata into paper title, authors, abstract, subject, comments,
  implementation notes, and source details. Existing arXiv placeholders are
  backfilled and relearned when documents are listed.
- Added arXiv abs-page fallback for fresh papers that are not yet returned by
  the Atom feed. Verified `https://arxiv.org/pdf/2607.00475` imports as
  "End-to-End Parametric Portfolio Policies for Cross-Asset Futures Timing:
  When Do AI Models Beat Simple Rules?" with authors Austin Pollok and Kevin
  Robik, subject tags, futures/risk-parity technicals, and concise strategy
  evidence.
- Added cleanup for saved arXiv rows with placeholder/noisy metadata so the
  vault list endpoint refreshes them and relearns their graph facts.
- Blended imported strategy sources into the strategy scoreboard, insights, and
  graph. Sources can now create research-only strategy candidates or attach to
  existing strategies by overlapping strategy/setup/tag labels.
- Added persistent source learning: every saved source is chunked into
  `memory_chunks` and projected into `kg_nodes` / `kg_edges` for source,
  strategy, setup, indicator, market, timeframe, rule, and tag relationships.
- Added richer technical extraction for source imports, including indicators,
  price action, market structure, setups, risk concepts, sessions, markets, and
  timeframes. Cloud AI prompts now explicitly request technical tags/profile;
  local extraction fills the same fields when no provider is configured.
- Added `/api/v1/trades/recommendations`, which generates paper-trading
  recommendations from uploaded strategy sources, extracted technical tags,
  learned memory summaries, and matching closed-trade history.
- Added source-card memory summaries in the UI so users can see how many chunks,
  nodes, and edges the personal AI learned from each source.
- Added source-card technical sections and trade-tab recommendation cards.
- Kept strategy/source technical details short in the UI by compacting source
  abstracts, implementation notes, technical tags, and entry/exit/risk rule
  lists.
- Upgraded the map with pan, zoom, recenter, focus selected, click-to-focus
  nodes, and connection-driven traversal.
- Added quick trade logging from one-line text, with live parse preview and
  source/history-backed strategy and setup suggestions.
- Added recommendation draft fill: each recommendation can now provide symbol,
  side, strategy, setup, emotion, quantity, fees, notes, and quick-text context,
  and the UI can apply that draft directly into the trade form.
- Added delayed live quote support through `/api/v1/trades/quotes/{symbol}`.
  The current adapter uses Yahoo chart data without requiring a key and is
  isolated behind `services/market_data.py` so it can be swapped for a broker or
  dedicated market-data provider later.
- Added open/in-progress trade support. `exit_price` can be null, open rows are
  marked with live quotes in the UI, and rows can be closed at the latest quote
  through `PATCH /api/v1/trades/{trade_id}`.
- Added a live paper-trade ticket action. The trade form can now place a paper
  market order at the latest quote, persist provider/time/order metadata, show
  the open position in an active book, refresh live marks, and close the
  position at the current quote.
- Recommendation and strategy-evaluation drafts now fill entry and exit prices
  when a quote is available, so the user can immediately log or paper-log a
  trade.
- Added `/api/v1/trades/strategy/optimal` to synthesize the current best
  knowledge-base strategy from learned sources and trade history, including
  included/excluded rationale and a draft.
- Added `/api/v1/trades/strategy/evaluate` for plain-English strategy ideas.
  It assigns technical tags/profile, scores whether the idea is beneficial,
  observational, or edge-weakening, returns included/excluded reasons, produces
  a trade draft, and writes the evaluation into the journal by default.
- Renamed the graph UI from the copyright-sensitive map label to Strategy
  Atlas.
- Replaced the circular atlas layout with spaced source, strategy, setup,
  trade, journal, tag, state, and market groups.
- Cleaned up the atlas view with a wider canvas, curved low-opacity links,
  quieter memory edges, conditional labels, and selected-node neighborhood
  highlighting.
- Added a recommended routine card that derives how to trade, what setup to
  look for, when to execute, and risk/review steps from extracted strategy
  rules and the current knowledge base.
- Updated README and environment docs.

## Verification

Run from repo root unless noted:

```bash
services/api/.venv/bin/pytest
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
```

All passed on 2026-07-06.

Re-run on 2026-07-07 after arXiv fallback and recommendation draft-fill work:

```bash
cd services/api && .venv/bin/ruff check app tests
cd services/api && .venv/bin/pytest
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
```

All passed. Live checks against the running local API also confirmed:

- `POST /api/v1/vault/import-url` for `https://arxiv.org/pdf/2607.00475`
  returns real paper metadata, risk-parity/futures tags, and concise strategy
  fields.
- `GET /api/v1/vault/documents` refreshes the saved placeholder/noisy arXiv row
  and updates learned memory graph counts.
- `GET /api/v1/trades/recommendations` returns a Risk parity recommendation
  with an `ES long` draft sourced from the learned paper.

Re-run on 2026-07-07 after live quote, open trade, optimal-strategy, and
plain-English evaluator work:

```bash
cd services/api && .venv/bin/ruff check app tests
cd services/api && .venv/bin/pytest
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
```

All passed. Live checks against the running local API confirmed:

- `GET /api/v1/trades/strategy/optimal` returns included/excluded rationale and
  quote-backed entry/exit draft prices.
- `POST /api/v1/trades/strategy/evaluate` returns technical tags/profile,
  included/excluded rationale, quote-backed draft prices, and a journal entry id.
- The Next dev server responds at `http://localhost:3000/` after the UI changes.

Re-run on 2026-07-07 after live paper-trade ticket work:

```bash
cd services/api && .venv/bin/ruff check app tests
cd services/api && .venv/bin/pytest
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
```

All passed. Local server checks confirmed:

- `GET /health` returns `{"status":"ok","service":"api","environment":"local"}`.
- `GET /api/v1/trades/quotes/AAPL` returns a delayed `yahoo_chart` quote.
- The Next dev server responds at `http://localhost:3000/`.

Re-run on 2026-07-07 after Strategy Atlas and routine-playbook work:

```bash
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
```

Both passed. Local server check confirmed `http://localhost:3000/` returns 200
and serves the renamed `Atlas` tab.

Re-run on 2026-07-07 after atlas visual cleanup:

```bash
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
```

Both passed. Local server check confirmed `http://localhost:3000/` returns 200.

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
