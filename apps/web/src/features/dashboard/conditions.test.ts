import { describe, expect, it } from "vitest";

import { conditionsScore } from "./conditions";
import type { InstrumentBias } from "./types";

function bias(overrides: Partial<InstrumentBias>): InstrumentBias {
  return {
    symbol: "TEST",
    assetClass: "fx",
    direction: "bullish",
    confidence: 50,
    strength: 0.8,
    agreement: 0.9,
    coverage: 1,
    lastPrice: 1,
    changePercent: 0.5,
    signals: [],
    explanation: "",
    explanationMode: "derived",
    asOf: "2026-07-25T00:00:00Z",
    provider: "yahoo_chart",
    priceBasis: "indicative_mid",
    sampleSize: 500,
    delayed: true,
    stale: false,
    proxyNote: null,
    limitations: [],
    writerProviderId: null,
    writerModel: null,
    news: [],
    rawConfidence: 50,
    calibrationApplied: false,
    calibrationSample: 0,
    calibrationNote: "",
    ...overrides
  };
}

describe("conditionsScore", () => {
  it("scores clean trend in tradable, healthy conditions as supported", () => {
    const result = conditionsScore(bias({}), {
      flow: "healthy",
      pulse: "tradable",
      bearing: "trending up"
    });
    expect(result.label).toBe("Supported");
    expect(result.score).toBeGreaterThanOrEqual(70);
  });

  it("marks a ranging desk in thin, quiet conditions as low clarity", () => {
    const result = conditionsScore(
      bias({ direction: "neutral", strength: 0.05, agreement: 0.3 }),
      { flow: "thin", pulse: "quiet", bearing: "flat" }
    );
    expect(result.label).toBe("Low clarity");
    const clarity = result.components.find((c) => c.label === "Directional clarity");
    expect(clarity?.reason).toContain("ranging");
  });

  it("keeps every component bounded with a reason", () => {
    const result = conditionsScore(bias({ coverage: 0.5 }), {
      flow: "crowded",
      pulse: "wild",
      bearing: "choppy down"
    });
    for (const component of result.components) {
      expect(component.score).toBeGreaterThanOrEqual(0);
      expect(component.score).toBeLessThanOrEqual(100);
      expect(component.reason).toBeTruthy();
    }
  });

  it("degrades gracefully on unknown regime labels", () => {
    const result = conditionsScore(bias({}), {
      flow: "unavailable",
      pulse: "unavailable",
      bearing: "flat"
    });
    expect(result.score).toBeGreaterThan(0);
  });
});
