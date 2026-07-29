// Daily desk report client for `/api/v1/desk/reports*`.

const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }
  });
  if (!response.ok) {
    throw new Error(`API ${init?.method ?? "GET"} ${path} failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export type GradedCall = {
  symbol: string;
  direction: string;
  confidence: number;
  called_at: string;
  verdict: "correct" | "incorrect" | "flat" | "ungradable" | string;
  detail: string;
};

export type ReportInstrument = {
  symbol: string;
  direction: string;
  confidence: number;
  change_percent: number;
  explanation: string;
  price_basis: string;
  proxy_note: string | null;
};

export type ReportEvent = {
  title: string;
  currency: string;
  impact: string;
  scheduled_at: string | null;
  forecast: string | null;
  previous: string | null;
};

export type ReportPayload = {
  graded_calls: GradedCall[];
  instruments: ReportInstrument[];
  events: ReportEvent[];
  strength: Array<{ currency: string; score: number; pairs: number }>;
  sessions: Array<{
    label: string;
    phase_label: string;
    next_phase_label: string;
    countdown: string;
  }>;
  unavailable: Record<string, string>;
  caveats: string[];
  assets_analyzed: number;
};

export type DeskReport = {
  id: string;
  reportDate: string;
  title: string;
  payload: ReportPayload;
  readAt: string | null;
  createdAt: string;
};

export type DeskReportSummary = {
  id: string;
  reportDate: string;
  title: string;
  readAt: string | null;
  createdAt: string;
  assetsAnalyzed: number;
  highImpactEvents: number;
};

type ReportDto = {
  id: string;
  report_date: string;
  title: string;
  payload: ReportPayload;
  read_at: string | null;
  created_at: string;
};

function reportFromDto(dto: ReportDto): DeskReport {
  return {
    id: dto.id,
    reportDate: dto.report_date,
    title: dto.title,
    payload: dto.payload,
    readAt: dto.read_at,
    createdAt: dto.created_at
  };
}

/** Today's report; the server generates it on the first call of the day. */
export async function generateTodayReport(): Promise<DeskReport> {
  return reportFromDto(
    await json<ReportDto>("/api/v1/desk/reports/generate", { method: "POST" })
  );
}

export async function listReports(): Promise<DeskReportSummary[]> {
  const rows = await json<
    Array<{
      id: string;
      report_date: string;
      title: string;
      read_at: string | null;
      created_at: string;
      assets_analyzed: number;
      high_impact_events: number;
    }>
  >("/api/v1/desk/reports");
  return rows.map((row) => ({
    id: row.id,
    reportDate: row.report_date,
    title: row.title,
    readAt: row.read_at,
    createdAt: row.created_at,
    assetsAnalyzed: row.assets_analyzed,
    highImpactEvents: row.high_impact_events
  }));
}

export async function getReport(id: string): Promise<DeskReport> {
  return reportFromDto(await json<ReportDto>(`/api/v1/desk/reports/${id}`));
}

export async function markReportRead(id: string): Promise<DeskReport> {
  return reportFromDto(
    await json<ReportDto>(`/api/v1/desk/reports/${id}/read`, { method: "PATCH" })
  );
}
