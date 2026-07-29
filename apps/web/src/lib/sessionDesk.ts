import { isClosed, realizedPnl, tradeR } from "@/lib/analytics";
import type { JournalEntry, TradeEntry, VaultItem } from "@/lib/types";

export type EdgeFactor = {
  score: number;
  label: "Insufficient evidence" | "Low clarity" | "Mixed" | "Supported";
  sample: number;
  components: Array<{ label: string; score: number; reason: string }>;
};

function clamp(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

export function edgeFactor(
  trades: TradeEntry[],
  symbol?: string,
  strategy?: string
): EdgeFactor {
  const closed = trades.filter(
    (trade) =>
      isClosed(trade) &&
      (!symbol || trade.symbol.toUpperCase() === symbol.toUpperCase()) &&
      (!strategy || trade.strategy.trim().toLowerCase() === strategy.trim().toLowerCase())
  );
  if (closed.length < 3) {
    return {
      score: 0,
      label: "Insufficient evidence",
      sample: closed.length,
      components: [
        {
          label: "Evidence",
          score: 0,
          reason: `${closed.length}/3 minimum comparable closed trades`
        }
      ]
    };
  }

  const pnls = closed.map(realizedPnl);
  const winRate = pnls.filter((value) => value > 0).length / closed.length;
  const grossWin = pnls.filter((value) => value > 0).reduce((sum, value) => sum + value, 0);
  const grossLoss = Math.abs(
    pnls.filter((value) => value < 0).reduce((sum, value) => sum + value, 0)
  );
  const profitFactor = grossLoss ? grossWin / grossLoss : grossWin > 0 ? 2 : 0;
  const riskDefined = closed.filter(
    (trade) => Boolean(trade.riskAmount) || Boolean(trade.stopPrice)
  ).length / closed.length;
  const routineQuality = closed.filter((trade) =>
    ["patient", "focused", "calm", "disciplined"].includes(trade.emotion.toLowerCase())
  ).length / closed.length;
  const sampleQuality = Math.min(1, closed.length / 20);

  const components = [
    {
      label: "Outcome quality",
      score: clamp(winRate * 100),
      reason: `${Math.round(winRate * 100)}% win rate`
    },
    {
      label: "Payoff quality",
      score: clamp(Math.min(profitFactor, 2) * 50),
      reason: `${Number.isFinite(profitFactor) ? profitFactor.toFixed(2) : "∞"} profit factor`
    },
    {
      label: "Risk definition",
      score: clamp(riskDefined * 100),
      reason: `${Math.round(riskDefined * 100)}% have stop or planned risk`
    },
    {
      label: "Decision state",
      score: clamp(routineQuality * 100),
      reason: `${Math.round(routineQuality * 100)}% logged calm/patient/focused`
    },
    {
      label: "Sample reliability",
      score: clamp(sampleQuality * 100),
      reason: `${closed.length} comparable trades; 20 is full weight`
    }
  ];
  const score = clamp(
    components[0].score * 0.25 +
      components[1].score * 0.25 +
      components[2].score * 0.2 +
      components[3].score * 0.1 +
      components[4].score * 0.2
  );
  return {
    score,
    label: score >= 70 ? "Supported" : score >= 50 ? "Mixed" : "Low clarity",
    sample: closed.length,
    components
  };
}

export type CoachFinding = {
  title: string;
  finding: string;
  evidence: string;
  tone: "positive" | "caution" | "neutral";
};

function groupPerformance(trades: TradeEntry[], key: (trade: TradeEntry) => string) {
  const groups = new Map<string, TradeEntry[]>();
  for (const trade of trades.filter(isClosed)) {
    const label = key(trade) || "Unlabeled";
    groups.set(label, [...(groups.get(label) ?? []), trade]);
  }
  return [...groups.entries()]
    .filter(([, group]) => group.length >= 2)
    .map(([label, group]) => ({
      label,
      count: group.length,
      pnl: group.reduce((sum, trade) => sum + realizedPnl(trade), 0),
      avgR: (() => {
        const values = group.map(tradeR).filter((value): value is number => value !== null);
        return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
      })()
    }))
    .sort((a, b) => b.pnl - a.pnl);
}

export function coachingFindings(
  trades: TradeEntry[],
  journal: JournalEntry[]
): CoachFinding[] {
  const closed = trades.filter(isClosed);
  if (closed.length < 3) {
    return [
      {
        title: "Build the evidence base",
        finding: "No behavioral conclusion is justified yet.",
        evidence: `${closed.length}/3 closed trades available`,
        tone: "neutral"
      }
    ];
  }
  const findings: CoachFinding[] = [];
  const sessions = groupPerformance(closed, (trade) => trade.session || "Unlabeled");
  if (sessions.length) {
    const best = sessions[0];
    const worst = sessions[sessions.length - 1];
    findings.push({
      title: "Session concentration",
      finding:
        best.label === worst.label
          ? `${best.label} is your only repeated session sample.`
          : `${best.label} outperforms ${worst.label} by recorded P&L.`,
      evidence: `${best.label}: ${best.count} trades / $${best.pnl.toFixed(0)}; ${worst.label}: ${worst.count} / $${worst.pnl.toFixed(0)}`,
      tone: best.pnl > worst.pnl ? "positive" : "neutral"
    });
  }
  const states = groupPerformance(closed, (trade) => trade.emotion || "Unlabeled");
  if (states.length) {
    const best = states[0];
    const worst = states[states.length - 1];
    findings.push({
      title: "Decision-state effect",
      finding: `${best.label} is your strongest repeated logged state; ${worst.label} is weakest.`,
      evidence: `${best.count + worst.count} trades compared; descriptive, not causal`,
      tone: "caution"
    });
  }
  const routineDays = new Set(
    journal.filter((entry) => entry.routineDone).map((entry) => entry.date.slice(0, 10))
  );
  const withRoutine = closed.filter((trade) => routineDays.has(trade.entryDate.slice(0, 10)));
  const withoutRoutine = closed.filter((trade) => !routineDays.has(trade.entryDate.slice(0, 10)));
  if (withRoutine.length >= 2 && withoutRoutine.length >= 2) {
    const avg = (values: TradeEntry[]) =>
      values.reduce((sum, trade) => sum + realizedPnl(trade), 0) / values.length;
    findings.push({
      title: "Routine association",
      finding:
        avg(withRoutine) >= avg(withoutRoutine)
          ? "Recorded routine days correlate with stronger average results."
          : "Recorded routine days have not correlated with stronger results yet.",
      evidence: `$${avg(withRoutine).toFixed(0)} vs $${avg(withoutRoutine).toFixed(0)} average; correlation only`,
      tone: avg(withRoutine) >= avg(withoutRoutine) ? "positive" : "caution"
    });
  }
  return findings;
}

export function macroSources(vault: VaultItem[]) {
  const terms = [
    "macro",
    "rates",
    "inflation",
    "fed",
    "central bank",
    "currency",
    "economic",
    "yield",
    "oil",
    "gold"
  ];
  return vault
    .filter((item) => {
      const text = `${item.title} ${item.body} ${item.tags.join(" ")}`.toLowerCase();
      return terms.some((term) => text.includes(term));
    })
    .slice(0, 8);
}

export type DayPerformance = {
  day: string;
  count: number;
  pnl: number;
  wins: number;
};

const weekDays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function pnlByWeekday(trades: TradeEntry[]): DayPerformance[] {
  const rows = weekDays.map((day) => ({ day, count: 0, pnl: 0, wins: 0 }));
  for (const trade of trades.filter(isClosed)) {
    const date = new Date(`${trade.entryDate.slice(0, 10)}T12:00:00Z`);
    if (Number.isNaN(date.getTime())) continue;
    const row = rows[date.getUTCDay()];
    const pnl = realizedPnl(trade);
    row.count += 1;
    row.pnl += pnl;
    if (pnl > 0) row.wins += 1;
  }
  return rows;
}

export type TradeQuality = {
  overall: number;
  axes: Array<{ label: string; score: number; evidence: string }>;
};

export function tradeQualityCoverage(trades: TradeEntry[]): TradeQuality {
  const sample = trades.filter(isClosed);
  if (!sample.length) {
    return {
      overall: 0,
      axes: [
        { label: "Entry context", score: 0, evidence: "No closed trades" },
        { label: "Exit context", score: 0, evidence: "No closed trades" },
        { label: "Risk definition", score: 0, evidence: "No closed trades" },
        { label: "Discipline", score: 0, evidence: "No closed trades" },
        { label: "Patience", score: 0, evidence: "No closed trades" },
        { label: "Execution record", score: 0, evidence: "No closed trades" }
      ]
    };
  }
  const ratio = (test: (trade: TradeEntry) => boolean) =>
    clamp((sample.filter(test).length / sample.length) * 100);
  const calmStates = new Set(["patient", "focused", "calm", "disciplined"]);
  const axes = [
    {
      label: "Entry context",
      score: ratio((trade) => Boolean(trade.setup && trade.strategy)),
      evidence: "setup and strategy recorded"
    },
    {
      label: "Exit context",
      score: ratio((trade) => Boolean(trade.targetPrice || trade.notes)),
      evidence: "target or review note recorded"
    },
    {
      label: "Risk definition",
      score: ratio((trade) => Boolean(trade.stopPrice || trade.riskAmount)),
      evidence: "stop or planned risk recorded"
    },
    {
      label: "Discipline",
      score: ratio((trade) => Boolean(trade.notes && trade.setup)),
      evidence: "setup plus execution note recorded"
    },
    {
      label: "Patience",
      score: ratio((trade) => calmStates.has(trade.emotion.toLowerCase())),
      evidence: "calm/patient/focused state recorded"
    },
    {
      label: "Execution record",
      score: ratio(
        (trade) =>
          trade.entryPrice > 0 &&
          trade.exitPrice !== null &&
          trade.quantity > 0 &&
          Boolean(trade.entryDate)
      ),
      evidence: "entry, exit, size, and date complete"
    }
  ];
  return {
    overall: clamp(axes.reduce((sum, axis) => sum + axis.score, 0) / axes.length),
    axes
  };
}
