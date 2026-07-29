import { describe, expect, it } from "vitest";

import {
  coachingFindings,
  edgeFactor,
  pnlByWeekday,
  tradeQualityCoverage
} from "@/lib/sessionDesk";
import type { TradeEntry } from "@/lib/types";

function trade(id: string, pnl: number, emotion = "focused", session = "London"): TradeEntry {
  return {
    id,
    symbol: "EURUSD",
    assetClass: "forex",
    side: "long",
    entryDate: `2026-07-${id.padStart(2, "0")}`,
    entryPrice: 100,
    exitPrice: 100 + pnl,
    quantity: 1,
    fees: 0,
    riskAmount: 1,
    strategy: "breakout",
    setup: "range break",
    emotion,
    session,
    notes: "",
    createdAt: "2026-07-01"
  };
}

describe("session desk evidence", () => {
  it("refuses to score tiny samples", () => {
    expect(edgeFactor([trade("1", 1), trade("2", -1)]).label).toBe("Insufficient evidence");
  });

  it("exposes weighted components and sample", () => {
    const result = edgeFactor([
      trade("1", 2),
      trade("2", 2),
      trade("3", 2),
      trade("4", -1)
    ]);
    expect(result.sample).toBe(4);
    expect(result.components).toHaveLength(5);
    expect(result.score).toBeGreaterThan(50);
  });

  it("labels coaching comparisons as descriptive", () => {
    const findings = coachingFindings(
      [
        trade("1", 2, "focused", "London"),
        trade("2", 1, "focused", "London"),
        trade("3", -2, "rushed", "New York"),
        trade("4", -1, "rushed", "New York")
      ],
      []
    );
    expect(findings.some((item) => item.evidence.includes("descriptive, not causal"))).toBe(true);
  });

  it("calculates weekday performance from recorded outcomes", () => {
    const rows = pnlByWeekday([trade("1", 2), trade("2", -1)]);
    expect(rows.reduce((sum, row) => sum + row.count, 0)).toBe(2);
    expect(rows.reduce((sum, row) => sum + row.pnl, 0)).toBe(1);
  });

  it("scores record coverage without calling it predictive quality", () => {
    const result = tradeQualityCoverage([trade("1", 2)]);
    expect(result.axes).toHaveLength(6);
    expect(result.overall).toBeGreaterThan(0);
  });
});
