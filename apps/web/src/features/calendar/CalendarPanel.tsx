"use client";

// Economic calendar: this week's events grouped by day, with a now-marker.
//
// Deliberately absent: a per-event "confidence" score. The reference dashboard
// prints one next to each release, but there is nothing to derive it from — an
// ECB speech has no measurable probability attached. Impact tier, consensus
// forecast, and previous value are all real fields from the feed; a confidence
// percentage would be invented.

import { AlertTriangle, CalendarDays, ExternalLink, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import { fetchStrength } from "@/features/dashboard/api";

import { fetchCalendar, type CalendarEvent, type CalendarFeed, type CalendarImpact } from "./api";
import { eventContext } from "./eventContext";

const IMPACT_ORDER: CalendarImpact[] = ["high", "medium", "low", "holiday"];

const IMPACT_STYLE: Record<CalendarImpact, string> = {
  high: "border-loss/40 bg-loss/10 text-loss",
  medium: "border-caution/40 bg-caution/10 text-caution",
  low: "border-line bg-ink/5 text-ink/55",
  holiday: "border-signal/30 bg-signal/10 text-signal",
  unknown: "border-line bg-ink/5 text-ink/45"
};

function dayKey(event: CalendarEvent): string {
  if (event.scheduledAt) return event.scheduledAt.slice(0, 10);
  // MM-DD-YYYY from the feed, normalized so undated events still group.
  const [month, day, year] = event.dateLabel.split("-");
  return `${year}-${month}-${day}`;
}

function formatDayHeading(key: string): string {
  const date = new Date(`${key}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return key;
  return date.toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "short",
    timeZone: "UTC"
  });
}

function formatTime(event: CalendarEvent): string {
  if (event.allDay) return "All day";
  if (event.tentative) return "Tentative";
  if (!event.scheduledAt) return "—";
  return `${event.scheduledAt.slice(11, 16)}Z`;
}

export function CalendarPanel() {
  const [feed, setFeed] = useState<CalendarFeed | null>(null);
  const [strengthByCurrency, setStrengthByCurrency] = useState<Record<string, number>>({});
  const [impacts, setImpacts] = useState<CalendarImpact[]>(["high", "medium"]);
  const [currency, setCurrency] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const result = await fetchCalendar();
      // Strength is optional garnish on the context lines; a failure there
      // must not take the calendar down with it.
      const strength = await fetchStrength().catch(() => null);
      setError(null);
      setFeed(result);
      if (strength) {
        setStrengthByCurrency(
          Object.fromEntries(strength.currencies.map((item) => [item.currency, item.score]))
        );
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The calendar could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    async function run() {
      await load();
    }
    void run();
    const timer = window.setInterval(() => void run(), 300_000);
    return () => window.clearInterval(timer);
  }, [load]);

  // Filtering happens client-side so toggling a chip does not re-fetch a feed
  // that only changes every 15 minutes.
  const visible = useMemo(() => {
    const events = feed?.events ?? [];
    return events.filter(
      (event) =>
        impacts.includes(event.impact) && (!currency || event.currency === currency)
    );
  }, [feed, impacts, currency]);

  const currencies = useMemo(
    () => [...new Set((feed?.events ?? []).map((event) => event.currency))].sort(),
    [feed]
  );

  const grouped = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    for (const event of visible) {
      const key = dayKey(event);
      map.set(key, [...(map.get(key) ?? []), event]);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [visible]);

  const now = feed?.nowUtc ? new Date(feed.nowUtc) : new Date();

  function toggleImpact(value: CalendarImpact) {
    setImpacts((current) =>
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value]
    );
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <CalendarDays aria-hidden="true" className="text-ink/50" size={19} strokeWidth={2.2} />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-ink">Calendar</h1>
            <p className="text-sm text-ink/55">
              This week&apos;s scheduled events, in UTC.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {feed?.stale && <Badge variant="warning">Cached</Badge>}
          <button
            aria-label="Refresh the calendar"
            className="flex items-center gap-2 rounded-md border border-line bg-card px-3 py-1.5 text-sm text-ink/70 hover:text-ink"
            onClick={() => void load()}
            type="button"
          >
            <RefreshCw
              aria-hidden="true"
              className={loading ? "animate-spin" : undefined}
              size={15}
              strokeWidth={2.2}
            />
            Refresh
          </button>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        {IMPACT_ORDER.map((value) => (
          <button
            className={cn(
              "rounded-md border px-2.5 py-1 text-xs font-medium capitalize",
              impacts.includes(value)
                ? IMPACT_STYLE[value]
                : "border-line text-ink/40 hover:text-ink/70"
            )}
            key={value}
            onClick={() => toggleImpact(value)}
            type="button"
          >
            {value}
          </button>
        ))}
        {currencies.length > 0 && <span className="mx-1 h-4 w-px bg-line" />}
        {currencies.map((code) => (
          <button
            className={cn(
              "rounded-md border px-2 py-1 font-mono text-xs",
              currency === code
                ? "border-signal bg-signal/10 text-signal"
                : "border-line text-ink/50 hover:text-ink"
            )}
            key={code}
            onClick={() => setCurrency(currency === code ? null : code)}
            type="button"
          >
            {code}
          </button>
        ))}
      </div>

      {error && (
        <Card className="border-loss/30 bg-loss/5">
          <CardContent className="p-3 text-sm text-ink/70">{error}</CardContent>
        </Card>
      )}

      {loading && !feed ? (
        <div className="space-y-2">
          {[0, 1, 2].map((index) => (
            <div className="h-12 animate-pulse rounded-lg bg-ink/10" key={index} />
          ))}
        </div>
      ) : !feed?.available ? (
        <Card>
          <CardContent className="p-4 text-sm text-ink/55">
            {feed?.reason ?? "The economic calendar is unavailable."}
          </CardContent>
        </Card>
      ) : grouped.length === 0 ? (
        <Card>
          <CardContent className="p-4 text-sm text-ink/55">
            No events match the selected filters.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-5">
          {grouped.map(([key, events]) => (
            <section key={key}>
              <h2 className="mb-2 text-sm font-semibold text-ink">
                {formatDayHeading(key)}
              </h2>
              <Card>
                <CardContent className="divide-y divide-line p-0">
                  {events.map((event, index) => (
                    <EventRow
                      event={event}
                      key={`${event.title}-${event.dateLabel}-${index}`}
                      now={now}
                      strengthByCurrency={strengthByCurrency}
                    />
                  ))}
                </CardContent>
              </Card>
            </section>
          ))}
        </div>
      )}

      <p className="text-[11px] text-ink/40">
        Source: ForexFactory weekly feed. Only the current week is published, and
        &quot;forecast&quot; is the market consensus, not a Quant Labs estimate.
      </p>
    </div>
  );
}

function EventRow({
  event,
  now,
  strengthByCurrency
}: {
  event: CalendarEvent;
  now: Date;
  strengthByCurrency: Record<string, number>;
}) {
  const context = eventContext(event, strengthByCurrency);
  const scheduled = event.scheduledAt ? new Date(event.scheduledAt) : null;
  const isPast = scheduled ? scheduled < now : false;
  // Highlight the next hour of high-impact risk — the window worth planning around.
  const imminent =
    scheduled && !isPast && scheduled.getTime() - now.getTime() < 3_600_000;

  return (
    <div
      className={cn(
        "flex items-start gap-3 px-4 py-2.5",
        isPast && "opacity-55",
        imminent && event.impact === "high" && "bg-loss/5"
      )}
    >
      <span className="w-14 shrink-0 pt-0.5 font-mono text-xs text-ink/60">
        {formatTime(event)}
      </span>
      <span className="w-10 shrink-0 pt-0.5 font-mono text-xs font-semibold text-ink/70">
        {event.currency}
      </span>
      <span
        className={cn(
          "mt-0.5 shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase",
          IMPACT_STYLE[event.impact]
        )}
      >
        {event.impact}
      </span>

      <div className="min-w-0 flex-1">
        <p className="text-sm leading-snug text-ink">
          {event.title}
          {imminent && event.impact === "high" && (
            <span className="ml-2 text-[10px] font-semibold uppercase text-loss">
              within the hour
            </span>
          )}
        </p>
        {context.length > 0 && (
          <p className="mt-0.5 text-[11px] leading-relaxed text-ink/55">
            {context.join(" ")}
          </p>
        )}
        {(event.forecast || event.previous || event.actual) && (
          <p className="mt-0.5 flex flex-wrap gap-x-3 text-[11px] text-ink/50">
            {event.actual && (
              <span>
                actual <span className="font-mono text-ink/80">{event.actual}</span>
              </span>
            )}
            {event.forecast && (
              <span>
                consensus <span className="font-mono text-ink/70">{event.forecast}</span>
              </span>
            )}
            {event.previous && (
              <span>
                previous <span className="font-mono text-ink/70">{event.previous}</span>
              </span>
            )}
          </p>
        )}
      </div>

      {event.tentative && (
        <AlertTriangle
          aria-label="Tentative timing"
          className="mt-0.5 shrink-0 text-caution"
          size={13}
          strokeWidth={2.2}
        />
      )}
      {event.url && (
        <a
          className="mt-0.5 shrink-0 text-ink/30 hover:text-ink"
          href={event.url}
          rel="noopener noreferrer"
          target="_blank"
          title="Open on ForexFactory"
        >
          <ExternalLink aria-hidden="true" size={13} strokeWidth={2.2} />
        </a>
      )}
    </div>
  );
}
