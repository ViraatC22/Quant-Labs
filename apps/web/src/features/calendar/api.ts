// Economic calendar client for `/api/v1/desk/calendar`.

const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type CalendarImpact = "high" | "medium" | "low" | "holiday" | "unknown";

export type CalendarEvent = {
  title: string;
  currency: string;
  impact: CalendarImpact;
  /** Null for all-day and tentative events, which have a date but no time. */
  scheduledAt: string | null;
  dateLabel: string;
  allDay: boolean;
  tentative: boolean;
  forecast: string | null;
  previous: string | null;
  actual: string | null;
  url: string | null;
};

export type CalendarFeed = {
  events: CalendarEvent[];
  available: boolean;
  stale: boolean;
  reason: string | null;
  source: string;
  nowUtc: string;
};

type CalendarDto = {
  events: Array<{
    title: string;
    currency: string;
    impact: string;
    scheduled_at: string | null;
    date_label: string;
    all_day: boolean;
    tentative: boolean;
    forecast: string | null;
    previous: string | null;
    actual: string | null;
    url: string | null;
  }>;
  available: boolean;
  stale: boolean;
  reason: string | null;
  source: string;
  now_utc: string;
};

export async function fetchCalendar(options?: {
  impact?: string[];
  currencies?: string[];
}): Promise<CalendarFeed> {
  const params = new URLSearchParams();
  if (options?.impact?.length) params.set("impact", options.impact.join(","));
  if (options?.currencies?.length) params.set("currencies", options.currencies.join(","));
  const query = params.toString();

  const response = await fetch(
    `${apiBaseUrl}/api/v1/desk/calendar${query ? `?${query}` : ""}`,
    { headers: { "Content-Type": "application/json" } }
  );
  if (!response.ok) {
    throw new Error(`API GET /api/v1/desk/calendar failed: ${response.status}`);
  }
  const dto = (await response.json()) as CalendarDto;
  return {
    events: dto.events.map((event) => ({
      title: event.title,
      currency: event.currency,
      impact: event.impact as CalendarImpact,
      scheduledAt: event.scheduled_at,
      dateLabel: event.date_label,
      allDay: event.all_day,
      tentative: event.tentative,
      forecast: event.forecast,
      previous: event.previous,
      actual: event.actual,
      url: event.url
    })),
    available: dto.available,
    stale: dto.stale,
    reason: dto.reason,
    source: dto.source,
    nowUtc: dto.now_utc
  };
}
