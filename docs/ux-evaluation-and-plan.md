# Quant Labs — UX & Product Evaluation and Implementation Plan

**Date:** 2026-07-08
**Method:** Hands-on walkthrough of the running app (every tab, real imports, seeded trades and journal entries, desktop + mobile). This is a usability and product audit, not a code review — findings are about what a user sees, understands, and can do.
**Audience:** Development team. Each finding is concrete and tied to something observed in the UI; each plan task has acceptance criteria.

---

## How I evaluated

I ran the app against a fresh database, then used it as a trader would: imported a source by URL, logged trades across strategies, added journal entries, and walked all six tabs (Vault, Journal, Trades, Routine, Insights, Atlas) at desktop and 375px mobile. Findings below reference exactly what appeared on screen.

---

## Part 1 — What genuinely works (protect these)

The **conceptual design is the app's biggest asset.** Several things are legitimately good and differentiated:

- **Insights framing.** "Net Edge," "Best Strategy" (e.g. *VWAP Pullback +$2,077 across 3 trades*), and especially **"Strategy Leak"** (*Opening Range Breakout −$63, −$31.50 avg*) are exactly the reflective, behavior-changing signals a discretionary trader needs. This is the product's soul.
- **The Routine Playbook skeleton** (Routine / How To Trade / Setup To Look For) is a smart structure, and its sober lines — *"Use paper orders first; promote sizing only after journal and closed-trade evidence improve"* — are excellent coaching.
- **Live paper positions** with real marks (the seeded NVDA position pulled a live quote and showed unrealized P&L) feels responsive and real.
- **The Strategy Idea Evaluator** — "score a plain-English idea against your memory" — is a genuinely novel, sticky interaction.
- **Quick-trade natural language entry** ("AAPL long 100 x10 strategy VWAP setup ORB") is a delightful power-user affordance.
- **The Atlas** is visually beautiful and communicates "your memory is a connected system" at a glance.
- **Offline resilience** and instant local feel (post-hardening) make the app trustworthy to keep open all day.

The problems below are almost all about **execution quality and clarity**, not the vision. The vision is right.

---

## Part 2 — The trust crisis: data quality (fix first, everything depends on it)

This is the single most important theme. The app's promise is "trustworthy trading memory," and right now the automatically generated content actively erodes trust. Concrete evidence from importing one ordinary URL (the Wikipedia "VWAP" page):

### T1. Extraction captures site boilerplate, not content
The stored body began: *"Jump to content Main menu Main menu move to sidebar hide Navigation Main page Contents Current events Random article About Wikipedia Contact us Contribute Help Learn to edit…"* — the site's navigation chrome, not the article. This is not a cosmetic bug: that same junk then **propagated into the "Strategy Info," the entry/exit evidence, and — worst of all — the Routine Playbook's "Setup To Look For,"** where the user's actionable setup criteria literally read as Wikipedia's menu. Any feature downstream of extraction inherits the garbage.

### T2. Tag spam, shown twice
One article produced ~30 tags, including nonsensical ones for a VWAP page: `journal`, `trade`, `earnings`, `new-york`, `paper`, `en.wikipedia.org`. They were then rendered a **second time** under a duplicate "Generated Tags" block. This inflates the Atlas (62 nodes from 5 trades + 1 article), pollutes recommendations, and makes the whole system look indiscriminate.

### T3. The source title is used as a strategy name
Trade Guidance and Recommendations displayed **"Favor Volume-weighted average price - Wikipedia"** as if the article title were a tradeable strategy. A user reading "favor [an article title]" concludes the intelligence layer doesn't understand trading.

### T4. Fabricated precision presented as authority
Nearly every generated card carries a **"89% / 95% confidence"** figure — for a Wikipedia article. These are keyword-count heuristics dressed as statistics. In a trading tool, a false confidence number is worse than no number: it invites misplaced trust.

### T5. Internal artifacts leak into the UI
Rules were prefixed with chunk indices like **"[ 2 ]"** and **"[ 8 ]"**; insight cards mention **"6 learned chunks / 59 map nodes."** "Chunks" and "map nodes" are implementation details no trader should see.

**Why this is #1:** every other feature (Insights, Routine, Atlas, Recommendations, Evaluator) reads *from* this layer. Clean it and four tabs get better at once. Leave it and polishing the rest is lipstick.

---

## Part 3 — Metrics correctness & consistency

Numbers must agree with themselves or the product is untrustworthy by a different route.

### M1. Two different win rates on one screen
On the Insights tab, the header tile read **"1 open / 75% win"** while the Net Edge card directly below read **"5 closed trades at 80% win rate."** The second counts the still-open NVDA position as a closed win (4 of 5 = 80%). Same screen, contradictory numbers.

