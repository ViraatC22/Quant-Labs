# Quant Labs Poster Section Content

This file contains copy-ready Markdown content for each poster section. It is
written for the three-column poster layout with a large central finding panel.
Photos and screenshots are intentionally left as placeholders for a later pass.

## Title Block

**Title:** Quant Labs

**Subtitle:** A Local-First AI Trading Intelligence OS

**Author:** Viraat Chauhan

**Short label:** Trading memory graph, vault capture, strategy insights, and
paper-only research tools.

## Main Finding

Quant Labs turns every trade, routine, article, journal entry, screenshot, and
strategy note into a living memory graph that helps traders understand why
their decisions work or fail.

The core finding is that the most valuable trading system is not just another
charting tool. It is a personal evidence engine that connects behavior,
strategy rules, outcomes, routines, emotions, and research sources into one
explainable workspace.

## Introduction

Traders generate useful evidence every day: trades, routines, screenshots,
strategy notes, PDFs, articles, CSV imports, Pine scripts, Python notebooks,
emotional state, and mistakes. The problem is fragmentation. Lessons live across
broker statements, notebooks, charting tools, browser tabs, screenshots, and
spreadsheet exports, so repeated patterns are hard to see.

Quant Labs addresses this by treating the trader's memory graph as the core
product. TradingView, broker APIs, market-data providers, and future AI tools
become adapters around that memory system. The app is designed to help the user
capture evidence, structure it automatically, and surface patterns that improve
research and paper-trading decisions.

## Methods

1. Capture trading evidence.
   - Import links, Markdown notes, PDFs, screenshots, images, CSVs, Pine files,
     and Python files into the vault.
   - Auto-fill vault fields such as title, source, content type, extracted body,
     generated tags, strategy name, setup, risk notes, entry logic, and exit
     logic.

2. Structure trading behavior.
   - Log closed trades with symbol, side, entry, exit, fees, setup, strategy,
     market state, notes, and realized P&L.
   - Log journal entries with routine completion, emotional state, tags, and
     context about the trading day.

3. Generate strategy intelligence.
   - Use vault sources and trade data to create AI-generated tags, strategy
     fields, setup labels, and risk notes.
   - Connect trades to strategies, symbols, setups, emotions, routines, sources,
     and generated tags.

4. Map the trading memory graph.
   - Display an Obsidian-style relationship map linking trades, journal entries,
     strategies, symbols, setups, vault documents, emotions, and tags.
   - Use the map to make repeated mistakes, strong setups, weak routines, and
     strategy evidence easier to inspect.

## Architecture Pipeline

```text
Vault capture
  links, uploads, notes, PDFs, screenshots, CSVs, Pine, Python

Generated enrichment
  title, source, type, body, tags, setup, strategy, entry, exit, risk

Local-first persistence
  browser fallback plus API-backed storage

Strategy memory graph
  trades, routines, emotions, symbols, sources, tags, and relationships

Trading insights and Obsidian map
  explain what works, what leaks, and what repeats
```

## Current Results

The current MVP is already usable as a local trading memory workspace. It
combines a Next.js web app, FastAPI service, local-first persistence, generated
vault enrichment, strategy and trade analytics, and a relationship map.

Implemented surfaces:

| Surface | Current status | Evidence to show on poster |
| --- | --- | --- |
| Vault capture | Link and file upload flows are implemented. | Screenshot placeholder |
| Auto-filled vault fields | Title, type, source, body, generated tags, and strategy information are generated. | Screenshot placeholder |
| Trade logging | Closed trades can be entered and analyzed by strategy, setup, state, and P&L. | Screenshot placeholder |
| Journal logging | Routines, emotional state, notes, and tags can be captured. | Screenshot placeholder |
| Strategy insights | The app surfaces P&L, win-rate, state, routine, and setup patterns. | Screenshot placeholder |
| Obsidian-style map | Relationships between trades, strategies, symbols, sources, emotions, and tags are visualized. | Screenshot placeholder |
| UI system | shadcn-style primitives, dark mode, and a polished dashboard shell are in place. | Screenshot placeholder |

## Discussion

The main product insight is architectural: the app should not be centered on
controlling TradingView. TradingView is useful for charts, Pine scripts, alerts,
and visual market context, but the durable product is the user's personal
trading memory.

Quant Labs becomes valuable before live broker integration exists because it
helps traders capture research, label strategies, review losses, map
relationships, and ask better questions about repeated mistakes and setup
quality. The app is intentionally paper-first and evidence-backed: AI-generated
claims should eventually cite source chunks, user trades, backtests, or paper
experiments.

