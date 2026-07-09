# Quant Labs Presentation And Demo Guide

Use this guide for a 5-7 minute project video or live demo. The safest demo flow is:
open the app, show the memory system, import or inspect a source, move through the
Strategy Atlas, generate a routine, then place or review a paper trade.

## Project Brief

Quant Labs is a local-first AI trading intelligence OS. It brings together the
parts of trading that usually live in separate places: research papers, strategy
notes, journal entries, trade logs, emotions, routines, technical tags, paper
trades, and a visual memory graph.

The main idea is that a trader should not have to remember every rule, mistake,
paper, setup, and trade manually. Quant Labs turns those inputs into a personal
knowledge base that can help answer: what strategy am I testing, what setup am I
waiting for, what evidence supports it, what risks should I avoid, and how did
similar trades perform before?

The app is intentionally paper-first. It is for research, journaling, simulated
execution, strategy review, and decision support. It does not autonomously trade
real money.

## One-Sentence Pitch

Quant Labs is an AI-assisted trading memory system that converts research,
journals, and paper trades into a living strategy map and safer paper-trading
workflow.

## 30-Second Overview

"Quant Labs is a local-first trading intelligence platform. Instead of treating
trading as just charts and entries, it treats the trader's memory as the core
asset. I can upload strategy sources or papers, extract technical rules, connect
them to a knowledge graph, generate routines and paper-trade recommendations,
then log and review trades with live quote marking and account-size guardrails.
The goal is not to replace judgment. The goal is to make strategy research,
execution discipline, and review more structured."

## What To Show First

Start at `http://localhost:3000`.

Before recording, make sure:

- The app is running on port `3000`.
- The API is running on port `8000` if you want source enrichment, quote lookup,
  recommendations, and persistence.
- The workspace has at least one uploaded strategy source or paper.
- The workspace has a few sample trades or paper trades.
- The Strategy Atlas has enough nodes to look alive.
- The trade ticket has account equity set to a realistic number.
- Avoid showing private API keys, personal brokerage accounts, or real financial
  records.

## Recommended Demo Script

### 0:00-0:30 - Hook And Problem

Say:

"This project is called Quant Labs. The problem I wanted to solve is that
traders collect useful information every day, but it gets scattered across
papers, screenshots, strategy notes, journal entries, and trade logs. When it is
time to make a decision, the trader has to manually remember what worked, what
failed, and what rules they are supposed to follow."

Show:

- Dashboard or main app shell.
- Briefly point at Vault, Trades, Routine, Insights, and Atlas tabs.

Say:

"Quant Labs brings those pieces into one local-first trading intelligence system."

### 0:30-1:40 - Learning Vault And Source Processing

Show:

- Go to the Vault tab.
- Point to an existing uploaded paper/source, or import a link if the API is
  running.
- Open/read the source card details.

Say:

"The Learning Vault is where I add strategy sources. These can be links, notes,
PDFs, or trading documents. When a source is added, the system extracts metadata
like the title, author details when available, summary information, and trading
technicals."

Point out:

- Title and source details.
- Technical tags.
- Strategy information.
- Memory chunks, nodes, and edges.
- Read-more sections for long details.

Say:

"The important part is that the source is not just stored as a file. It becomes
structured memory. The app learns strategy concepts, setups, markets,
indicators, timeframes, and risk rules from the source."

### 1:40-2:40 - Strategy Atlas

Show:

- Go to the Atlas tab.
- Move around the galaxy-style map.
- Select a node and show that motion pauses.
- Show the inspector/details for a source, strategy, setup, trade, or tag.

Say:

"This is the Strategy Atlas. It visualizes the trading memory as a galaxy. The
center is Trading Memory, and the surrounding nodes are sources, strategies,
setups, trades, symbols, journal states, and technical tags."

Say:

"The map is dynamic, so the nodes float like a living knowledge system. When I
select a node, the movement pauses so I can inspect the relationships without
the graph shifting around."

Point out:

- Nodes are not random decoration; they represent learned trading facts.
- Edges show relationships between trades, strategies, setups, tags, and
  sources.
- The map helps explain why a recommendation or routine exists.

### 2:40-3:30 - Routine And Execution Plan

Show:

- Go to the Routine tab.
- Show the recommended routine card.
- Point to how to trade, setup criteria, execution timing, risk rules, and review
  steps.

Say:

"The Routine tab turns the learned strategy information into a practical trading
plan. Instead of only saying 'this strategy looks good,' it tells me what setup
to look for, when to execute, what risk rules to follow, and how to review the
trade afterward."

