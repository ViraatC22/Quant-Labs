// Pure performance analytics over closed trades — equity curve, risk/expectancy,
// per-strategy breakdown, and a position-size calculator. No React, no I/O, so
// it is unit-tested directly (analytics.test.ts).

import type { TradeEntry } from "@/lib/types";

export function tradeMultiplier(trade: Pick<TradeEntry, "assetClass" | "contractMultiplier">): number {
  if (trade.contractMultiplier && trade.contractMultiplier > 0) return trade.contractMultiplier;
  if (trade.assetClass === "option") return 100;
  return 1;
}

export function isClosed(trade: TradeEntry): boolean {
  return trade.exitPrice !== null && trade.exitPrice !== undefined;
}

// Realized P&L for a closed trade (no live marks): the canonical closed-trade
// formula, matching the server.
export function realizedPnl(trade: TradeEntry): number {
  if (!isClosed(trade)) return 0;
  const direction = trade.side === "short" ? -1 : 1;
  return (
    (Number(trade.exitPrice) - trade.entryPrice) *
      trade.quantity *
      tradeMultiplier(trade) *
      direction -
    (trade.fees ?? 0)
  );
}

// Risk per trade in dollars, from an explicit risk amount or a stop distance.
export function tradeRiskDollars(trade: TradeEntry): number | null {
  if (trade.riskAmount && trade.riskAmount > 0) return trade.riskAmount;
  if (trade.stopPrice && trade.stopPrice > 0) {
    const perUnit = Math.abs(trade.entryPrice - trade.stopPrice);
    const risk = perUnit * trade.quantity * tradeMultiplier(trade);
    return risk > 0 ? risk : null;
  }
  return null;
}

// R-multiple: realized P&L expressed in units of the trade's initial risk.
export function tradeR(trade: TradeEntry): number | null {
  if (!isClosed(trade)) return null;
  const risk = tradeRiskDollars(trade);
  if (!risk) return null;
  return realizedPnl(trade) / risk;
}

export type EquityPoint = { date: string; cumulative: number; pnl: number; symbol: string };

// Cumulative realized P&L over time, ordered by entry date.
export function equityCurve(trades: TradeEntry[]): EquityPoint[] {
  const closed = trades
    .filter(isClosed)
    .slice()
    .sort((a, b) => a.entryDate.localeCompare(b.entryDate));
  let cumulative = 0;
  return closed.map((trade) => {
    const pnl = realizedPnl(trade);
    cumulative += pnl;
    return { date: trade.entryDate, cumulative, pnl, symbol: trade.symbol };
  });
}

export function maxDrawdown(curve: EquityPoint[]): number {
  let peak = 0;
  let maxDd = 0;
  for (const point of curve) {
    peak = Math.max(peak, point.cumulative);
    maxDd = Math.min(maxDd, point.cumulative - peak);
  }
  return maxDd; // <= 0
}

export type PerformanceStats = {
  count: number;
  realizedPnl: number;
  wins: number;
  losses: number;
  winRate: number; // 0..1
  avgWin: number;
  avgLoss: number;
  profitFactor: number | null;
  expectancyR: number | null;
  rSampleSize: number;
  maxDrawdown: number;
};

export function performanceStats(trades: TradeEntry[]): PerformanceStats {
  const closed = trades.filter(isClosed);
  const pnls = closed.map(realizedPnl);
  const winsArr = pnls.filter((p) => p > 0);
  const lossesArr = pnls.filter((p) => p < 0);
  const grossProfit = winsArr.reduce((s, p) => s + p, 0);
  const grossLoss = Math.abs(lossesArr.reduce((s, p) => s + p, 0));
  const rs = closed.map(tradeR).filter((r): r is number => r !== null);

  return {
    count: closed.length,
    realizedPnl: pnls.reduce((s, p) => s + p, 0),
    wins: winsArr.length,
    losses: lossesArr.length,
    winRate: closed.length ? winsArr.length / closed.length : 0,
    avgWin: winsArr.length ? grossProfit / winsArr.length : 0,
    avgLoss: lossesArr.length ? -grossLoss / lossesArr.length : 0,
    profitFactor: grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? Infinity : null,
    expectancyR: rs.length ? rs.reduce((s, r) => s + r, 0) / rs.length : null,
    rSampleSize: rs.length,
    maxDrawdown: maxDrawdown(equityCurve(trades))
  };
}

export type StrategyPerf = { name: string; pnl: number; count: number; winRate: number };

export function strategyBreakdown(trades: TradeEntry[]): StrategyPerf[] {
  const groups = new Map<string, TradeEntry[]>();
  for (const trade of trades.filter(isClosed)) {
    const key = trade.strategy?.trim() || "Unlabeled";
    groups.set(key, [...(groups.get(key) ?? []), trade]);
  }
  return Array.from(groups.entries())
    .map(([name, group]) => {
      const pnls = group.map(realizedPnl);
      const wins = pnls.filter((p) => p > 0).length;
      return {
        name,
        pnl: pnls.reduce((s, p) => s + p, 0),
        count: group.length,
        winRate: group.length ? wins / group.length : 0
      };
    })
    .sort((a, b) => b.pnl - a.pnl);
}

export type PositionSizeResult = {
  quantity: number;
  riskAmount: number;
  perUnitRisk: number;
};

// account * risk% / (|entry-stop| * multiplier) -> whole-unit quantity.
export function positionSize(
  accountSize: number,
  riskPercent: number,
  entry: number,
  stop: number,
  multiplier = 1
): PositionSizeResult | null {
  const perUnit = Math.abs(entry - stop) * multiplier;
  if (accountSize <= 0 || riskPercent <= 0 || perUnit <= 0) return null;
  const riskAmount = accountSize * (riskPercent / 100);
  return {
    quantity: Math.floor(riskAmount / perUnit),
    riskAmount,
    perUnitRisk: perUnit
  };
}
