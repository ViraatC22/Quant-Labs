import { describe, expect, it } from "vitest";

import type { CalendarEvent } from "./api";
import { eventContext, parseEconomicValue } from "./eventContext";

function event(overrides: Partial<CalendarEvent>): CalendarEvent {
  return {
    title: "CPI y/y",
    currency: "GBP",
    impact: "high",
    scheduledAt: "2026-07-22T06:00:00Z",
    dateLabel: "07-22-2026",
    allDay: false,
    tentative: false,
    forecast: "2.7%",
    previous: "2.8%",
    actual: null,
    url: null,
    ...overrides
  };
}

describe("parseEconomicValue", () => {
  it("parses percents, negatives, and magnitude suffixes", () => {
    expect(parseEconomicValue("2.7%")).toBe(2.7);
    expect(parseEconomicValue("-0.2%")).toBe(-0.2);
    expect(parseEconomicValue("29.4K")).toBe(29_400);
    expect(parseEconomicValue("250M")).toBe(250_000_000);
    expect(parseEconomicValue(null)).toBeNull();
    expect(parseEconomicValue("speech")).toBeNull();
  });
});

describe("eventContext", () => {
  it("relates consensus to previous", () => {
    const lines = eventContext(event({}), {});
    expect(lines[0]).toBe("Consensus 2.7% sits below the previous 2.8%.");
  });

  it("reports the actual against consensus once printed", () => {
    const lines = eventContext(event({ actual: "2.9%" }), {});
    expect(lines).toContain("Printed 2.9% — beat consensus.");
  });

  it("says nothing numeric for speeches with no fields", () => {
    const lines = eventContext(
      event({
        title: "ECB Press Conference",
        forecast: null,
        previous: null,
        scheduledAt: "2026-07-23T20:00:00Z"
      }),
      {}
    );
    // No consensus line, no session line (20:00Z is far from both opens).
    expect(lines).toEqual([]);
  });

  it("flags proximity to a session open", () => {
    // 13:30Z is the NY open itself.
    const lines = eventContext(event({ scheduledAt: "2026-07-22T13:30:00Z" }), {});
    expect(lines.some((line) => line.includes("at the New York open"))).toBe(true);
  });

  it("adds the currency strength reading when supplied", () => {
    const lines = eventContext(event({}), { GBP: 0.145 });
    expect(lines.some((line) => line.includes("GBP currently reads firm"))).toBe(true);
  });

  it("never emits a confidence percentage", () => {
    const lines = eventContext(event({ actual: "2.9%" }), { GBP: 0.1 });
    expect(lines.join(" ")).not.toMatch(/confidence/i);
  });
});
