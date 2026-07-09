import { describe, expect, it } from "vitest";

import {
  equityCurve,
  maxDrawdown,
  performanceStats,
  positionSize,
  realizedPnl,
  strategyBreakdown,
  tradeR
} from "@/lib/analytics";
import type { TradeEntry } from "@/lib/types";

function trade(over: Partial<TradeEntry>): TradeEntry {
  return {
    id: Math.random().toString(36),
    symbol: "AAPL",
    side: "long",
    entryDate: "2026-07-01",
    entryPrice: 100,
    exitPrice: 110,
    quantity: 10,
    fees: 0,
    strategy: "VWAP Pullback",
    setup: "",
    emotion: "focused",
    notes: "",
    createdAt: "2026-07-01T00:00:00Z",
    ...over
  };
}

describe("analytics", () => {
  it("computes realized P&L with multiplier and direction", () => {
    expect(realizedPnl(trade({ entryPrice: 100, exitPrice: 110, quantity: 10 }))).toBe(100);
    expect(
      realizedPnl(trade({ side: "short", entryPrice: 100, exitPrice: 90, quantity: 10 }))
    ).toBe(100);
    expect(
      realizedPnl(trade({ assetClass: "future", contractMultiplier: 5, entryPrice: 5000, exitPrice: 5005, quantity: 2, fees: 1 }))
    ).toBe(49);
  });

  it("returns null R when there is no stop or risk", () => {
    expect(tradeR(trade({ stopPrice: null, riskAmount: null }))).toBeNull();
  });

  it("computes R from stop distance", () => {
    // entry 100, stop 98 -> risk 2*10 = 20; pnl (110-100)*10 = 100 -> R = 5
    expect(tradeR(trade({ entryPrice: 100, exitPrice: 110, stopPrice: 98, quantity: 10 }))).toBe(5);
  });

  it("builds a cumulative equity curve in date order", () => {
    const curve = equityCurve([
      trade({ entryDate: "2026-07-02", entryPrice: 100, exitPrice: 90, quantity: 10 }), // -100
      trade({ entryDate: "2026-07-01", entryPrice: 100, exitPrice: 110, quantity: 10 }) // +100
    ]);
    expect(curve.map((p) => p.cumulative)).toEqual([100, 0]);
  });

  it("computes max drawdown as a non-positive number", () => {
    const curve = equityCurve([
      trade({ entryDate: "2026-07-01", entryPrice: 100, exitPrice: 110, quantity: 10 }), // +100
      trade({ entryDate: "2026-07-02", entryPrice: 100, exitPrice: 70, quantity: 10 }) // -300
    ]);
    expect(maxDrawdown(curve)).toBe(-300);
  });

  it("computes win rate, profit factor, and expectancy", () => {
    const stats = performanceStats([
      trade({ entryPrice: 100, exitPrice: 110, quantity: 10, stopPrice: 98 }), // +100, R=5
      trade({ entryPrice: 100, exitPrice: 95, quantity: 10, stopPrice: 98 }) // -50, R=-2.5
    ]);
    expect(stats.count).toBe(2);
    expect(stats.wins).toBe(1);
    expect(stats.winRate).toBe(0.5);
    expect(stats.profitFactor).toBe(2); // 100 / 50
    expect(stats.expectancyR).toBeCloseTo(1.25); // (5 + -2.5)/2
    expect(stats.rSampleSize).toBe(2);
  });

  it("breaks down performance by strategy, best first", () => {
    const rows = strategyBreakdown([
      trade({ strategy: "A", entryPrice: 100, exitPrice: 90, quantity: 10 }), // -100
      trade({ strategy: "B", entryPrice: 100, exitPrice: 120, quantity: 10 }) // +200
    ]);
    expect(rows[0].name).toBe("B");
    expect(rows[0].pnl).toBe(200);
  });

  it("sizes a position from account, risk%, and stop distance", () => {
    // 10000 * 1% = 100 risk; entry 100 stop 98 -> 2/unit -> 50 shares
    expect(positionSize(10000, 1, 100, 98)?.quantity).toBe(50);
    expect(positionSize(10000, 1, 5000, 4990, 5)?.quantity).toBe(2); // futures mult 5: 50/unit
    expect(positionSize(0, 1, 100, 98)).toBeNull();
  });
});