### M2. Open positions blended into "closed" stats
"Best Strategy: VWAP Pullback $2,077.88 across 3 trades" and "How To Trade… 3 logged trades, 100% win rate" both fold an *open* position's unrealized mark into what reads as realized, closed-trade performance. Unrealized and realized must be visually and arithmetically distinct.

### M3. No definitions for the headline numbers
"Net Edge," "P&L (realized + open marks)," "Memory," "source signals" appear with no tooltip or drill-down. A user can't tell whether P&L includes fees, whether win rate counts scratches, or what "edge" means.

---

## Part 4 — First-run & onboarding (there is none)

Loading a fresh workspace shows **four zeros** (Vault 0, Trades 0, P&L $0, Memory 0) and two abstract panels ("Auto Capture," "Auto-filled fields" with placeholder values like *file/link metadata*). There is:

- **No welcome, no explanation of the workflow**, no "start here."
- **No sample data / demo mode** to explore the app's value before investing effort.
- **No empty-state guidance** — the Vault says "Vault is empty" but doesn't say *import an arXiv paper or a strategy PDF to see it learned into your memory.*
- **A misleading "Auto-filled fields" panel** that looks like a form but is a static legend, and **never updates after an import** — it still showed placeholders after a successful capture.

A first-time trader has no idea what to do or why. The activation moment (first import → see it become structured intelligence) is the product's magic and it's completely unguided.

---

## Part 5 — Navigation, information architecture, and layout

### N1. Double, misleading navigation
The top header shows badge-buttons **"Vault / Trades / Insights"** that look clickable but are decorative, directly above the *real* tab bar (Vault / Journal / Trades / Routine / Insights / Atlas). Two nav-looking rows, one of them fake and a subset of the other.

### N2. Brand vs product-name confusion
The header simultaneously says **"Quant Labs," "Local Memory,"** and **"Trading Intelligence OS."** Three names, no clear hierarchy of what the thing is called.

### N3. Global metric tiles dominate every tab
The four big stat tiles render at the top of **all six tabs** and, on mobile, each fills nearly a full screen height — so every tab starts with a mandatory scroll past the same four numbers before any tab-specific content. They belong on a dashboard/overview, not stapled to the journal form and the trade ticket.

### N4. Overlapping tab concepts
"Routine" is its own tab, yet "Routine complete" is a checkbox inside the Journal form. Insights and Atlas are both "look at your aggregate data." A new user can't predict what lives where.

### N5. Mobile tab overflow
At 375px the tab bar scrolls horizontally and Insights/Atlas are off-screen with no affordance signaling more tabs exist.

---

## Part 6 — Language & comprehensibility

The app speaks its own dialect. Undefined terms observed: **"Memory," "local records," "Memory Bot," "chunks," "map nodes," "Net Edge," "source signals," "map labels."** "Memory Bot: 6 chunks — 1 sources are available as graph memory and strategy evidence" is a sentence no trader will parse (and "1 sources" is a grammar bug).

There is no glossary, no tooltips, and no consistent vocabulary (the same thing is a "source," a "document," a "record," and "memory" in different places).

---

## Part 7 — Information density & specific components

### D1. Source cards are enormous and repetitive
A single imported article rendered a card **thousands of pixels tall**: summary, "Read more," ~30 tags, a duplicate "Generated Tags" block, Technicals, Strategy Info (repeating the same junk text a third time), Entry/Exit/Risk evidence each with their own "Read more," Confidence, Timeframe, Market. It's exhausting and buries the one or two useful facts.

### D2. The trade ticket has ~25 fields
The manual ticket exposes symbol, asset class, side, entry/exit, quantity, fees, contract multiplier, risk, stop, target, timeframe, session, exchange, leverage, underlying, expiration, strike, delta, IV, futures contract, tick size/value, strategy, setup, state, notes — all at once. For the common case (log an equity trade) this is overwhelming; advanced fields should be progressively disclosed by asset class.

### D3. No edit affordance in the UI
Source and journal cards offer only delete (a trash icon). There is no way to fix a bad title or correct a note from the UI, even though the API now supports editing. Users are forced into delete-and-recreate.

### D4. Destructive deletes have no confirmation
The trash icon deletes immediately with no undo and no confirm.

---

## Part 8 — Accessibility & polish

- **Status is color-only** in places (green/red P&L, moss/loss dots) — needs text/though most numbers do have signs.
- **Delete is an unlabeled icon button**; confirm screen-reader labels exist and tap targets are ≥44px on mobile.
- **The Atlas** is pointer-and-large-screen only; no keyboard navigation, and it's effectively unusable at 375px.
- **No loading skeletons** for imports/quotes beyond a text status line; a slow import looks frozen.