Say:

"This is useful because a lot of trading mistakes happen between knowing a
strategy and actually executing it consistently."

### 3:30-4:50 - Paper Trade Ticket And Account Guard

Show:

- Go to Trades.
- Point at Account Guard.
- Show account equity, reserved capital, and buying power.
- Show quick trade input and the structured ticket.
- Show advanced parameters for options/futures/crypto/forex.

Say:

"The trade ticket supports both quick entry and structured paper trades. It can
handle stocks, options, futures, crypto, and forex, with advanced parameters like
contract multiplier, stop, target, option strike, expiration, and futures tick
details."

Say:

"A newer safety feature is the Account Guard. If the account only has a certain
amount of buying power, the app blocks paper trades that would not realistically
fit. For example, a covered call reserves 100 underlying shares per options
contract, so the system will not let me paper trade a covered call if the
account cannot support the required collateral."

If live quote works:

- Click `Use live quote` or `Place live paper trade`.
- Show an open paper position with live mark and close action.

If live quote does not work:

Say:

"If live quotes are unavailable, the app still supports manual paper entries and
keeps them in the local workspace. The quote adapter is isolated so it can be
swapped for a more dedicated provider later."

### 4:50-5:50 - AI Recommendations And Strategy Evaluation

Show:

- AI Trade Recommendations card.
- Strategy Idea Evaluator.
- Apply a recommendation or evaluation draft to the trade ticket if available.
- Show included/excluded rationale if present.

Say:

"The AI features use the current knowledge base rather than only a generic
prompt. Recommendations are based on uploaded strategies, extracted technical
tags, learned source memory, and trade history."

Say:

"There is also a plain-English strategy evaluator. I can describe a trading idea
I heard about, and the system assigns technical tags, compares it with the
existing knowledge base, and tells me whether it looks beneficial,
observational, needs more structure, or could weaken the current edge."

Important note:

"Cloud AI is opt-in. By default, the system uses local semantic rules. If keys
are configured, routing can use providers like OpenRouter, Groq, Gemini, or
Cerebras."

### 5:50-6:40 - Insights And Review

Show:

- Insights tab.
- Pattern Snapshot.
- Strategy scoreboard or performance cards.
- Trade history dropdown rows.

Say:

"After trades are logged, Quant Labs becomes a review system. It can show
strategy performance, setup quality, routine effects, emotional state patterns,
and source-backed validation gaps."

Say:

"The point is not just to log trades. The point is to create a feedback loop:
research informs strategy, strategy informs routine, routine informs execution,
and execution results update the memory system."

### 6:40-7:00 - Closing

Say:

"Quant Labs is still an MVP, but the core idea is working: it turns trading
research, journaling, and paper trading into a connected memory system. The next
steps are deeper semantic search, stronger evidence citations, better
backtesting, and optional broker-paper integration. The long-term goal is a
personal trading assistant that helps the user stay disciplined, evidence-based,
and aware of risk."

## Shorter 3-Minute Script

"Quant Labs is a local-first AI trading intelligence OS. The idea is that a
trader's real edge is not just a chart setup; it is the memory of research,
rules, trades, routines, emotions, and mistakes.

Here in the Learning Vault, I can add a strategy paper or source. The app
extracts useful metadata, technical tags, strategy information, and memory graph
relationships. That source becomes part of the trading knowledge base instead of
just sitting as a file.

The Strategy Atlas shows that memory visually. It is built like a galaxy:
Trading Memory is the center, and sources, strategies, setups, trades, symbols,
states, and tags orbit around it. Selecting a node pauses the motion so I can
inspect the exact relationships.

The Routine tab turns learned strategy rules into an actionable trading plan:
what setup to wait for, when to execute, what risk rules matter, and how to
review the trade.

The Trades tab is where the system becomes a paper-trading workflow. I can use a
quick trade line or the structured ticket with options, futures, crypto, forex,
and stock parameters. The Account Guard restricts trades based on account size,
so unrealistic positions like underfunded covered calls are blocked.

The AI recommendation and strategy evaluator features use the knowledge base to
suggest paper trades or evaluate a plain-English strategy idea. Finally, the
Insights tab closes the loop by showing performance patterns, strategy leaks,
routine effects, and review signals.

The project is paper-only and evidence-focused. It is not a real-money trading
bot. The goal is to help a trader become more structured, disciplined, and aware
of the reasoning behind each trade."

## Things To Know Before Presenting

### Product Thesis

