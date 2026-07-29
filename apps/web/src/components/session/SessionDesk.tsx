"use client";

import {
  BarChart3,
  BookOpenCheck,
  BrainCircuit,
  CalendarClock,
  ChevronDown,
  CircleGauge,
  FileWarning,
  Newspaper,
  Radar,
  ShieldAlert,
  TimerReset
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import * as api from "@/lib/api";
import {
  coachingFindings,
  edgeFactor,
  macroSources,
  pnlByWeekday,
  tradeQualityCoverage
} from "@/lib/sessionDesk";
import type { JournalEntry, MarketContext, TradeEntry, VaultItem } from "@/lib/types";

type View = "brief" | "macro" | "calendar" | "instruments" | "journal" | "reports";
type Event = {
  id: string;
  time: string;
  currency: string;
  impact: "high" | "medium" | "low" | "unrated";
  title: string;
  source: string;
};
type SavedReport = {
  id: string;
  date: string;
  symbol: string;
  edgeScore: number;
  edgeLabel: string;
  eventCount: number;
  sourceCount: number;
  reviewFocus: string;
  read: boolean;
};

const eventsStorageKey = "quant-labs.session-desk.events.v1";
const reportsStorageKey = "quant-labs.session-desk.reports.v1";

const viewLabels: Array<{ key: View; label: string }> = [
  { key: "brief", label: "Session brief" },
  { key: "macro", label: "Macro desk" },
  { key: "calendar", label: "Calendar" },
  { key: "instruments", label: "Deep dives" },
  { key: "journal", label: "Coach" },
  { key: "reports", label: "Report" }
];

function money(value: number) {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0
  });
}