---

## Part 9 — Features to add (make it more useful)

Ordered by leverage. The top items turn the app from "a clever memory demo" into "a tool a trader opens every day."

### High leverage
1. **Guided onboarding + demo data.** A first-run checklist ("Import your first source → Log a trade → See your edge") and a one-click "Load sample workspace" so the value is visible in 10 seconds. *This is the single highest-ROI addition.*
2. **Equity curve & performance charts.** The app computes P&L but never plots it. A cumulative P&L/equity curve, a per-strategy bar chart, and an R-multiple distribution would make Insights genuinely analytical. (Charts also make the poster/demo far stronger.)
3. **Risk & expectancy panel.** Compute R per trade from stop distance (fields already exist), show expectancy, profit factor, max drawdown, and a position-size calculator (account size + risk% → shares/contracts). Trading value that's currently missing entirely.
4. **Global search / command palette (⌘K).** Search across vault, trades, and journal from anywhere; jump to any tab. Makes a growing memory navigable.
5. **Trade ↔ journal ↔ source linking.** Let a journal entry reference a trade, and a trade cite the source/strategy it came from, so the "memory graph" is something the user builds deliberately, not just an auto-generated cloud.

### Medium leverage
6. **Broker CSV import with a preview/mapping step.** The file upload exists; add real parsing for TradingView/IBKR/Webull exports with a column-mapping and dedupe preview. Turns manual journaling into bulk import.
7. **Calendar / heatmap view** of trades and journaling streaks (P&L by day, routine-adherence streak). Traders love a calendar; it also reinforces the journaling habit.
8. **Filter & sort trade history** by symbol, strategy, setup, date, outcome, and asset class.
9. **Manual note/strategy creation in the Vault** (not just import) — a blank "New note" so a user can write a strategy directly.
10. **Pre-trade checklist gate** on the ticket, generated from the strategy's routine, with adherence logged and compared (checklist-on vs off performance).

### Delight / differentiation
11. **Lesson resurfacing** — journal entries tagged as mistakes/lessons resurface on a spaced schedule ("2 weeks ago you paid $312 to relearn: don't chase the ORB").
12. **Attach chart screenshots** to trades (thumbnails in history and the Atlas).
13. **Weekly review export** (PDF/HTML) — a shareable summary of P&L, R stats, best/worst, and lessons.

---

## Part 10 — Implementation plan

Phases are ordered by dependency and impact. Each task has acceptance criteria (AC).

### Phase A — Fix the data-quality foundation (everything reads from it)

**A1. Real content extraction (T1).** Replace naive "collect all text" with main-content extraction (strip nav/header/footer/aside/script; prefer `<article>`/`<main>`/readability heuristics). For arXiv, keep the structured path.
 AC: importing the Wikipedia VWAP page stores prose about VWAP, not the nav menu; no "Jump to content Main menu…" anywhere in the body, strategy info, or routine.

**A2. Tag hygiene (T2).** Cap tags (e.g. ≤ 12), drop domain/site tags (`en.wikipedia.org`, `article`) and generic-noise tags, dedupe, and show **one** tag list (remove the duplicate "Generated Tags" block).
 AC: the same import yields a short, on-topic tag set shown once; no `journal`/`trade`/`new-york` on a VWAP article.

**A3. Stop using titles as strategy names (T3).** A source is not a strategy. Only surface a strategy name when a real setup/rules were extracted; otherwise present the source as *research*, and label recommendations by setup, not article title.
 AC: no card ever says "Favor [article title]"; a plain article appears under Research, not as trade guidance.

**A4. Honest confidence (T4).** Remove the fabricated percentage, or replace it with a plain qualitative label ("rule-based extraction") and, where real trades exist, show the actual sample (n, win rate, avg R) instead of a synthetic scalar.
 AC: no "% confidence" appears unless it is derived from real closed-trade outcomes, and it's labeled as such.

**A5. Hide internal artifacts (T5).** Strip chunk-index prefixes ("[ 2 ]") from displayed rules; remove "chunks / map nodes" from user-facing copy (keep in logs/debug).
 AC: no bracketed indices or "chunk/node" language in any card.

### Phase B — Metrics you can trust

**B1. One definition of win rate and P&L (M1, M2).** Compute closed-trade stats from closed trades only; show open positions' unrealized P&L in a separate, clearly labeled place. Reconcile the header tile with the Insights cards.
 AC: every win-rate and closed-P&L figure on a screen agrees; unrealized is always labeled "unrealized/open."

