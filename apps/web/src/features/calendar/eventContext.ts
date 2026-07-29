// Derived per-event context lines. Every clause traces to a real field:
// consensus vs previous (from the feed), proximity to a session open (from the
// clock), and the currency's current strength reading (from the desk).
//
// Deliberately absent: a per-event "confidence" percentage. The reference
// product prints one next to every release; there is nothing to derive it
// from, so no number is shown.

import type { CalendarEvent } from "./api";

/** Parse "2.7%", "29.4K", "-0.2%", "250M", "3.00%" into a comparable number. */
export function parseEconomicValue(raw: string | null): number | null {
  if (!raw) return null;
  const cleaned = raw.trim().replace(/[,%]/g, "");
  const match = cleaned.match(/^(-?\d+(?:\.\d+)?)([KMBT])?$/i);
  if (!match) return null;
  const value = Number(match[1]);
  const scale = { K: 1e3, M: 1e6, B: 1e9, T: 1e12 }[match[2]?.toUpperCase() ?? ""] ?? 1;
  return value * scale;
}

const SESSION_OPENS_UTC_MINUTES: Array<{ label: string; minutes: number }> = [
  // Approximate opens in UTC; the strip on the dashboard carries the exact,
  // DST-correct versions. Good enough for "lands near the open" phrasing.
  { label: "London open", minutes: 7 * 60 },
  { label: "New York open", minutes: 13 * 60 + 30 }
];

export function eventContext(
  event: CalendarEvent,
  strengthByCurrency: Record<string, number>
): string[] {
  const lines: string[] = [];

  const consensus = parseEconomicValue(event.forecast);
  const previous = parseEconomicValue(event.previous);
  if (consensus !== null && previous !== null && event.forecast && event.previous) {
    const relation =
      consensus > previous ? "above" : consensus < previous ? "below" : "level with";
    lines.push(
      `Consensus ${event.forecast} sits ${relation} the previous ${event.previous}.`
    );
  }

  const actual = parseEconomicValue(event.actual);
  if (actual !== null && consensus !== null && event.actual) {
    const relation = actual > consensus ? "beat" : actual < consensus ? "missed" : "met";
    lines.push(`Printed ${event.actual} — ${relation} consensus.`);
  }

  if (event.scheduledAt) {
    const date = new Date(event.scheduledAt);
    const minutes = date.getUTCHours() * 60 + date.getUTCMinutes();
    for (const open of SESSION_OPENS_UTC_MINUTES) {
      const distance = minutes - open.minutes;
      if (Math.abs(distance) <= 90) {
        lines.push(
          distance >= 0
            ? `Lands ${distance ? `${distance}m after` : "at"} the ${open.label}.`
            : `Lands ${-distance}m before the ${open.label}.`
        );
        break;
      }
    }
  }

  const strength = strengthByCurrency[event.currency];
  if (strength !== undefined) {
    const word = strength > 0.05 ? "firm" : strength < -0.05 ? "soft" : "flat";
    lines.push(
      `${event.currency} currently reads ${word} on the strength meter (${
        strength > 0 ? "+" : ""
      }${strength.toFixed(3)}).`
    );
  }

  return lines;
}
