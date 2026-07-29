import { describe, expect, it } from "vitest";

import { dailyPnl, focusActions, tradeQualityAxes, weekdayPnl } from "./journalInsights";
import type { TradeEntry } from "./types";

let counter = 0;

function trade(overrides: Partial<TradeEntry>): TradeEntry {
  counter += 1;
  return {
    id: `t${counter}`,
    symbol: "EURUSD",
    assetClass: "forex",
    side: "long",
    entryDate: "2026-07-20",
    entryPrice: 1.1,
    exitPrice: 1.11,
    quantity: 1,
    fees: 0,
    strategy: "breakout",
    setup: "",
    emotion: "focused",
    notes: "note",
    ...overrides
  } as TradeEntry;
}

describe("dailyPnl", () => {
  it("buckets realized pnl per day and skips open trades", () => {
    const buckets = dailyPnl([
      trade({ entryDate: "2026-07-20", exitPrice: 1.11 }),
      trade({ entryDate: "2026-07-20", exitPrice: 1.12 }),
      trade({ entryDate: "2026-07-21", exitPrice: null as unknown as number })
    ]);
    expect(buckets).toHaveLength(1);
    expect(buckets[0].date).toBe("2026-07-20");
    expect(buckets[0].count).toBe(2);
    expect(buckets[0].pnl).toBeCloseTo(0.03);
  });
});

describe("weekdayPnl", () => {
  it("maps UTC dates to a Monday-first week", () => {
    // 2026-07-20 is a Monday.
    const rows = weekdayPnl([trade({ entryDate: "2026-07-20" })]);
    expect(rows[0].weekday).toBe("Mon");
    expect(rows[0].count).toBe(1);
    expect(rows[6].weekday).toBe("Sun");
  });
});

describe("tradeQualityAxes", () => {
  it("returns nothing below three closed trades", () => {
    expect(tradeQualityAxes([trade({}), trade({})])).toEqual([]);
  });

  it("scores every axis from measurable fields with a stated reason", () => {
    const axes = tradeQualityAxes([
      trade({ stopPrice: 1.09, emotion: "focused", notes: "a" }),
      trade({ stopPrice: 1.09, emotion: "revenge", notes: "" }),
      trade({ exitPrice: 1.08, emotion: "calm", notes: "b" })
    ]);
    expect(axes).toHaveLength(6);
    for (const axis of axes) {
      expect(axis.score).toBeGreaterThanOrEqual(0);
      expect(axis.score).toBeLessThanOrEqual(100);
      expect(axis.reason).toBeTruthy();
    }
    const state = axes.find((axis) => axis.label === "Decision state");
    expect(state?.reason).toContain("67%");
  });
});

describe("focusActions", () => {
  it("stays silent when no group reaches three trades", () => {
    expect(focusActions([trade({}), trade({ symbol: "GBPUSD" })])).toEqual([]);
  });

  it("names best and worst groups with evidence counts", () => {
    const winners = [1, 2, 3].map(() =>
      trade({ symbol: "XAUUSD", exitPrice: 1.2, strategy: "gold-momo" })
    );
    const losers = [1, 2, 3].map(() =>
      trade({ symbol: "GBPJPY", exitPrice: 1.0, strategy: "chase", emotion: "revenge" })
    );
    const actions = focusActions([...winners, ...losers]);

    expect(actions.length).toBeGreaterThan(0);
    const positive = actions.find((action) => action.tone === "positive");
    const caution = actions.find((action) => action.tone === "caution");
    expect(positive?.title).toContain("XAUUSD");
    expect(positive?.detail).toContain("3 closed trades");
    expect(caution?.title).toContain("GBPJPY");
  });

  it("never suggests concentrating on a losing best group", () => {
    const allLosing = [1, 2, 3].map(() => trade({ symbol: "EURUSD", exitPrice: 1.0 }));
    const actions = focusActions(allLosing);
    expect(actions.every((action) => action.tone === "caution")).toBe(true);
  });
});