**B2. Definitions everywhere (M3).** Tooltip/popover on Net Edge, P&L, win rate, expectancy explaining exactly what's counted (fees in/out, scratches, open vs closed).
 AC: hovering any headline metric explains its formula in one sentence.

### Phase C — Onboarding & first-run

**C1. Empty states with a next action (Part 4).** Every empty tab gets a one-line "what this is + do this next" and a primary button.
 AC: a fresh user on any tab sees a concrete next step, not just a zero.

**C2. Demo workspace (Part 4).** "Load sample data" seeds a realistic vault + trades + journal so the value is instantly visible; "Reset" clears it.
 AC: one click populates every tab with coherent sample data; one click restores empty.

**C3. First-run checklist (Part 4, feature 1).** A dismissible 3-step activation checklist (import a source → log a trade → open Insights).
 AC: progress persists; disappears once completed or dismissed.

**C4. Fix the "Auto-filled fields" panel.** Make it reflect the *actual* extracted values after an import, or remove it.
 AC: after an import, the panel shows the real title/type/tags/strategy, or it's gone.

### Phase D — Navigation, IA, layout

**D1. One navigation (N1, N2).** Remove the decorative header badges; settle on one product name with a clear brand lockup.
 AC: exactly one set of tabs; the header states one name.

**D2. Move global metrics to an Overview (N3).** Introduce an Overview/Dashboard as the landing tab (metrics + equity curve + top insight + open positions); remove the metric strip from the other tabs (or collapse it to a slim summary bar).
 AC: Journal, Trades, Routine no longer open with four full-height stat tiles; metrics live on Overview.

**D3. Resolve overlapping tabs (N4).** Fold "Routine complete" into a coherent daily-routine flow; clarify Insights (aggregate analytics) vs Atlas (graph exploration) with one-line subtitles.
 AC: no concept appears in two unrelated places; each tab has a one-line purpose statement.

**D4. Mobile tab affordance (N5).** Show that more tabs exist (scroll hint/overflow menu) and keep the active tab in view.
 AC: at 375px a user can reach Insights/Atlas without guessing they exist.

### Phase E — Component-level clarity

**E1. Condense the source card (D1).** Collapse to a compact summary (title, type, 1-line summary, ≤ 8 tags, key setup) with an expandable detail drawer; never repeat the same text more than once.
 AC: a source card is ≤ ~1.5 screens collapsed; no repeated blocks.

**E2. Progressive trade ticket (D2).** Default to the equity essentials; reveal option/futures/forex fields only when that asset class is selected; keep advanced fields behind a disclosure.
 AC: logging an equity trade shows ≤ 8 fields; option/futures fields appear only for those classes.

**E3. Edit affordances (D3).** Add edit to source and journal cards (wired to the existing PATCH endpoints), preserving IDs.
 AC: a user can fix a title/note in place without deleting.

**E4. Confirm destructive actions (D4).** Delete asks for confirmation (or offers undo).
 AC: an accidental click can't silently destroy a record.

### Phase F — High-value features (post-foundation)

F1. Equity curve + per-strategy + R-distribution charts (feature 2).
F2. Risk/expectancy panel + position-size calculator (feature 3).
F3. ⌘K global search (feature 4).
F4. Trade ↔ journal ↔ source linking (feature 5).
F5. Broker CSV import with mapping/preview (feature 6).
F6. Calendar/heatmap, filters, manual notes, checklist gate, lesson resurfacing (features 7–11).

Each: ships with the metric/definition rules from Phase B and the language rules from Phase C, and does not reintroduce jargon.

---

## Part 11 — Sequencing

| Phase | Theme | Why this order |
|---|---|---|
| A | Data quality | Everything downstream (Insights, Routine, Atlas, Recs) reads from it; biggest trust win |
| B | Metric consistency | Cheap, and the app can't be trusted with contradictory numbers |
| C | Onboarding | Turns a confusing first run into an activation moment |
| D | Navigation/IA/layout | Removes structural confusion; makes room for new features |
| E | Component clarity | Makes the daily surfaces (cards, ticket) pleasant |
| F | New features | Built on a clean, trustworthy, navigable base |

**Two standing rules going forward:**
1. **Nothing user-facing may show internal vocabulary** (chunks, nodes, map labels) or a confidence number not derived from real outcomes.
2. **Every number must be reconcilable** — if two places show a win rate, they compute it the same way, and each is one hover from its definition.

The through-line: the vision and the "aha" features are already here. The work is making the generated content trustworthy, the numbers consistent, the first run guided, and the surfaces calm — then the analytical features (charts, risk, search) that a clean foundation finally makes worth building.
