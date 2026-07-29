"use client";

// Session desk dashboard: greeting, market sessions, macro bias cards, the
// pre-session briefing, and the news rail.
//
// A running theme in this file is that provenance is rendered, not hidden. Every
// bias card states whether its prose was derived or model-phrased, what kind of
// price it is built on, and whether the instrument is a proxy. That surface area
// is the difference between a dashboard you can audit and one you have to trust.

import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  ChevronDown,
  ExternalLink,
  Minus,
  Newspaper,
  RefreshCw,
  Sparkles,
  UserRound
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TradeEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

import {
  fetchBriefing,
  fetchCalibration,
  fetchMacroDesk,
  fetchNews,
  fetchSessions,
  fetchStrength
} from "./api";
import { confidenceFormula } from "./confidence";
import { InstrumentDeepDive } from "./InstrumentDeepDive";
import { StrengthSection } from "./StrengthSection";
import type {
  BiasDirection,
  CalibrationStats,
  Briefing,
  InstrumentBias,
  MacroDesk,
  NewsFeed,
  SessionState,
  StrengthSnapshot
} from "./types";

const NAME_STORAGE_KEY = "quant-labs.desk.trader-name";
const REFRESH_INTERVAL_MS = 60_000;

function greetingFor(date: Date): string {
  const hour = date.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function directionTone(direction: BiasDirection): string {
  if (direction === "bullish") return "text-moss";
  if (direction === "bearish") return "text-loss";
  return "text-ink/55";
}

function directionBadge(direction: BiasDirection): "success" | "destructive" | "outline" {
  if (direction === "bullish") return "success";
  if (direction === "bearish") return "destructive";
  return "outline";
}

/** Human label for market_data.PRICE_BASIS_*, with the caveat that matters. */
const PRICE_BASIS_LABELS: Record<string, { label: string; hint: string }> = {
  top_of_book: {
    label: "Top of book",
    hint: "Live bid/ask from the execution venue."
  },
  last_trade: {
    label: "Last trade",
    hint: "Last printed trade. There is no size behind this price."
  },
  indicative_mid: {
    label: "Indicative mid",
    hint: "Aggregated mid with no bid/ask. A real fill costs at least half the spread."
  }
};

export function DashboardPanel({ trades = [] }: { trades?: TradeEntry[] }) {
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [editingName, setEditingName] = useState(false);
  const [desk, setDesk] = useState<MacroDesk | null>(null);
  const [sessions, setSessions] = useState<SessionState[]>([]);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [news, setNews] = useState<NewsFeed | null>(null);
  const [strength, setStrength] = useState<StrengthSnapshot | null>(null);
  const [calibration, setCalibration] = useState<CalibrationStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => new Date());

  // Read after mount so the server render and first client render match, the
  // same approach WorkspaceApp uses for the persisted workspace.
  useEffect(() => {
    function loadName() {
      try {
        setName(window.localStorage.getItem(NAME_STORAGE_KEY) ?? "");
      } catch {
        // Storage can be unavailable (private mode); the greeting just drops
        // the name.
      }
    }
    loadName();
  }, []);

  // A local ticking clock keeps the session strip alive between polls, so the
  // countdown does not visibly freeze for a minute at a time.
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1_000);
    return () => window.clearInterval(timer);
  }, []);

  const load = useCallback(async () => {
    try {
      const [
        deskResult,
        sessionResult,
        briefingResult,
        newsResult,
        strengthResult,
        calibrationResult
      ] = await Promise.all([
        fetchMacroDesk(),
        fetchSessions(),
        fetchBriefing(),
        fetchNews(),
        fetchStrength(),
        fetchCalibration().catch(() => null)
      ]);
      setError(null);
      setDesk(deskResult);
      setSessions(sessionResult);
      setBriefing(briefingResult);
      setNews(newsResult);
      setStrength(strengthResult);
      setCalibration(calibrationResult);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The desk could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Poll on an interval so the desk stays current without a manual refresh.
  // `run` awaits before any state is written, keeping the effect body free of
  // synchronous setState (see WorkspaceApp's mount effect for the same shape).
  useEffect(() => {
    async function run() {
      await load();
    }
    void run();
    const timer = window.setInterval(() => void run(), REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [load]);

  function persistName(value: string) {
    setName(value);
    window.localStorage.setItem(NAME_STORAGE_KEY, value);
  }

  const greeting = useMemo(() => greetingFor(now), [now]);

  if (selectedSymbol) {
    return (
      <InstrumentDeepDive
        onBack={() => setSelectedSymbol(null)}
        symbol={selectedSymbol}
        trades={trades}
      />
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-ink">
            {greeting}
            {name ? `, ${name}` : ""}.
          </h1>
          <p className="mt-1 flex items-center gap-2 text-sm text-ink/55">
            <Sparkles aria-hidden="true" size={14} strokeWidth={2.2} />
            Your session desk — every number below is derived from data you can inspect.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {editingName ? (
            <input
              autoFocus
              aria-label="Your name"
              className="rounded-md border border-line bg-card px-3 py-1.5 text-sm"
              defaultValue={name}
              onBlur={(event) => {
                persistName(event.target.value.trim());
                setEditingName(false);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") event.currentTarget.blur();
                if (event.key === "Escape") setEditingName(false);
              }}
              placeholder="Your name"
            />
          ) : (
            <button
              className="flex items-center gap-2 rounded-md border border-line bg-card px-3 py-1.5 text-sm text-ink/70 hover:text-ink"
              onClick={() => setEditingName(true)}
              type="button"
            >
              <UserRound aria-hidden="true" size={15} strokeWidth={2.2} />
              Personalize
            </button>
          )}
          <button
            aria-label="Refresh the desk"
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

      {error && (
        <Card className="border-loss/30 bg-loss/5">
          <CardContent className="flex items-start gap-3 p-4">
            <AlertTriangle
              aria-hidden="true"
              className="mt-0.5 shrink-0 text-loss"
              size={16}
              strokeWidth={2.2}
            />
            <div className="text-sm">
              <p className="font-medium text-ink">The desk could not be loaded.</p>
              <p className="mt-0.5 text-ink/60">{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      <SessionStrip now={now} sessions={sessions} />

      <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <MacroDeskSection desk={desk} loading={loading} onSelect={setSelectedSymbol} />
        <BriefingSection briefing={briefing} loading={loading} />
      </div>

      <StrengthSection snapshot={strength} />

      <TrackRecordSection stats={calibration} />

      <NewsSection feed={news} loading={loading} />
    </div>
  );
}

function SessionStrip({ now, sessions }: { now: Date; sessions: SessionState[] }) {
  if (!sessions.length) return null;
  return (
    <Card>
      <CardContent className="flex flex-wrap items-center gap-x-8 gap-y-4 p-4">
        {sessions.map((session) => (
          <div className="flex items-center gap-2.5" key={session.key}>
            <span
              aria-hidden="true"
              className={cn(
                "h-2 w-2 shrink-0 rounded-full",
                session.isOpen
                  ? "bg-moss"
                  : session.phase === "closed"
                    ? "bg-ink/25"
                    : "bg-caution"
              )}
            />
            <div className="leading-tight">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink">
                {session.label}
              </p>
              <p className="text-xs text-ink/55">
                <span className={session.isOpen ? "text-moss" : undefined}>
                  {session.phaseLabel}
                </span>
                {" · "}
                {session.nextPhaseLabel.toLowerCase()} in {session.countdown}
              </p>
            </div>
          </div>
        ))}
        <div className="ml-auto text-right leading-tight">
          <p className="font-mono text-sm text-ink">
            {now.toISOString().slice(11, 19)}
          </p>
          <p className="text-xs text-ink/50">UTC</p>
        </div>
      </CardContent>
    </Card>
  );
}

function MacroDeskSection({
  desk,
  loading,
  onSelect
}: {
  desk: MacroDesk | null;
  loading: boolean;
  onSelect: (symbol: string) => void;
}) {
  const unavailable = Object.entries(desk?.unavailable ?? {});
  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink">Macro desk</h2>
          <p className="text-sm text-ink/55">
            Direction and confidence are computed from market data, not asserted by a model.
          </p>
        </div>
      </div>

      {loading && !desk ? (
        <SkeletonGrid />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {desk?.instruments.map((bias) => (
            <BiasCard bias={bias} key={bias.symbol} onSelect={onSelect} />
          ))}
        </div>
      )}

      {unavailable.length > 0 && (
        <Card className="border-caution/30 bg-caution/5">
          <CardContent className="p-3 text-xs text-ink/70">
            {unavailable.map(([symbol, reason]) => (
              <p key={symbol}>
                <span className="font-semibold text-ink">{symbol}</span> — {reason}
              </p>
            ))}
          </CardContent>
        </Card>
      )}
    </section>
  );
}

function BiasCard({
  bias,
  onSelect
}: {
  bias: InstrumentBias;
  onSelect: (symbol: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const basis = PRICE_BASIS_LABELS[bias.priceBasis] ?? {
    label: bias.priceBasis,
    hint: "Unrecognized price basis."
  };
  const Arrow =
    bias.changePercent > 0 ? ArrowUpRight : bias.changePercent < 0 ? ArrowDownRight : Minus;

  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="font-mono text-base tracking-tight">
            <button
              className="rounded hover:text-signal hover:underline"
              onClick={() => onSelect(bias.symbol)}
              title={`Open the ${bias.symbol} deep dive`}
              type="button"
            >
              {bias.symbol}
            </button>
          </CardTitle>
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "flex items-center gap-0.5 text-xs font-medium",
                directionTone(
                  bias.changePercent > 0
                    ? "bullish"
                    : bias.changePercent < 0
                      ? "bearish"
                      : "neutral"
                )
              )}
            >
              <Arrow aria-hidden="true" size={13} strokeWidth={2.4} />
              {bias.changePercent > 0 ? "+" : ""}
              {bias.changePercent.toFixed(2)}%
            </span>
            <Badge variant={directionBadge(bias.direction)}>
              {bias.direction[0].toUpperCase() + bias.direction.slice(1)}
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-3">
        <div>
          <div className="flex items-baseline justify-between text-xs">
            <span className="text-ink/55">
              Confidence
              {bias.calibrationApplied && (
                <span
                  className="ml-1 rounded border border-signal/40 px-1 text-[9px] uppercase text-signal"
                  title={bias.calibrationNote}
                >
                  calibrated
                </span>
              )}
            </span>
            <span className="font-mono font-medium text-ink">
              {bias.confidence}%
              {bias.calibrationApplied && (
                <span className="ml-1 text-[10px] font-normal text-ink/40">
                  raw {bias.rawConfidence}%
                </span>
              )}
            </span>
          </div>
          <div
            aria-label={`Confidence ${bias.confidence} percent`}
            aria-valuemax={100}
            aria-valuemin={0}
            aria-valuenow={bias.confidence}
            className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-ink/10"
            role="progressbar"
          >
            <div
              className={cn(
                "h-full rounded-full",
                bias.direction === "bullish"
                  ? "bg-moss"
                  : bias.direction === "bearish"
                    ? "bg-loss"
                    : "bg-ink/35"
              )}
              style={{ width: `${bias.confidence}%` }}
            />
          </div>
        </div>

        <div className="rounded-md border border-line bg-paper/40 p-3">
          <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-signal">
            <Sparkles aria-hidden="true" size={12} strokeWidth={2.4} />
            {bias.explanationMode === "model" ? "AI-phrased analysis" : "Derived analysis"}
          </p>
          <p className="text-sm leading-relaxed text-ink/80">{bias.explanation}</p>
        </div>

        {bias.news.length > 0 && (
          <ul className="space-y-1 rounded-md border border-line bg-paper/30 p-2.5">
            {bias.news.slice(0, 3).map((item) => (
              <li key={item.url}>
                <a
                  className="flex items-baseline gap-1.5 text-xs text-ink/70 hover:text-ink"
                  href={item.url}
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  <span aria-hidden="true" className="text-ink/30">
                    •
                  </span>
                  <span className="min-w-0 flex-1 truncate">{item.title}</span>
                  {item.ageLabel && (
                    <span className="shrink-0 text-[10px] text-ink/40">
                      {item.ageLabel}
                    </span>
                  )}
                </a>
              </li>
            ))}
          </ul>
        )}

        {bias.proxyNote && (
          <p className="flex items-start gap-1.5 rounded-md border border-caution/30 bg-caution/5 p-2 text-xs text-ink/70">
            <AlertTriangle
              aria-hidden="true"
              className="mt-0.5 shrink-0 text-caution"
              size={13}
              strokeWidth={2.2}
            />
            {bias.proxyNote}
          </p>
        )}

        <div className="mt-auto space-y-2">
          <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-ink/50">
            <span
              className="rounded border border-line px-1.5 py-0.5"
              title={basis.hint}
            >
              {basis.label}
            </span>
            {bias.delayed && (
              <span
                className="rounded border border-line px-1.5 py-0.5"
                title="Not an executable quote."
              >
                Delayed
              </span>
            )}
            {bias.stale && (
              <span className="rounded border border-caution/40 px-1.5 py-0.5 text-caution">
                Stale
              </span>
            )}
            <span>{bias.sampleSize} bars</span>
          </div>

          <button
            aria-expanded={open}
            className="flex w-full items-center justify-between rounded-md border border-line px-2.5 py-1.5 text-xs text-ink/65 hover:text-ink"
            onClick={() => setOpen((value) => !value)}
            type="button"
          >
            <span>{open ? "Hide" : "Show"} the signals behind this</span>
            <ChevronDown
              aria-hidden="true"
              className={cn("transition-transform", open && "rotate-180")}
              size={14}
              strokeWidth={2.2}
            />
          </button>

          {open && (
            <ul className="space-y-1.5 rounded-md border border-line bg-paper/40 p-2.5 text-xs">
              {bias.signals.map((signal) => (
                <li className="flex items-baseline justify-between gap-3" key={signal.label}>
                  <span className="shrink-0 text-ink/70">
                    {signal.label}
                    {signal.role === "confirmation" && (
                      <span className="ml-1 text-ink/40">(confirmation only)</span>
                    )}
                  </span>
                  <span className="text-right text-ink/55">{signal.detail}</span>
                </li>
              ))}
              <li className="border-t border-line pt-1.5 text-[11px] text-ink/45">
                {confidenceFormula(bias)}
              </li>
            </ul>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function BriefingSection({
  briefing,
  loading
}: {
  briefing: Briefing | null;
  loading: boolean;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-ink">For you</h2>
        <p className="text-sm text-ink/55">Your pre-session briefing.</p>
      </div>

      <Card className="flex flex-col">
        <CardContent className="space-y-4 p-4">
          {loading && !briefing ? (
            <div className="space-y-2">
              <div className="h-4 w-3/4 animate-pulse rounded bg-ink/10" />
              <div className="h-3 w-full animate-pulse rounded bg-ink/10" />
              <div className="h-3 w-5/6 animate-pulse rounded bg-ink/10" />
            </div>
          ) : briefing ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{briefing.regime}</Badge>
                <Badge
                  variant={briefing.tone === "Cautious" ? "warning" : "success"}
                >
                  {briefing.tone}
                </Badge>
              </div>

              <div>
                <h3 className="font-semibold leading-snug text-ink">{briefing.headline}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-ink/70">
                  {briefing.summary}
                </p>
              </div>

              {briefing.changes.length > 0 && (
                <ul className="space-y-1.5 rounded-md border border-signal/25 bg-signal/5 p-3">
                  {briefing.changes.map((change) => (
                    <li className="flex items-start gap-2 text-xs text-ink/80" key={change}>
                      <span
                        aria-hidden="true"
                        className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-signal"
                      />
                      {change}
                    </li>
                  ))}
                </ul>
              )}

              <ul className="space-y-2.5 border-t border-line pt-3">
                {briefing.items.map((item) => (
                  <li className="text-sm" key={item.symbol}>
                    <p className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-ink">
                        {item.symbol}
                      </span>
                      <span
                        className={cn(
                          "text-xs font-medium uppercase",
                          directionTone(item.direction)
                        )}
                      >
                        {item.direction}
                      </span>
                      <span className="text-[11px] text-ink/45">
                        {item.band} · {item.confidence}%
                      </span>
                    </p>
                    <p className="mt-0.5 text-xs leading-relaxed text-ink/60">{item.text}</p>
                  </li>
                ))}
              </ul>

              {briefing.caveats.length > 0 && (
                <ul className="space-y-1 border-t border-line pt-3 text-[11px] text-ink/50">
                  {briefing.caveats.map((caveat) => (
                    <li key={caveat}>• {caveat}</li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <p className="text-sm text-ink/55">No briefing is available.</p>
          )}
        </CardContent>
      </Card>
    </section>
  );
}

function NewsSection({ feed, loading }: { feed: NewsFeed | null; loading: boolean }) {
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <Newspaper aria-hidden="true" className="text-ink/50" size={17} strokeWidth={2.2} />
        <h2 className="text-lg font-semibold text-ink">News</h2>
        {feed?.stale && <Badge variant="warning">Cached</Badge>}
      </div>

      <Card>
        <CardContent className="p-4">
          {loading && !feed ? (
            <div className="space-y-3">
              {[0, 1, 2].map((index) => (
                <div className="h-4 w-2/3 animate-pulse rounded bg-ink/10" key={index} />
              ))}
            </div>
          ) : feed?.available && feed.items.length > 0 ? (
            <ul className="divide-y divide-line">
              {feed.items.map((item) => (
                <li key={item.url}>
                  <a
                    className="flex items-start justify-between gap-3 py-2.5 hover:opacity-80"
                    href={item.url}
                    rel="noopener noreferrer"
                    target="_blank"
                  >
                    <div className="min-w-0">
                      <p className="text-sm leading-snug text-ink">{item.title}</p>
                      <p className="mt-0.5 text-xs text-ink/50">
                        {item.source}
                        {item.ageLabel ? ` · ${item.ageLabel}` : ""}
                      </p>
                    </div>
                    <ExternalLink
                      aria-hidden="true"
                      className="mt-0.5 shrink-0 text-ink/35"
                      size={13}
                      strokeWidth={2.2}
                    />
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            // No key or a provider outage shows the reason rather than an empty
            // panel — and never placeholder headlines.
            <p className="text-sm text-ink/55">
              {feed?.reason ?? "No headlines are available."}
            </p>
          )}
        </CardContent>
      </Card>
    </section>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {[0, 1, 2, 3].map((index) => (
        <Card key={index}>
          <CardContent className="space-y-3 p-4">
            <div className="h-4 w-24 animate-pulse rounded bg-ink/10" />
            <div className="h-1.5 w-full animate-pulse rounded bg-ink/10" />
            <div className="h-16 w-full animate-pulse rounded bg-ink/10" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
const BUCKET_LABELS: Record<string, string> = {
  directional_high: "Directional calls, confidence ≥45",
  directional_low: "Directional calls, confidence <45",
  neutral: "Ranging calls"
};

function TrackRecordSection({ stats }: { stats: CalibrationStats | null }) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-ink">Track record</h2>
        <p className="text-sm text-ink/55">
          Every call is graded 8–48h later against what price actually did.
          Once a bucket reaches {stats?.minSample ?? 20} graded calls, its hit
          rate calibrates the confidence shown on new calls.
        </p>
      </div>
      <Card>
        <CardContent className="p-4">
          {!stats || stats.totalGraded === 0 ? (
            <p className="text-sm text-ink/55">
              Nothing graded yet. Calls become gradable 8 hours after they are
              made, so the record starts filling in from tomorrow&apos;s visits.
            </p>
          ) : (
            <div className="space-y-3">
              <ul className="space-y-2">
                {stats.buckets.map((bucket) => (
                  <li className="flex items-center gap-3 text-xs" key={bucket.bucket}>
                    <span className="w-56 shrink-0 text-ink/70">
                      {BUCKET_LABELS[bucket.bucket] ?? bucket.bucket}
                    </span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-ink/10">
                      {bucket.hitRate !== null && (
                        <div
                          className="h-full rounded-full bg-signal"
                          style={{ width: `${Math.round(bucket.hitRate * 100)}%` }}
                        />
                      )}
                    </div>
                    <span className="w-32 shrink-0 text-right font-mono text-ink/70">
                      {bucket.hitRate !== null
                        ? `${Math.round(bucket.hitRate * 100)}% of ${bucket.graded}`
                        : "—"}
                      {bucket.graded < (stats.minSample ?? 20) && (
                        <span className="ml-1 text-[10px] text-ink/40">
                          (below floor)
                        </span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
              {stats.luckBaseline !== null && (
                <p className="border-t border-line pt-2 text-[11px] text-ink/50">
                  Luck baseline: a coin-flip direction call would have scored{" "}
                  {Math.round(stats.luckBaseline * 100)}% on these same windows —
                  a hit rate has to beat that before it means anything.
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
