// Market-conditions score for the deep dive.
//
// This answers "do current conditions support taking a setup at all?" and is
// deliberately a separate number from the trade-record Edge Factor in
// lib/sessionDesk.ts, which scores *your history* on a symbol. Same label
// vocabulary, different subject — conflating them was a trap this codebase
// already stepped around once.
//
// Inputs are all values the deep dive already fetched: the bias derivation
// (strength/agreement/coverage) plus the regime labels (flow/pulse/bearing).
// Deterministic; every component carries its reason.

import type { MarketContext } from "@/lib/types";

import type { InstrumentBias } from "./types";

export type ConditionsComponent = { label: string; score: number; reason: string };

export type ConditionsScore = {
  score: number;
  label: "Supported" | "Mixed" | "Low clarity";
  components: ConditionsComponent[];
};

function clamp(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

/** How tradable the volatility state is: quiet and wild both cost you. */
const PULSE_SCORES: Record<string, [number, string]> = {
  tradable: [100, "volatility in its normal range — setups have room to breathe"],
  quiet: [40, "volatility compressed — targets need to shrink"],
  wild: [30, "volatility elevated — stop-outs more likely at normal size"],
  unavailable: [50, "volatility state unknown"]
};

const FLOW_SCORES: Record<string, [number, string]> = {
  healthy: [100, "participation in its normal band"],
  thin: [35, "thin participation — moves are easier to fake out"],
  crowded: [55, "very high participation — momentum may be over-extended"],
  unavailable: [50, "participation unknown"]
};

export function conditionsScore(
  bias: InstrumentBias,
  context: Pick<MarketContext, "flow" | "pulse" | "bearing">
): ConditionsScore {
  const [pulseScore, pulseReason] = PULSE_SCORES[context.pulse] ?? PULSE_SCORES.unavailable;
  const [flowScore, flowReason] = FLOW_SCORES[context.flow] ?? FLOW_SCORES.unavailable;

  const clarity = clamp(bias.strength * bias.agreement * 100);
  const clarityReason =
    bias.direction === "neutral"
      ? "no directional agreement — the desk reads ranging"
      : `${bias.direction} with strength ${bias.strength.toFixed(2)} × agreement ${bias.agreement.toFixed(2)}`;

  const components: ConditionsComponent[] = [
    { label: "Directional clarity", score: clarity, reason: clarityReason },
    { label: "Volatility", score: pulseScore, reason: pulseReason },
    { label: "Participation", score: flowScore, reason: flowReason },
    {
      label: "Data coverage",
      score: clamp(bias.coverage * 100),
      reason: `${Math.round(bias.coverage * 100)}% of the indicator set was available`
    }
  ];

  const score = clamp(
    components[0].score * 0.4 +
      components[1].score * 0.25 +
      components[2].score * 0.15 +
      components[3].score * 0.2
  );

  return {
    score,
    label: score >= 70 ? "Supported" : score >= 45 ? "Mixed" : "Low clarity",
    components
  };
}