- The core product is the trader's memory graph.
- TradingView, broker APIs, market data, and AI providers are adapters around
  that memory system.
- The system is designed to improve research, journaling, review, and paper
  execution discipline.

### Current Strengths

- Local-first workspace with offline queue and API sync.
- Source import with technical extraction and strategy metadata.
- arXiv paper handling with title, author, abstract, and implementation details.
- Knowledge graph / Strategy Atlas for visual exploration.
- Routine generation from extracted strategy rules.
- Paper trade ticket with quick entry, live quotes, contract multipliers, and
  advanced instrument parameters.
- Account Guard for account-size and collateral restrictions.
- AI recommendations and plain-English strategy evaluation.
- Insights that connect trades, strategies, routines, states, and sources.

### Technical Stack

- Frontend: Next.js, React, TypeScript, Tailwind, shadcn-style UI primitives.
- Backend: FastAPI, SQLAlchemy, Alembic.
- Storage: local browser workspace, API persistence, SQLite standalone, Postgres
  in Docker.
- Optional infrastructure: Redis, MinIO, worker service.
- AI routing: local semantic rules by default, optional provider routing through
  OpenRouter, Groq, Gemini, and Cerebras.
- Market data: quote adapter currently supports delayed quote lookup and can be
  swapped later.

### Safety Boundaries

- This is not investment advice.
- This is not autonomous live trading.
- The app is for paper trading, journaling, research, and strategy review.
- AI outputs should be treated as decision support, not truth.
- Real broker integration should require explicit user consent, risk checks, and
  paper-mode validation first.

### Limitations To Be Honest About

- The knowledge graph is keyword/relationship-based today; deeper embedding
  search and GraphRAG chat are roadmap items.
- Quote data can be delayed or unavailable depending on provider access.
- AI enrichment depends on configured provider keys if cloud mode is enabled.
- Strategy recommendations still need more backtesting and stronger evidence
  citations before being treated as high confidence.
- This is an MVP, so the best use case is structured paper experimentation, not
  production trading.

## Likely Questions And Answers

**Q: Is this connected to a real brokerage?**  
A: Not yet. The current system is intentionally paper-first. Future broker
integration should start with broker paper accounts and require strict safety
checks before anything real-money-related.

**Q: Does the AI make trades for the user?**  
A: No. It recommends and evaluates ideas using the knowledge base, but the user
stays in control.

**Q: Why local-first?**  
A: Trading notes and journals can be private. Local-first lets the user keep
working offline and avoids sending private source text to cloud AI unless they
explicitly configure provider routing.

**Q: What makes this different from a normal trade journal?**  
A: A normal journal stores trades. Quant Labs connects trades to sources,
strategies, technical tags, routines, emotions, and a graph, then uses those
relationships for recommendations and review.

**Q: What makes this different from just asking ChatGPT about a strategy?**  
A: The app has a persistent personal memory: uploaded sources, past trades,
journal states, routines, and extracted technical rules. The AI workflow is
grounded in that user-specific context.

**Q: Can it prove a strategy works?**  
A: Not by itself yet. It can organize evidence, generate paper-trade ideas, and
highlight patterns. Backtesting and stronger statistical validation are future
work.

**Q: Why does the Account Guard matter?**  
A: It prevents unrealistic paper trading. For example, covered calls require
underlying collateral, so the app blocks trades the account cannot afford.

## Demo Backup Plan

If a live import fails:

- Use an existing source already in the vault.
- Say: "The importer depends on the API and source availability, so I prepared a
  saved source to show the same processed result."

If live quotes fail:

- Use manual entry prices.
- Say: "The quote adapter is intentionally isolated. If the provider is
  unavailable, paper logging still works and the adapter can be swapped later."

If AI provider status is offline:

- Say: "The default mode is local semantic extraction. Cloud AI is opt-in and
  only runs when provider keys are configured."

If the graph is crowded:

- Select one node and explain its direct relationships.
- Say: "The graph is meant for exploration; selecting a node pauses motion and
  narrows attention to the relevant relationship set."

## Phrases To Avoid

- Do not say the app guarantees profitable trades.
- Do not say it is a fully autonomous trading bot.
- Do not say the AI always knows the best strategy.
- Do not present paper-trading results as real-money performance.
- Do not claim live broker execution is implemented if you are showing internal
  paper trading.

## Strong Closing Line

"Quant Labs is trying to make trading less memory-dependent and more
evidence-dependent. It does not remove risk, but it gives the trader a structured
way to connect research, execution, review, and discipline."
