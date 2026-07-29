// Renders the exact arithmetic behind a bias card's confidence number.
//
// This exists because the two branches in services/desk/bias.py use different
// formulas, and a UI that prints one while the server computed the other shows
// a sum that does not add up. The whole point of exposing the derivation is
// that a reader can check it, so it has to match `derive_bias` exactly.

import type { InstrumentBias } from "./types";

/** Mirror of bias.MAX_CONFIDENCE. Keep in step with the server constant. */
export const MAX_CONFIDENCE = 75;

/**
 * A directional call is scored on how strong and agreed-upon the move is.
 * A ranging call inverts that — conviction comes from the *absence* of
 * direction — and participation does not corroborate a non-move, so agreement
 * is not a factor.
 */
export function confidenceFormula(bias: InstrumentBias): string {
  const strength = bias.strength.toFixed(2);
  const coverage = bias.coverage.toFixed(2);

  if (bias.direction === "neutral") {
    return `${MAX_CONFIDENCE} cap × (1 − strength ${strength}) × coverage ${coverage} → ${bias.confidence}%`;
  }
  return (
    `${MAX_CONFIDENCE} cap × strength ${strength} × agreement ${bias.agreement.toFixed(2)}` +
    ` × coverage ${coverage} → ${bias.confidence}%`
  );
}