export function SessionDesk({
  trades,
  journal,
  vault,
  onOpenJournal,
  onOpenTrades,
  onOpenResearch
}: {
  trades: TradeEntry[];
  journal: JournalEntry[];
  vault: VaultItem[];
  onOpenJournal: () => void;
  onOpenTrades: () => void;
  onOpenResearch: () => void;
}) {
  const [view, setView] = useState<View>("brief");
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [events, setEvents] = useState<Event[]>([]);
  const [eventTitle, setEventTitle] = useState("");
  const [eventTime, setEventTime] = useState("");
  const [eventCurrency, setEventCurrency] = useState("USD");
  const [eventImpact, setEventImpact] = useState<Event["impact"]>("high");
  const [eventSource, setEventSource] = useState("");
  const [showMethod, setShowMethod] = useState(false);
  const [marketContext, setMarketContext] = useState<MarketContext | null>(null);
  const [marketContextState, setMarketContextState] = useState<"idle" | "loading" | "ready" | "unavailable">("idle");
  const [savedReports, setSavedReports] = useState<SavedReport[]>([]);
  const [storageReady, setStorageReady] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const symbols = useMemo(
    () => [...new Set(trades.map((trade) => trade.symbol.toUpperCase()))].sort(),
    [trades]
  );
  const selectedTrades = useMemo(
    () => trades.filter((trade) => !selectedSymbol || trade.symbol.toUpperCase() === selectedSymbol),
    [trades, selectedSymbol]
  );
  const edge = useMemo(
    () => edgeFactor(trades, selectedSymbol || undefined),
    [trades, selectedSymbol]
  );
  const coach = useMemo(() => coachingFindings(trades, journal), [trades, journal]);
  const sources = useMemo(() => macroSources(vault), [vault]);
  const weekday = useMemo(() => pnlByWeekday(selectedTrades), [selectedTrades]);
  const quality = useMemo(() => tradeQualityCoverage(selectedTrades), [selectedTrades]);
  const closed = selectedTrades.filter((trade) => trade.exitPrice !== null);
  const pnl = closed.reduce((sum, trade) => {
    const direction = trade.side === "short" ? -1 : 1;
    return (
      sum +
      ((Number(trade.exitPrice) - trade.entryPrice) *
        trade.quantity *
        (trade.contractMultiplier || (trade.assetClass === "option" ? 100 : 1)) *
        direction -
        trade.fees)
    );
  }, 0);
  const wins = closed.filter((trade) => {
    const direction = trade.side === "short" ? -1 : 1;
    return (Number(trade.exitPrice) - trade.entryPrice) * direction > 0;
  }).length;
  const latestJournal = journal.slice().sort((a, b) => b.date.localeCompare(a.date))[0];

  useEffect(() => {
    const timer = window.setTimeout(() => {
      try {
        setEvents(JSON.parse(window.localStorage.getItem(eventsStorageKey) || "[]") as Event[]);
        setSavedReports(
          JSON.parse(window.localStorage.getItem(reportsStorageKey) || "[]") as SavedReport[]
        );
      } catch {
        setEvents([]);
        setSavedReports([]);
      }
      setStorageReady(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!storageReady) return;
    window.localStorage.setItem(eventsStorageKey, JSON.stringify(events));
  }, [events, storageReady]);

  useEffect(() => {
    if (!storageReady) return;
    window.localStorage.setItem(reportsStorageKey, JSON.stringify(savedReports));
  }, [savedReports, storageReady]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!selectedSymbol) return;
    void api
      .getMarketContext(selectedSymbol)
      .then((context) => {
        if (cancelled) return;
        setMarketContext(context);
        setMarketContextState("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setMarketContext(null);
        setMarketContextState("unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, [selectedSymbol]);

  return (
    <section
      aria-labelledby="desk-tab"
      className="overflow-hidden rounded-xl border border-line bg-card/90 shadow-panel"
      id="desk-panel"
      role="tabpanel"
    >
      <header className="border-b border-line bg-gradient-to-r from-signal/10 via-card to-moss/10 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Radar className="text-signal" size={20} />
              <Badge variant="outline">Evidence-aware</Badge>
              <Badge variant="secondary">Decision support, not signals</Badge>
            </div>
            <h2 className="mt-3 text-2xl font-semibold text-ink">Session Desk</h2>
            <p className="mt-1 max-w-2xl text-sm text-ink/58">
              Prepare, execute, and review from your own recorded evidence. Missing live feeds are
              shown as missing—never filled with invented market context.
            </p>
          </div>
          <label className="text-xs font-medium text-ink/55">
            Instrument context
            <select
              className="mt-1 block min-h-9 min-w-48 rounded-md border border-line bg-card px-3 text-sm text-ink"
              onChange={(event) => {
                const symbol = event.target.value;
                setSelectedSymbol(symbol);
                if (!symbol) {
                  setMarketContext(null);
                  setMarketContextState("idle");
                } else {
                  setMarketContext(null);
                  setMarketContextState("loading");
                }
              }}
              value={selectedSymbol}
            >
              <option value="">All instruments</option>
              {symbols.map((symbol) => (
                <option key={symbol}>{symbol}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="mt-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <SessionClock label="London" now={now} timeZone="Europe/London" />
          <SessionClock label="New York" now={now} timeZone="America/New_York" />
          <SessionClock label="Sydney" now={now} timeZone="Australia/Sydney" />
          <SessionClock label="Tokyo" now={now} timeZone="Asia/Tokyo" />
        </div>
        <nav aria-label="Session Desk modules" className="mt-5 flex gap-1 overflow-x-auto">
          {viewLabels.map((item) => (
            <button
              className={[
                "shrink-0 rounded-md px-3 py-2 text-sm font-medium transition",
                view === item.key ? "bg-ink text-paper" : "text-ink/58 hover:bg-ink/5 hover:text-ink"
              ].join(" ")}
              key={item.key}
              onClick={() => setView(item.key)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </nav>
      </header>

      <div className="p-5">
        {view === "brief" && (
          <div className="grid gap-4 xl:grid-cols-[1.25fr_.75fr]">
            <article className="rounded-lg border border-line p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[.14em] text-signal">
                    Pre-session brief
                  </p>
                  <h3 className="mt-1 text-lg font-semibold text-ink">
                    {selectedSymbol || "Portfolio"} decision context
                  </h3>
                </div>
                <CircleGauge className="text-signal" />
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <BriefItem
                  label="Evidence posture"
                  text={
                    edge.label === "Insufficient evidence"
                      ? "Observe or paper-trade; the sample cannot support a setup score."
                      : `${edge.label}. Recorded conditions score ${edge.score}/100.`
                  }
                />
                <BriefItem
                  label="Event risk"
                  text={
                    events.length
                      ? `${events.length} manually confirmed catalyst${events.length === 1 ? "" : "s"} on deck.`
                      : "Unknown—no economic-calendar provider is connected."
                  }
                />
                <BriefItem
                  label="Journal state"
                  text={
                    latestJournal
                      ? `Latest check-in: ${latestJournal.emotion}; routine ${latestJournal.routineDone ? "complete" : "not confirmed"}.`
                      : "No pre-session journal check-in recorded."
                  }
                />
                <BriefItem
                  label="Macro context"
                  text={
                    sources.length
                      ? `${sources.length} potentially relevant saved sources; open Macro Desk to inspect provenance.`
                      : "Unknown—no relevant saved macro source or live news feed."
                  }
                />
                <BriefItem
                  label="Observed structure"
                  text={
                    marketContext
                      ? `${marketContext.bearing}; ${marketContext.pulse} volatility; ${marketContext.flow} participation (${marketContext.interval}, delayed).`
                      : selectedSymbol
                        ? marketContextState === "loading"
                          ? "Calculating from delayed hourly bars…"
                          : "Unavailable—historical price bars could not be retrieved."
                        : "Choose an instrument to calculate technical context."
                  }
                />
              </div>
              <div className="mt-5 flex flex-wrap gap-2">
                <Button onClick={onOpenJournal} type="button">
                  <BookOpenCheck size={16} /> Journal prep
                </Button>
                <Button onClick={onOpenTrades} type="button" variant="outline">
                  Open paper ticket
                </Button>
              </div>
            </article>
            <EdgeCard edge={edge} showMethod={showMethod} onToggle={() => setShowMethod(!showMethod)} />
          </div>
        )}

        {view === "macro" && (
          <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
            <article className="rounded-lg border border-line p-5">
              <div className="flex items-start gap-3">
                <Newspaper className="mt-0.5 text-signal" />
                <div>
                  <h3 className="font-semibold text-ink">Grounded macro narratives</h3>
                  <p className="mt-1 text-sm text-ink/55">
                    These are saved research records, not a claim of live market coverage.
                  </p>
                </div>
              </div>
              <div className="mt-4 divide-y divide-line">
                {sources.map((source) => (
                  <article className="py-4" key={source.id}>
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="font-medium text-ink">{source.title}</h4>
                      <Badge variant="outline">{source.kind}</Badge>
                    </div>
                    <p className="mt-1 line-clamp-3 text-sm leading-6 text-ink/60">{source.body}</p>
                    <p className="mt-2 text-xs text-ink/40">Source: {source.source || "user record"}</p>
                  </article>
                ))}
                {!sources.length && (
                  <EmptyEvidence text="No macro evidence is saved. Add current central-bank, rates, inflation, currency, or cross-asset research before asking the system to explain a move." />
                )}
              </div>
            </article>
            <div className="space-y-4">
              <MarketRegimeCard context={marketContext} state={marketContextState} symbol={selectedSymbol} />
              <aside className="rounded-lg border border-line bg-ink/[.025] p-5">
                <ShieldAlert className="text-caution" />
                <h3 className="mt-3 font-semibold text-ink">Reality check</h3>
                <p className="mt-2 text-sm leading-6 text-ink/60">
                  A language model cannot know why price moved from price alone. A defensible
                  explanation needs time-stamped news, economic releases, rates, positioning, and
                  price data. QuantLab retrieves and summarizes configured evidence; it does not
                  manufacture the missing causal chain.
                </p>
                <Button className="mt-4" onClick={onOpenResearch} type="button" variant="outline">
                  Open grounded research
                </Button>
              </aside>
            </div>
          </div>
        )}

        {view === "calendar" && (
          <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
            <form
              className="rounded-lg border border-line p-5"
              onSubmit={(submitEvent) => {
                submitEvent.preventDefault();
                if (!eventTitle.trim() || !eventTime) return;
                setEvents((current) => [
                  ...current,
                  {
                    id: crypto.randomUUID(),
                    time: eventTime,
                    currency: eventCurrency,
                    impact: eventImpact,
                    title: eventTitle.trim(),
                    source: eventSource.trim() || "Manually confirmed"
                  }
                ]);
                setEventTitle("");
                setEventTime("");
                setEventSource("");
              }}
            >
              <h3 className="font-semibold text-ink">Confirm a catalyst</h3>
              <p className="mt-1 text-sm text-ink/50">
                Manual events are local session-planning context, not a live calendar.
              </p>
              <label className="mt-4 block text-xs text-ink/55">
                Event
                <input
                  className="mt-1 min-h-10 w-full rounded-md border border-line bg-card px-3 text-sm text-ink"
                  onChange={(event) => setEventTitle(event.target.value)}
                  placeholder="e.g. US CPI release"
                  value={eventTitle}
                />
              </label>
              <label className="mt-3 block text-xs text-ink/55">
                Time
                <input
                  className="mt-1 min-h-10 w-full rounded-md border border-line bg-card px-3 text-sm text-ink"
                  onChange={(event) => setEventTime(event.target.value)}
                  type="datetime-local"
                  value={eventTime}
                />
              </label>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <label className="block text-xs text-ink/55">
                  Currency
                  <select
                    className="mt-1 min-h-10 w-full rounded-md border border-line bg-card px-3 text-sm text-ink"
                    onChange={(event) => setEventCurrency(event.target.value)}
                    value={eventCurrency}
                  >
                    {["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "CNY", "ALL"].map((currency) => (
                      <option key={currency}>{currency}</option>
                    ))}
                  </select>
                </label>
                <label className="block text-xs text-ink/55">
                  Impact
                  <select
                    className="mt-1 min-h-10 w-full rounded-md border border-line bg-card px-3 text-sm text-ink"
                    onChange={(event) => setEventImpact(event.target.value as Event["impact"])}
                    value={eventImpact}
                  >
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                    <option value="unrated">Unrated</option>
                  </select>
                </label>
              </div>
              <label className="mt-3 block text-xs text-ink/55">
                Verification source
                <input
                  className="mt-1 min-h-10 w-full rounded-md border border-line bg-card px-3 text-sm text-ink"
                  onChange={(event) => setEventSource(event.target.value)}
                  placeholder="URL, calendar, or release name"
                  value={eventSource}
                />
              </label>
              <Button className="mt-4" type="submit">
                <CalendarClock size={16} /> Add confirmed event
              </Button>
            </form>
            <article className="rounded-lg border border-line p-5">
              <h3 className="font-semibold text-ink">Catalyst timeline</h3>
              <div className="mt-4 divide-y divide-line">
                {events.map((event) => (
                  <div className="flex items-center gap-4 py-3" key={event.id}>
                    <time className="w-44 shrink-0 text-sm font-medium text-ink">
                      {new Date(event.time).toLocaleString()}
                    </time>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-ink">{event.title}</p>
                      <p className="text-xs text-ink/45">
                        {event.currency} · {event.impact} · {event.source}
                      </p>
                    </div>
                    <button
                      className="text-xs text-loss"
                      onClick={() => setEvents((current) => current.filter((item) => item.id !== event.id))}
                      type="button"
                    >
                      Remove
                    </button>
                  </div>
                ))}
                {!events.length && (
                  <EmptyEvidence text="No confirmed catalysts. Connect a licensed calendar source in a future adapter or add events you have independently verified." />
                )}
              </div>
            </article>
          </div>
        )}

        {view === "instruments" && (
          <div className="grid gap-4 lg:grid-cols-3">
            <Metric label="Closed trades" value={String(closed.length)} />
            <Metric label="Recorded win rate" value={closed.length ? `${Math.round((wins / closed.length) * 100)}%` : "—"} />
            <Metric label="Realized P&L" value={closed.length ? money(pnl) : "—"} tone={pnl < 0 ? "bad" : "good"} />
            {marketContext && (
              <>
                <Metric label="Observed flow" value={marketContext.flow} />
                <Metric label="Observed bearing" value={marketContext.bearing} />
                <Metric label="Observed pulse" value={marketContext.pulse} />
              </>
            )}
            <article className="rounded-lg border border-line p-5 lg:col-span-2">
              <h3 className="font-semibold text-ink">Instrument deep dive</h3>
              <p className="mt-2 text-sm leading-6 text-ink/58">
                This view combines your execution history with delayed, time-stamped hourly bars.
                Flow is volume percentile, Bearing is 12-bar direction plus path efficiency, and
                Pulse is the percentile of current 14-bar ATR versus its lookback.
              </p>
              {marketContext ? (
                <>
                  <div className="mt-4 grid gap-2 sm:grid-cols-2">
                    <BriefItem label={`RSI (14) · ${marketContext.rsi_14 ?? "—"}`} text="Momentum oscillator over the latest 14 hourly closes." />
                    <BriefItem label={`ATR · ${marketContext.atr_percent ?? "—"}%`} text="Latest 14-bar average true range as a percent of price." />
                    <BriefItem label={`Bollinger width · ${marketContext.bollinger_width_percent ?? "—"}%`} text="Four standard deviations over the 20-bar mean." />
                    <BriefItem label={`Volume percentile · ${marketContext.volume_percentile ?? "—"}`} text={marketContext.volume_percentile === null || marketContext.volume_percentile === undefined ? "Reliable volume is unavailable for this instrument." : "Latest volume ranked against the hourly lookback."} />
                    <BriefItem label={`Trend efficiency · ${marketContext.trend_efficiency ?? "—"}`} text="Net 12-bar move divided by total path; lower values mean choppier movement." />
                    <BriefItem label={`Data confidence · ${Math.round(marketContext.confidence * 100)}%`} text={`${marketContext.sample_size} ${marketContext.interval} bars from ${marketContext.provider}; as of ${new Date(marketContext.as_of).toLocaleString()}.`} />
                  </div>
                  <ul className="mt-4 space-y-1 text-xs text-ink/45">
                    {marketContext.limitations.map((limitation) => (
                      <li key={limitation}>• {limitation}</li>
                    ))}
                  </ul>
                </>
              ) : (
                <EmptyEvidence
                  text={
                    selectedSymbol
                      ? marketContextState === "loading"
                        ? "Calculating technical context from historical bars…"
                        : "Historical bars are unavailable for this symbol."
                      : "Choose an instrument above to calculate technical context."
                  }
                />
              )}
            </article>
            <article className="rounded-lg border border-line p-5">
              <h3 className="font-semibold text-ink">Setup context</h3>
              <p className="mt-2 text-sm text-ink/55">
                {edge.label === "Supported"
                  ? "Your recorded sample supports further paper evaluation under the same conditions."
                  : "Conditions do not justify increased confidence. Preserve capital and collect a cleaner sample."}
              </p>
              <div className="mt-4 space-y-2">
                {edge.components.map((component) => (
                  <div className="text-xs" key={component.label}>
                    <div className="flex justify-between gap-3">
                      <span className="text-ink/55">{component.label}</span>
                      <strong>{component.score}</strong>
                    </div>
                    <div className="mt-1 h-1 rounded-full bg-ink/10">
                      <div className="h-1 rounded-full bg-signal" style={{ width: `${component.score}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </article>
          </div>
        )}

        {view === "journal" && (
          <div>
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="font-semibold text-ink">Behavioral coaching loop</h3>
                <p className="mt-1 text-sm text-ink/50">
                  Deterministic comparisons over your own trades; no causal or predictive claim.
                </p>
              </div>
              <BrainCircuit className="text-signal" />
            </div>
            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              {coach.map((finding) => (
                <article className="rounded-lg border border-line p-4" key={finding.title}>
                  <Badge
                    variant={
                      finding.tone === "positive"
                        ? "success"
                        : finding.tone === "caution"
                          ? "warning"
                          : "secondary"
                    }
                  >
                    {finding.tone}
                  </Badge>
                  <h4 className="mt-3 font-semibold text-ink">{finding.title}</h4>
                  <p className="mt-2 text-sm leading-6 text-ink/62">{finding.finding}</p>
                  <p className="mt-3 text-xs leading-5 text-ink/42">{finding.evidence}</p>
                </article>
              ))}
            </div>
            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <article className="rounded-lg border border-line p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-semibold text-ink">P&amp;L by weekday</h4>
                    <p className="mt-1 text-xs text-ink/45">Recorded outcomes; timezone follows saved trade dates.</p>
                  </div>
                  <BarChart3 className="text-signal" size={18} />
                </div>
                <div className="mt-5 flex h-44 items-end gap-2">
                  {weekday.map((row) => {
                    const max = Math.max(...weekday.map((item) => Math.abs(item.pnl)), 1);
                    const height = row.count ? Math.max(8, (Math.abs(row.pnl) / max) * 120) : 3;
                    return (
                      <div className="flex flex-1 flex-col items-center gap-2" key={row.day}>
                        <span className="text-[10px] text-ink/45">{row.count ? money(row.pnl) : "—"}</span>
                        <div
                          className={`w-full max-w-10 rounded-t ${row.pnl < 0 ? "bg-loss/70" : "bg-moss/70"}`}
                          style={{ height }}
                          title={`${row.day}: ${row.count} trades, ${money(row.pnl)}`}
                        />
                        <span className="text-xs text-ink/55">{row.day}</span>
                      </div>
                    );
                  })}
                </div>
              </article>
              <article className="rounded-lg border border-line p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h4 className="font-semibold text-ink">Trade-record coverage</h4>
                    <p className="mt-1 text-xs text-ink/45">
                      {quality.overall}/100 completeness heuristic—not a grade of trading skill.
                    </p>
                  </div>
                  <CircleGauge className="text-signal" size={18} />
                </div>
                <div className="mt-4 space-y-3">
                  {quality.axes.map((axis) => (
                    <div key={axis.label}>
                      <div className="flex items-center justify-between gap-3 text-xs">
                        <span className="text-ink/58">{axis.label}</span>
                        <strong className="text-ink">{axis.score}</strong>
                      </div>
                      <div className="mt-1 h-1.5 rounded-full bg-ink/10">
                        <div className="h-1.5 rounded-full bg-signal" style={{ width: `${axis.score}%` }} />
                      </div>
                      <p className="mt-1 text-[10px] text-ink/38">{axis.evidence}</p>
                    </div>
                  ))}
                </div>
              </article>
            </div>
            <Button className="mt-4" onClick={onOpenJournal} type="button">
              Capture decision context
            </Button>
          </div>
        )}

        {view === "reports" && (
          <div className="space-y-4">
          <article className="rounded-lg border border-line p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[.14em] text-signal">
                  Daily desk report
                </p>
                <h3 className="mt-1 text-xl font-semibold text-ink">
                  {new Date().toLocaleDateString(undefined, { dateStyle: "full" })}
                </h3>
              </div>
              <BarChart3 className="text-signal" />
            </div>
            <div className="mt-5 grid gap-3 md:grid-cols-2">
              <BriefItem label="Market evidence" text={`${sources.length} saved macro-relevant sources available for grounded retrieval.`} />
              <BriefItem label="Execution evidence" text={`${closed.length} comparable closed trades; ${edge.label.toLowerCase()} (${edge.score}/100).`} />
              <BriefItem label="Event posture" text={events.length ? `${events.length} manually confirmed events.` : "Calendar risk unknown; no provider or confirmed events."} />
              <BriefItem label="Review focus" text={coach[0]?.finding || "Log more closed trades before behavioral review."} />
            </div>
            <div className="mt-5 rounded-md border border-caution/25 bg-caution/5 p-3 text-xs leading-5 text-ink/58">
              Generated from the records currently visible to QuantLab. It is a reproducible
              workspace summary, not financial advice, a price forecast, or proof of market cause.
            </div>
            <Button
              className="mt-4"
              onClick={() => {
                const today = new Date().toISOString().slice(0, 10);
                const report: SavedReport = {
                  id: `${today}:${selectedSymbol || "portfolio"}`,
                  date: today,
                  symbol: selectedSymbol || "Portfolio",
                  edgeScore: edge.score,
                  edgeLabel: edge.label,
                  eventCount: events.length,
                  sourceCount: sources.length,
                  reviewFocus: coach[0]?.finding || "More evidence required.",
                  read: false
                };
                setSavedReports((current) => [
                  report,
                  ...current.filter((item) => item.id !== report.id)
                ].slice(0, 60));
              }}
              type="button"
              variant="outline"
            >
              Save report snapshot
            </Button>
          </article>
          <article className="rounded-lg border border-line p-5">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-ink">Reports archive</h3>
                <p className="mt-1 text-xs text-ink/45">Device-local, point-in-time snapshots.</p>
              </div>
              <Badge variant="secondary">{savedReports.length}</Badge>
            </div>
            <div className="mt-4 divide-y divide-line">
              {savedReports.map((report) => (
                <div className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center" key={report.id}>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium text-ink">{report.date} · {report.symbol}</p>
                      {!report.read && <Badge variant="warning">Unread</Badge>}
                    </div>
                    <p className="mt-1 text-xs text-ink/48">
                      Edge {report.edgeScore}/100 ({report.edgeLabel}) · {report.sourceCount} sources · {report.eventCount} events
                    </p>
                    <p className="mt-1 truncate text-xs text-ink/42">{report.reviewFocus}</p>
                  </div>
                  <button
                    className="shrink-0 text-xs font-medium text-signal"
                    onClick={() =>
                      setSavedReports((current) =>
                        current.map((item) =>
                          item.id === report.id ? { ...item, read: !item.read } : item
                        )
                      )
                    }
                    type="button"
                  >
                    Mark {report.read ? "unread" : "read"}
                  </button>
                </div>
              ))}
              {!savedReports.length && <EmptyEvidence text="No saved report snapshots yet." />}
            </div>
          </article>
          </div>
        )}
      </div>
    </section>
  );
}

function SessionClock({
  label,
  now,
  timeZone
}: {
  label: string;
  now: Date;
  timeZone: string;
}) {
  const parts = new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone
  }).formatToParts(now);
  const hour = Number(parts.find((part) => part.type === "hour")?.value || 0);
  const openHour = label === "London" ? 8 : label === "New York" ? 9 : label === "Sydney" ? 10 : 9;
  const closeHour = label === "London" ? 16 : label === "New York" ? 16 : label === "Sydney" ? 16 : 15;
  const open = hour >= openHour && hour < closeHour;
  const time = new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    timeZone
  }).format(now);
  return (
    <div className="flex items-center justify-between rounded-md border border-line bg-card/70 px-3 py-2">
      <div className="flex items-center gap-2">
        <span className={`h-1.5 w-1.5 rounded-full ${open ? "bg-moss" : "bg-ink/20"}`} />
        <div>
          <p className="text-xs font-semibold text-ink">{label}</p>
          <p className="text-[10px] uppercase tracking-wide text-ink/38">{open ? "Open" : "Closed"}</p>
        </div>
      </div>
      <time className="text-xs font-medium tabular-nums text-ink/55">{time}</time>
    </div>
  );
}

function MarketRegimeCard({
  context,
  state,
  symbol
}: {
  context: MarketContext | null;
  state: "idle" | "loading" | "ready" | "unavailable";
  symbol: string;
}) {
  return (
    <article className="rounded-lg border border-line bg-ink/[.025] p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[.12em] text-ink/42">
            Observed regime
          </p>
          <h3 className="mt-1 font-semibold text-ink">{symbol || "Choose an instrument"}</h3>
        </div>
        <TimerReset className="text-signal" size={19} />
      </div>
      {context ? (
        <>
          <div className="mt-4 grid grid-cols-3 gap-2 text-center">
            <RegimeMetric label="Flow" value={context.flow} />
            <RegimeMetric label="Bearing" value={context.bearing} />
            <RegimeMetric label="Pulse" value={context.pulse} />
          </div>
          <p className="mt-3 text-xs leading-5 text-ink/45">
            {context.sample_size} {context.stale ? "stale cached" : "delayed"} {context.interval} bars · {Math.round(context.confidence * 100)}% data coverage · {new Date(context.as_of).toLocaleString()}
          </p>
        </>
      ) : (
        <p className="mt-3 text-sm leading-6 text-ink/50">
          {!symbol
            ? "Select a traded instrument to calculate participation, direction, and volatility."
            : state === "loading"
              ? "Calculating observed regime…"
              : "Observed regime is unavailable from the configured data adapter."}
        </p>
      )}
    </article>
  );
}

function RegimeMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-card p-2">
      <p className="text-[10px] uppercase tracking-wide text-ink/38">{label}</p>
      <p className="mt-1 truncate text-xs font-semibold capitalize text-ink" title={value}>{value}</p>
    </div>
  );
}

function BriefItem({ label, text }: { label: string; text: string }) {
  return (
    <div className="rounded-md border border-line bg-ink/[.025] p-3">
      <p className="text-xs font-semibold uppercase tracking-[.1em] text-ink/42">{label}</p>
      <p className="mt-1.5 text-sm leading-6 text-ink/66">{text}</p>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" }) {
  return (
    <article className="rounded-lg border border-line p-5">
      <p className="text-xs uppercase tracking-[.12em] text-ink/42">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${tone === "bad" ? "text-loss" : tone === "good" ? "text-moss" : "text-ink"}`}>
        {value}
      </p>
    </article>
  );
}

function EmptyEvidence({ text }: { text: string }) {
  return (
    <div className="my-5 rounded-lg border border-dashed border-line p-6 text-center">
      <FileWarning className="mx-auto text-caution" />
      <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-ink/55">{text}</p>
    </div>
  );
}

function EdgeCard({
  edge,
  showMethod,
  onToggle
}: {
  edge: ReturnType<typeof edgeFactor>;
  showMethod: boolean;
  onToggle: () => void;
}) {
  return (
    <article className="rounded-lg border border-line bg-ink/[.025] p-5">
      <p className="text-xs font-semibold uppercase tracking-[.14em] text-ink/42">Edge Factor</p>
      <div className="mt-3 flex items-end gap-3">
        <span className="text-5xl font-semibold tabular-nums text-ink">{edge.score}</span>
        <span className="pb-1 text-sm text-ink/50">/ 100 · {edge.label}</span>
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-ink/10">
        <div className="h-full rounded-full bg-signal transition-all" style={{ width: `${edge.score}%` }} />
      </div>
      <p className="mt-3 text-sm text-ink/55">
        {edge.sample} comparable closed trades. A score of zero means evidence is insufficient,
        not that the setup is bad.
      </p>
      <button
        className="mt-4 flex items-center gap-1 text-sm font-medium text-signal"
        onClick={onToggle}
        type="button"
      >
        How this score works
        <ChevronDown className={showMethod ? "rotate-180" : ""} size={15} />
      </button>
      {showMethod && (
        <div className="mt-3 space-y-2">
          {edge.components.map((component) => (
            <div className="flex items-start justify-between gap-3 text-xs" key={component.label}>
              <span className="text-ink/55">{component.label}: {component.reason}</span>
              <strong className="text-ink">{component.score}</strong>
            </div>
          ))}
          <p className="pt-2 text-xs leading-5 text-ink/42">
            Weights: outcome 25%, payoff 25%, defined risk 20%, decision state 10%, sample
            reliability 20%. This is a transparent heuristic, not a validated probability.
          </p>
        </div>
      )}
    </article>
  );
}
