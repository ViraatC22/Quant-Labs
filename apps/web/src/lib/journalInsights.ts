// Journal presentation math: heatmap buckets, weekday P&L, a six-axis quality
// radar, and deterministic focus actions.
//
// Scope note on the radar: the reference product scores axes like "Entry
// Timing" that trade records cannot actually measure. Every axis here is
// computed from fields that exist in the journal, and each carries its reason,
// so the radar describes the record rather than pretending to referee skill.

import { isClosed, realizedPnl, tradeR } from "@/lib/analytics";
import type { TradeEntry } from "@/lib/types";

export type DayBucket = { date: string; pnl: number; count: number };

/** Realized P&L per calendar day (UTC dates), for the heatmap. */
export function dailyPnl(trades: TradeEntry[]): DayBucket[] {
  const buckets = new Map<string, { pnl: number; count: number }>();
  for (const trade of trades.filter(isClosed)) {
    const day = trade.entryDate.slice(0, 10);
    const current = buckets.get(day) ?? { pnl: 0, count: 0 };
    current.pnl += realizedPnl(trade);
    current.count += 1;
    buckets.set(day, current);
  }
  return [...buckets.entries()]
    .map(([date, value]) => ({ date, pnl: value.pnl, count: value.count }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

export type WeekdayPnl = { weekday: string; pnl: number; count: number };

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function weekdayPnl(trades: TradeEntry[]): WeekdayPnl[] {
  const totals = WEEKDAYS.map((weekday) => ({ weekday, pnl: 0, count: 0 }));
  for (const trade of trades.filter(isClosed)) {
    const day = new Date(`${trade.entryDate.slice(0, 10)}T00:00:00Z`).getUTCDay();
    const index = (day + 6) % 7; // JS Sunday=0 → Monday-first
    totals[index].pnl += realizedPnl(trade);
    totals[index].count += 1;
  }
  return totals;
}

export type QualityAxis = { label: string; score: number; reason: string };

const CALM_STATES = new Set(["patient", "focused", "calm", "disciplined"]);

function clampScore(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

/**
 * Six axes, each measurable from stored fields. Requires 3 closed trades;
 * below that it returns [] and the caller shows "insufficient evidence".
 */
export function tradeQualityAxes(trades: TradeEntry[]): QualityAxis[] {
  const closed = trades.filter(isClosed);
  if (closed.length < 3) return [];

  const pnls = closed.map(realizedPnl);
  const wins = pnls.filter((value) => value > 0);
  const losses = pnls.filter((value) => value < 0);
  const avgWin = wins.length ? wins.reduce((s, v) => s + v, 0) / wins.length : 0;
  const avgLoss = losses.length
    ? Math.abs(losses.reduce((s, v) => s + v, 0) / losses.length)
    : 0;
  const payoff = avgLoss > 0 ? avgWin / avgLoss : avgWin > 0 ? 2 : 0;

  const riskDefined =
    closed.filter((trade) => Boolean(trade.riskAmount) || Boolean(trade.stopPrice))
      .length / closed.length;
  const rMeasured =
    closed.map(tradeR).filter((value) => value !== null).length / closed.length;
  const stateLogged =
    closed.filter((trade) => CALM_STATES.has(trade.emotion.trim().toLowerCase()))
      .length / closed.length;
  const journaled =
    closed.filter((trade) => trade.notes.trim().length > 0).length / closed.length;

  return [
    {
      label: "Outcome",
      score: clampScore((wins.length / closed.length) * 100),
      reason: `${Math.round((wins.length / closed.length) * 100)}% win rate over ${closed.length} trades`
    },
    {
      label: "Payoff",
      score: clampScore(Math.min(payoff, 2) * 50),
      reason: `${payoff.toFixed(2)} average win/loss ratio`
    },
    {
      label: "Risk definition",
      score: clampScore(riskDefined * 100),
      reason: `${Math.round(riskDefined * 100)}% of trades carry a stop or planned risk`
    },
    {
      label: "R discipline",
      score: clampScore(rMeasured * 100),
      reason: `${Math.round(rMeasured * 100)}% of trades have a measurable R multiple`
    },
    {
      label: "Decision state",
      score: clampScore(stateLogged * 100),
      reason: `${Math.round(stateLogged * 100)}% logged calm/patient/focused`
    },
    {
      label: "Journaling",
      score: clampScore(journaled * 100),
      reason: `${Math.round(journaled * 100)}% of trades carry notes`
    }
  ];
}

export type FocusAction = {
  title: string;
  detail: string;
  tone: "positive" | "caution";
};

type Group = { label: string; pnl: number; count: number };

function groupBy(
  trades: TradeEntry[],
  key: (trade: TradeEntry) => string
): Group[] {
  const groups = new Map<string, TradeEntry[]>();
  for (const trade of trades.filter(isClosed)) {
    const label = key(trade).trim() || "Unlabeled";
    groups.set(label, [...(groups.get(label) ?? []), trade]);
  }
  return [...groups.entries()]
    // Below three trades a group average is an anecdote, not a pattern.
    .filter(([, group]) => group.length >= 3)
    .map(([label, group]) => ({
      label,
      pnl: group.reduce((sum, trade) => sum + realizedPnl(trade), 0),
      count: group.length
    }));
}

/**
 * Deterministic focus suggestions: the best and worst symbol/strategy/state
 * groups with at least three closed trades. Evidence counts ride along so
 * every suggestion can be checked against the journal it came from.
 */
export function focusActions(trades: TradeEntry[]): FocusAction[] {
  const actions: FocusAction[] = [];
  const dimensions: Array<[string, (trade: TradeEntry) => string]> = [
    ["symbol", (trade) => trade.symbol.toUpperCase()],
    ["strategy", (trade) => trade.strategy],
    ["state", (trade) => trade.emotion.toLowerCase()]
  ];

  for (const [dimension, key] of dimensions) {
    const groups = groupBy(trades, key).sort((a, b) => b.pnl - a.pnl);
    if (!groups.length) continue;
    const best = groups[0];
    const worst = groups[groups.length - 1];
    if (best.pnl > 0) {
      actions.push({
        title: `Your ${best.label} ${dimension} record is carrying the book`,
        detail: `${best.count} closed trades, ${best.pnl >= 0 ? "+" : ""}${best.pnl.toFixed(2)} realized. Worth concentrating on.`,
        tone: "positive"
      });
    }
    if (worst !== best && worst.pnl < 0) {
      actions.push({
        title: `${worst.label} (${dimension}) is costing you`,
        detail: `${worst.count} closed trades, ${worst.pnl.toFixed(2)} realized. Review before adding more.`,
        tone: "caution"
      });
    }
  }
  return actions.slice(0, 4);
}
