import { describe, expect, it } from "vitest";

import { MAX_CONFIDENCE, confidenceFormula } from "./confidence";
import type { InstrumentBias } from "./types";

function bias(overrides: Partial<InstrumentBias>): InstrumentBias {
  return {
    symbol: "TEST",
    assetClass: "fx",
    direction: "bullish",
    confidence: 45,
    strength: 0.67,
    agreement: 1,
    coverage: 0.89,
    lastPrice: 1,
    changePercent: 0,
    signals: [],
    explanation: "",
    explanationMode: "derived",
    asOf: "2026-07-24T00:00:00Z",
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

/** Recompute what the printed formula claims, so the string must reconcile. */
function evaluateDirectional(b: InstrumentBias): number {
  return Math.round(MAX_CONFIDENCE * b.strength * b.agreement * b.coverage);
}

function evaluateNeutral(b: InstrumentBias): number {
  return Math.round(MAX_CONFIDENCE * (1 - b.strength) * b.coverage);
}

describe("confidenceFormula", () => {
  it("shows the directional formula for a bullish call", () => {
    const b = bias({ direction: "bullish", strength: 0.67, agreement: 1, coverage: 0.89 });
    const text = confidenceFormula(b);
    expect(text).toContain("strength 0.67");
    expect(text).toContain("agreement 1.00");
    expect(text).toContain("coverage 0.89");
    // The printed terms must actually produce the printed result.
    expect(evaluateDirectional(b)).toBe(45);
    expect(text).toContain("→ 45%");
  });

  it("shows the inverted formula for a ranging call", () => {
    // Regression: the neutral branch of derive_bias uses (1 - strength) and
    // drops agreement entirely. Printing the directional formula here produced
    // "strength 0.11 x agreement 0.72 x coverage 1.00 -> 67%", which is 5.9.
    const b = bias({ direction: "neutral", confidence: 67, strength: 0.11, agreement: 0.72, coverage: 1 });
    const text = confidenceFormula(b);
    expect(text).toContain("(1 − strength 0.11)");
    expect(text).toContain("coverage 1.00");
    expect(text).not.toContain("agreement");
    expect(evaluateNeutral(b)).toBe(67);
    expect(text).toContain("→ 67%");
  });

  it("states the cap in both branches", () => {
    expect(confidenceFormula(bias({ direction: "bullish" }))).toContain("75 cap");
    expect(confidenceFormula(bias({ direction: "neutral" }))).toContain("75 cap");
  });

  it("reconciles across a range of derived values", () => {
    for (const [strength, agreement, coverage] of [
      [0.2, 0.5, 0.8],
      [1, 1, 1],
      [0.45, 0.9, 0.95]
    ] as const) {
      const directional = bias({
        direction: "bearish",
        strength,
        agreement,
        coverage,
        confidence: Math.round(MAX_CONFIDENCE * strength * agreement * coverage)
      });
      expect(confidenceFormula(directional)).toContain(`→ ${directional.confidence}%`);

      const neutral = bias({
        direction: "neutral",
        strength,
        agreement,
        coverage,
        confidence: Math.round(MAX_CONFIDENCE * (1 - strength) * coverage)
      });
      expect(confidenceFormula(neutral)).toContain(`→ ${neutral.confidence}%`);
    }
  });
});