This approach turns trading review from a scattered manual habit into a
structured feedback system. Instead of asking only "What was my win rate?", the
user can ask questions such as:

- Why do my breakout trades fail after 11:00 AM?
- Which strategy articles contradict my current rules?
- What rule did I keep violating during my last losing trades?
- Which emotional states or routines correlate with worse execution?
- What should I paper-test before adding a strategy to my playbook?

## Ammo Bar

Use this section for extra details that support the poster but do not need to
dominate the central panel.

Extra implementation details:

- Local-first behavior: the UI remains usable with browser storage when the API
  is unavailable.
- API-backed persistence: trades, journal entries, and vault documents can be
  stored through the FastAPI service when it is online.
- Safety boundary: the MVP is for research, journaling, review, and paper-only
  experimentation, not live autonomous trading.
- Design system: shadcn-style UI primitives, Tailwind tokens, dark mode, and a
  restrained animated shell support a serious trading workflow.
- Data model direction: future work should connect source documents, chunks,
  tags, graph nodes, trades, strategies, routines, and paper experiments with
  provenance.

Extra graph relationship examples:

```text
Trade -> USED_STRATEGY -> Strategy
Trade -> VIOLATED_RULE -> Rule
Trade -> OCCURRED_DURING -> Emotional State
Strategy -> SUPPORTED_BY_SOURCE -> Vault Source
Source -> GENERATED_TAG -> Tag
Strategy -> TESTED_BY -> Paper Experiment
```

## Future Implementation

The current MVP proves the workspace direction, but the full Trading
Intelligence OS still needs deeper AI memory, testing, integrations, and safety
systems.

1. Embeddings and graph memory.
   - Add source chunking for vault documents.
   - Generate embeddings for notes, articles, PDFs, trades, and journal entries.
   - Store graph nodes and edges with provenance.
   - Improve the Obsidian-style map with filtering, search, graph expansion, and
     stronger relationship explanations.

2. GraphRAG chat.
   - Build evidence-backed chat over vault sources, trades, routines, journal
     entries, strategies, and graph context.
   - Require answers to cite source chunks, trades, backtests, or paper
     experiments.
   - Let the user ask questions such as "why did this setup fail?" or "which
     rules should I paper-test next?"

3. Strategy creator and compiler.
   - Ingest articles, PDFs, screenshots, Pine scripts, YouTube transcripts,
     notes, and strategy documents.
   - Extract setup rules, entry rules, exit rules, invalidation rules, risk
     models, market-regime assumptions, indicators, warnings, and examples.
   - Compare imported strategy rules with the user's actual trading history.
   - Generate personalized strategy variants that must be tested before use.

4. Backtest and paper lab.
   - Build an internal backtesting and paper-simulation module.
   - Track strategy variants, test windows, metrics, drawdowns, overfitting
     checks, and paper-trade outcomes.
   - Promote strategies only after sufficient evidence from backtests and paper
     experiments.

5. Provider mesh and integrations.
   - Add market-data provider routing with fallback behavior and setup
     documentation.
   - Add TradingView webhook ingestion for alerts and Pine strategy events.
   - Add optional Alpaca paper-trading integration after the internal simulator
     is stable.
   - Keep integrations as adapters around the memory graph, not the center of
     the product.

6. Safety, evaluation, and auditability.
   - Keep the MVP paper-only and avoid live autonomous trading.
   - Add approval gates, risk limits, kill switches, and audit logs for any
     future paper-agent behavior.
   - Evaluate AI extraction quality, hallucination risk, and recommendation
     quality.
   - Ensure every AI-created rule, tag, insight, or strategy claim can be traced
     back to evidence.

7. Product polish and reporting.
   - Add richer dashboards for strategy performance, mistakes, routines,
     emotional state, and market conditions.
   - Generate monthly review reports from trades, journals, vault notes, and
     paper experiments.
   - Add exportable strategy cards and study summaries.
   - Add poster-ready screenshots and photos in a later visual pass.

## Photo And Screenshot Placeholders

Photos and screenshots will be added later. Suggested slots:

- Vault capture screen showing link or file upload.
- Auto-generated tags and strategy information.
- Trading insights dashboard.
- Obsidian-style relationship map.
- Strategy detail or trade review panel.
- Optional founder/project photo or QR code area.

## References

- `docs/project-overview.md`
- `docs/architecture.md`
- `docs/implementation-plan-v2.md`
- `docs/tradingview-adapter-thesis.md`
- `docs/UI-LIBRARY-IMPLEMENTATION.md`
