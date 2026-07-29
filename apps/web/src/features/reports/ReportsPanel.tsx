"use client";

// Daily Reports: today's pre-market report plus the archive.
//
// The report is a stored record of what the desk said that morning, not a live
// regeneration — so the archive can be trusted as history. The graded-calls
// section is the honest version of "grading our predictions": verdicts were
// computed against stored prices at generation time, and calls that could not
// be graded say why instead of being scored.

import { CheckCheck, FileText, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import {
  generateTodayReport,
  getReport,
  listReports,
  markReportRead,
  type DeskReport,
  type DeskReportSummary,
  type GradedCall
} from "./api";

const VERDICT_STYLE: Record<string, string> = {
  correct: "border-moss/40 bg-moss/10 text-moss",
  incorrect: "border-loss/40 bg-loss/10 text-loss",
  flat: "border-line bg-ink/5 text-ink/55",
  ungradable: "border-caution/40 bg-caution/10 text-caution"
};

function formatReportDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00Z`);
  return date.toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone: "UTC"
  });
}

export function ReportsPanel() {
  const [report, setReport] = useState<DeskReport | null>(null);
  const [archive, setArchive] = useState<DeskReportSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      // Generating is idempotent: the first visit of the day creates the
      // report; later visits get the stored one.
      const today = await generateTodayReport();
      const summaries = await listReports();
      setError(null);
      setReport(today);
      setArchive(summaries);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Reports could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    async function run() {
      await load();
    }
    void run();
  }, [load]);

  async function openArchived(id: string) {
    try {
      setReport(await getReport(id));
      window.scrollTo({ top: 0 });
    } catch {
      // The row stays; a failed detail fetch is not worth a modal.
    }
  }

  async function markRead() {
    if (!report || report.readAt) return;
    const updated = await markReportRead(report.id);
    setReport(updated);
    setArchive((rows) =>
      rows.map((row) => (row.id === updated.id ? { ...row, readAt: updated.readAt } : row))
    );
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <FileText aria-hidden="true" className="text-ink/50" size={19} strokeWidth={2.2} />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-ink">Daily Reports</h1>
            <p className="text-sm text-ink/55">
              Your pre-market report, generated from the desk&apos;s own data.
            </p>
          </div>
        </div>
        <button
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
      </header>

      {error && (
        <Card className="border-loss/30 bg-loss/5">
          <CardContent className="p-3 text-sm text-ink/70">{error}</CardContent>
        </Card>
      )}

      {loading && !report ? (
        <div className="h-48 animate-pulse rounded-lg bg-ink/10" />
      ) : report ? (
        <ReportDetail onMarkRead={() => void markRead()} report={report} />
      ) : null}

      {archive.length > 1 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold text-ink">Archive</h2>
          <Card>
            <CardContent className="divide-y divide-line p-0">
              {archive
                .filter((row) => row.id !== report?.id)
                .map((row) => (
                  <button
                    className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-ink/5"
                    key={row.id}
                    onClick={() => void openArchived(row.id)}
                    type="button"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm text-ink">{row.title}</p>
                      <p className="text-xs text-ink/50">
                        {row.assetsAnalyzed} assets analyzed
                        {row.highImpactEvents
                          ? ` · ${row.highImpactEvents} high-impact events`
                          : ""}
                      </p>
                    </div>
                    {!row.readAt && <Badge variant="warning">Unread</Badge>}
                  </button>
                ))}
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  );
}

function ReportDetail({
  report,
  onMarkRead
}: {
  report: DeskReport;
  onMarkRead: () => void;
}) {
  const payload = report.payload;
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-ink/45">
              {formatReportDate(report.reportDate)}
            </p>
            <CardTitle className="mt-1 text-lg leading-snug">{report.title}</CardTitle>
            <p className="mt-1 text-xs text-ink/50">
              {payload.assets_analyzed} assets analyzed · generated{" "}
              {new Date(report.createdAt).toISOString().slice(11, 16)}Z
            </p>
          </div>
          <button
            className={cn(
              "flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm",
              report.readAt
                ? "border-line text-ink/40"
                : "border-signal text-signal hover:bg-signal/10"
            )}
            disabled={Boolean(report.readAt)}
            onClick={onMarkRead}
            type="button"
          >
            <CheckCheck aria-hidden="true" size={15} strokeWidth={2.2} />
            {report.readAt ? "Read" : "Mark as read"}
          </button>
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        {payload.graded_calls.length > 0 && (
          <section>
            <h3 className="mb-2 text-sm font-semibold text-ink">
              Grading the desk&apos;s previous calls
            </h3>
            <ul className="space-y-1.5">
              {payload.graded_calls.map((call) => (
                <GradedCallRow call={call} key={`${call.symbol}-${call.called_at}`} />
              ))}
            </ul>
          </section>
        )}

        <section>
          <h3 className="mb-2 text-sm font-semibold text-ink">Instrument outlooks</h3>
          <ul className="space-y-2.5">
            {payload.instruments.map((instrument) => (
              <li className="text-sm" key={instrument.symbol}>
                <p className="flex items-center gap-2">
                  <span className="font-mono text-xs font-semibold text-ink">
                    {instrument.symbol}
                  </span>
                  <span
                    className={cn(
                      "text-xs font-medium uppercase",
                      instrument.direction === "bullish"
                        ? "text-moss"
                        : instrument.direction === "bearish"
                          ? "text-loss"
                          : "text-ink/55"
                    )}
                  >
                    {instrument.direction}
                  </span>
                  <span className="text-[11px] text-ink/45">
                    {instrument.confidence}%
                  </span>
                </p>
                <p className="mt-0.5 text-xs leading-relaxed text-ink/65">
                  {instrument.explanation}
                </p>
              </li>
            ))}
          </ul>
        </section>

        {payload.events.length > 0 && (
          <section>
            <h3 className="mb-2 text-sm font-semibold text-ink">Events today</h3>
            <ul className="space-y-1.5 text-xs">
              {payload.events.map((event, index) => (
                <li className="flex items-baseline gap-2" key={`${event.title}-${index}`}>
                  <span className="w-12 shrink-0 font-mono text-ink/55">
                    {event.scheduled_at ? `${event.scheduled_at.slice(11, 16)}Z` : "—"}
                  </span>
                  <span className="w-9 shrink-0 font-mono font-semibold text-ink/70">
                    {event.currency}
                  </span>
                  <span
                    className={cn(
                      "shrink-0 rounded border px-1 py-0.5 text-[10px] uppercase",
                      event.impact === "high"
                        ? "border-loss/40 text-loss"
                        : "border-caution/40 text-caution"
                    )}
                  >
                    {event.impact}
                  </span>
                  <span className="text-ink/80">{event.title}</span>
                  {event.forecast && (
                    <span className="text-ink/45">consensus {event.forecast}</span>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        {payload.strength.length > 0 && (
          <section>
            <h3 className="mb-2 text-sm font-semibold text-ink">Currency strength</h3>
            <p className="flex flex-wrap gap-x-3 gap-y-1 font-mono text-xs">
              {payload.strength.map((item) => (
                <span
                  className={
                    item.score > 0
                      ? "text-moss"
                      : item.score < 0
                        ? "text-loss"
                        : "text-ink/50"
                  }
                  key={item.currency}
                >
                  {item.currency} {item.score > 0 ? "+" : ""}
                  {item.score.toFixed(3)}
                </span>
              ))}
            </p>
          </section>
        )}

        <ul className="space-y-1 border-t border-line pt-3 text-[11px] text-ink/50">
          {payload.caveats.map((caveat) => (
            <li key={caveat}>• {caveat}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function GradedCallRow({ call }: { call: GradedCall }) {
  return (
    <li className="flex items-start gap-2 text-xs">
      <span
        className={cn(
          "mt-0.5 shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase",
          VERDICT_STYLE[call.verdict] ?? VERDICT_STYLE.ungradable
        )}
      >
        {call.verdict}
      </span>
      <span className="font-mono font-semibold text-ink/80">{call.symbol}</span>
      <span className="text-ink/60">{call.detail}</span>
    </li>
  );
}
