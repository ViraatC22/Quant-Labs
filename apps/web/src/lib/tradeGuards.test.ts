import { describe, expect, it } from "vitest";

import {
  accountBuyingPower,
  tradeCapitalRequirement,
  validateTradeBuyingPower
} from "@/lib/tradeGuards";
import type { TradeEntry } from "@/lib/types";

function trade(overrides: Partial<TradeEntry>): TradeEntry {
  return {
    id: "trade-1",
    symbol: "SPY",
    assetClass: "equity",
    side: "long",
    entryDate: "2026-07-09",
    entryPrice: 100,
    exitPrice: null,
    quantity: 1,
    fees: 0,
    strategy: "Test",
    setup: "",
    emotion: "focused",
    notes: "",
    createdAt: "2026-07-09T00:00:00Z",
    ...overrides
  };
}

describe("tradeGuards", () => {
  it("blocks a covered call when account buying power cannot reserve the underlying shares", () => {
    const coveredCall = trade({
      assetClass: "option",
      side: "short",
      entryPrice: 2,
      optionType: "call",
      strikePrice: 500,
      contractMultiplier: 100,
      quantity: 1,
      strategy: "Covered call income",
      notes: "covered call"
    });

    const result = validateTradeBuyingPower(coveredCall, [], 10000);

    expect(result.ok).toBe(false);
    expect(result.reason).toBe("capital");
    expect(result.requirement.amount).toBe(50000);
    expect(result.requirement.underlyingShares).toBe(100);
  });

  it("allows a long option when the premium fits inside available buying power", () => {
    const longCall = trade({
      assetClass: "option",
      entryPrice: 2,
      optionType: "call",
      contractMultiplier: 100,
      quantity: 1
    });

    const result = validateTradeBuyingPower(longCall, [], 10000);

    expect(result.ok).toBe(true);
    expect(tradeCapitalRequirement(longCall, true).amount).toBe(200);
  });

  it("reserves capital from existing open paper trades before validating a new trade", () => {
    const openStock = trade({ entryPrice: 80, quantity: 100 });
    const nextStock = trade({ id: "trade-2", entryPrice: 30, quantity: 100 });

    expect(accountBuyingPower([openStock], 10000).buyingPower).toBe(2000);
    expect(validateTradeBuyingPower(nextStock, [openStock], 10000).ok).toBe(false);
  });
});
