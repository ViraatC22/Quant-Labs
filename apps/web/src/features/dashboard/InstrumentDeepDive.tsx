"use client";

// Per-instrument deep dive.
//
// Almost everything here is wiring rather than new logic: Flow / Bearing /
// Pulse and every indicator already come out of services/market_data.py, and
// the Edge Factor already exists in lib/sessionDesk.ts. This view arranges
// them; it does not compute a second opinion.
//
// One naming trap is called out in the UI itself. Quant Labs' Edge Factor
// scores *your trade record* on a symbol (win rate, payoff, risk definition).
// It is not a read on current market conditions, so it is labelled as such —
// two different questions that happen to share a name.

import { AlertTriangle, ArrowLeft, Gauge } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import * as api from "@/lib/api";
import { edgeFactor } from "@/lib/sessionDesk";
import type { MarketContext, TradeEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

import { TradingViewChart } from "@/features/chart/TradingViewChart";
import { toTradingViewSymbol } from "@/features/chart/tradingViewSymbols";

import { fetchMacroDesk, fetchMood, type MarketMood } from "./api";
import { conditionsScore } from "./conditions";
import { confidenceFormula } from "./confidence";
import type { InstrumentBias } from "./types";

/** Ordered scales straight out of market_data.py's vocabulary. */
const FLOW_SCALE = ["thin", "healthy", "crowded"] as const;
const PULSE_SCALE = ["quiet", "tradable", "wild"] as const;

const FLOW_MEANING: Record<string, string> = {
  thin: "Low participation — moves are easier to fake out and slippage widens.",
  healthy: "Participation is in its normal band for this instrument.",
  crowded: "Very high participation — momentum may already be over-extended.",
  unavailable: "The provider returned no usable volume for this instrument."
};

const PULSE_MEANING: Record<string, string> = {
  quiet: "Volatility is compressed — targets need to be smaller, not stops wider.",
  tradable: "Volatility sits in its normal range; standard stop sizing applies.",
  wild: "Volatility is elevated — expect stop-outs at normal position size.",
  unavailable: "Not enough ATR history to rank volatility."
};

function bearingMeaning(bearing: string): string {
  if (bearing.startsWith("trending")) {
    return "Price is covering ground efficiently — pullbacks are more likely to hold.";
  }
  if (bearing.startsWith("choppy")) {
    return "Direction exists but the path is inefficient — stop-outs are more frequent.";
  }
  if (bearing === "flat") return "No net direction over the recent window.";
  return "Bearing is unavailable.";
}

export function InstrumentDeepDive({
  symbol,
  trades,
  onBack
}: {
  symbol: string;
  trades: TradeEntry[];
  onBack: () => void;
}) {
  const [context, setContext] = useState<MarketContext | null>(null);
  const [bias, setBias] = useState<InstrumentBias | null>(null);
  const [mood, setMood] = useState<MarketMood | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [contextResult, deskResult, moodResult] = await Promise.all([
        api.getMarketContext(symbol),
        fetchMacroDesk([symbol]),
        fetchMood().catch(() => null)
      ]);
      setError(null);
      setContext(contextResult);
      setBias(deskResult.instruments[0] ?? null);
      setMood(moodResult);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : `Could not load ${symbol}.`);
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    async function run() {
      await load();
    }
    void run();
  }, [load]);

  // Scoped to this symbol. Returns "Insufficient evidence" below three
  // comparable closed trades rather than inventing a score.
  const edge = edgeFactor(trades, symbol);

  return (
    <div className="space-y-5">
      <button
        className="flex items-center gap-2 text-sm text-ink/60 hover:text-ink"
        onClick={onBack}
        type="button"
      >
        <ArrowLeft aria-hidden="true" size={15} strokeWidth={2.2} />
        Back to the desk
      </button>

      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-mono text-2xl font-semibold tracking-tight text-ink">{symbol}</h2>
          {context && (
            <p className="mt-0.5 text-sm text-ink/55">
              {context.last_price.toLocaleString(undefined, { maximumFractionDigits: 6 })}{" "}
              <span
                className={
                  context.change_percent > 0
                    ? "text-moss"
                    : context.change_percent < 0
                      ? "text-loss"
                      : undefined
                }
              >
                {context.change_percent > 0 ? "+" : ""}
                {context.change_percent.toFixed(2)}%
              </span>
              <span className="text-ink/40">
                {" "}
                · {context.interval} bars over {context.lookback} · {context.sample_size} samples
              </span>
            </p>
          )}
        </div>
        {bias && (
          <div className="text-right">
            <Badge
              variant={
                bias.direction === "bullish"
                  ? "success"
                  : bias.direction === "bearish"
                    ? "destructive"
                    : "outline"
              }
            >
              {bias.direction[0].toUpperCase() + bias.direction.slice(1)} · {bias.confidence}%
            </Badge>
          </div>
        )}
      </header>

      {error && (
        <Card className="border-loss/30 bg-loss/5">
          <CardContent className="p-3 text-sm text-ink/70">{error}</CardContent>
        </Card>
      )}

      {loading && !context ? (
        <div className="h-40 animate-pulse rounded-lg bg-ink/10" />
      ) : context ? (
        <>
          <TradingViewChart
            height={360}
            theme={
              typeof document !== "undefined" &&
              document.documentElement.classList.contains("dark")
                ? "dark"
                : "light"
            }
            ticker={toTradingViewSymbol(symbol).ticker}
          />
          <p className="-mt-2 text-[11px] text-ink/45">
            Chart data is TradingView&apos;s ({toTradingViewSymbol(symbol).ticker});
            every number below comes from Quant Labs&apos; own feed.
          </p>
          <div className="grid gap-4 lg:grid-cols-3">
            <ScaleCard
              label="Flow"
              meaning={FLOW_MEANING[context.flow] ?? "Unavailable."}
              scale={FLOW_SCALE}
              value={context.flow}
              detail={
                context.volume_percentile != null
                  ? `Volume in the ${context.volume_percentile.toFixed(0)}th percentile`
                  : "No usable volume"
              }
            />
            <BearingCard
              bearing={context.bearing}
              efficiency={context.trend_efficiency}
              changePercent={context.change_percent}
            />
            <ScaleCard
              label="Pulse"
              meaning={PULSE_MEANING[context.pulse] ?? "Unavailable."}
              scale={PULSE_SCALE}
              value={context.pulse}
              detail={
                context.atr_percent != null
                  ? `ATR ${context.atr_percent.toFixed(2)}% of price`
                  : "No ATR available"
              }
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            {bias && <ConditionsCard bias={bias} context={context} />}
            {mood && <MoodCard mood={mood} />}
          </div>

          <div className="grid gap-4 lg:grid-cols-[1fr_1.1fr]">
            <EdgeFactorCard edge={edge} symbol={symbol} />
            <IndicatorCard context={context} />
          </div>

          {bias && <SignalsCard bias={bias} />}

          {bias && bias.news.length > 0 && <InstrumentNewsCard bias={bias} />}

          {context.limitations.length > 0 && (
            <Card className="border-caution/30 bg-caution/5">
              <CardContent className="space-y-1 p-3 text-xs text-ink/70">
                {context.limitations.map((item) => (
                  <p className="flex items-start gap-1.5" key={item}>
                    <AlertTriangle
                      aria-hidden="true"
                      className="mt-0.5 shrink-0 text-caution"
                      size={12}
                      strokeWidth={2.2}
                    />
                    {item}
                  </p>
                ))}
              </CardContent>
            </Card>
          )}
        </>
      ) : null}
    </div>
  );
}

function ScaleCard({
  label,
  value,
  scale,
  meaning,
  detail
}: {
  label: string;
  value: string;
  scale: readonly string[];
  meaning: string;
  detail: string;
}) {
  const activeIndex = scale.indexOf(value);
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-semibold uppercase tracking-wide text-ink/55">
          {label}
        </CardTitle>
        <p className="text-lg font-semibold uppercase tracking-tight text-ink">{value}</p>
      </CardHeader>
      <CardContent className="space-y-2.5">
        <div className="flex gap-1">
          {scale.map((step, index) => (
            <div className="flex-1" key={step}>
              <div
                className={cn(
                  "h-1.5 rounded-full",
                  index === activeIndex ? "bg-signal" : "bg-ink/10"
                )}
              />
              <p
                className={cn(
                  "mt-1 text-[10px] capitalize",
                  index === activeIndex ? "font-medium text-ink" : "text-ink/40"
                )}
              >
                {step}
              </p>
            </div>
          ))}
        </div>
        <p className="text-xs text-ink/60">{meaning}</p>
        <p className="text-[11px] text-ink/45">{detail}</p>
      </CardContent>
    </Card>
  );
}

function BearingCard({
  bearing,
  efficiency,
  changePercent
}: {
  bearing: string;
  efficiency?: number | null;
  changePercent: number;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-semibold uppercase tracking-wide text-ink/55">
          Bearing
        </CardTitle>
        <p
          className={cn(
            "text-lg font-semibold uppercase tracking-tight",
            bearing.endsWith("up")
              ? "text-moss"
              : bearing.endsWith("down")
                ? "text-loss"
                : "text-ink"
          )}
        >
          {bearing}
        </p>
      </CardHeader>
      <CardContent className="space-y-2.5">
        <div>
          {/* Trend efficiency in [0,1]: how much of the path travelled became
              net progress. Low means chop, high means a clean impulse. */}
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink/10">
            <div
              className="h-full rounded-full bg-signal"
              style={{ width: `${Math.round((efficiency ?? 0) * 100)}%` }}
            />
          </div>
          <p className="mt-1 text-[10px] text-ink/40">
            {efficiency != null ? efficiency.toFixed(2) : "—"} trend efficiency
          </p>
        </div>
        <p className="text-xs text-ink/60">{bearingMeaning(bearing)}</p>
        <p className="text-[11px] text-ink/45">
          {changePercent > 0 ? "+" : ""}
          {changePercent.toFixed(2)}% net over the window
        </p>
      </CardContent>
    </Card>
  );
}

function EdgeFactorCard({
  edge,
  symbol
}: {
  edge: ReturnType<typeof edgeFactor>;
  symbol: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Gauge aria-hidden="true" className="text-ink/50" size={16} strokeWidth={2.2} />
          <CardTitle className="text-sm">Edge Factor</CardTitle>
        </div>
        {/* Stated explicitly: this scores the trader's record, not the market. */}
        <p className="text-xs text-ink/55">
          Your record trading {symbol} — not a read on current conditions.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-baseline gap-3">
          <span className="text-3xl font-semibold tabular-nums text-ink">{edge.score}</span>
          <div>
            <p className="text-sm font-medium text-ink">{edge.label}</p>
            <p className="text-xs text-ink/50">{edge.sample} comparable closed trades</p>
          </div>
        </div>
        <ul className="space-y-1.5 border-t border-line pt-2.5 text-xs">
          {edge.components.map((component) => (
            <li className="flex items-baseline justify-between gap-3" key={component.label}>
              <span className="text-ink/70">{component.label}</span>
              <span className="text-right text-ink/50">{component.reason}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function IndicatorCard({ context }: { context: MarketContext }) {
  const rows: Array<[string, string]> = [
    ["RSI(14)", context.rsi_14 != null ? context.rsi_14.toFixed(1) : "—"],
    ["ATR %", context.atr_percent != null ? `${context.atr_percent.toFixed(3)}%` : "—"],
    [
      "Bollinger width",
      context.bollinger_width_percent != null
        ? `${context.bollinger_width_percent.toFixed(2)}%`
        : "—"
    ],
    [
      "Volume percentile",
      context.volume_percentile != null ? `${context.volume_percentile.toFixed(0)}th` : "—"
    ],
    [
      "Trend efficiency",
      context.trend_efficiency != null ? context.trend_efficiency.toFixed(3) : "—"
    ],
    ["Data coverage", `${Math.round(context.confidence * 100)}%`],
    ["Provider", `${context.provider} (${context.provider_symbol})`],
    ["As of", new Date(context.as_of).toISOString().replace("T", " ").slice(0, 16) + "Z"]
  ];
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Indicators</CardTitle>
        <p className="text-xs text-ink/55">
          Every value the classifications above were derived from.
        </p>
      </CardHeader>
      <CardContent>
        <ul className="space-y-1.5 text-xs">
          {rows.map(([label, value]) => (
            <li className="flex items-baseline justify-between gap-3" key={label}>
              <span className="text-ink/60">{label}</span>
              <span className="font-mono text-ink/80">{value}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function SignalsCard({ bias }: { bias: InstrumentBias }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">How the bias was derived</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <ul className="space-y-1.5 text-xs">
          {bias.signals.map((signal) => (
            <li className="flex items-baseline justify-between gap-3" key={signal.label}>
              <span className="text-ink/70">
                {signal.label}
                {signal.role === "confirmation" && (
                  <span className="ml-1 text-ink/40">(confirmation only)</span>
                )}
              </span>
              <span className="text-right text-ink/55">{signal.detail}</span>
            </li>
          ))}
        </ul>
        <p className="border-t border-line pt-2 text-[11px] text-ink/45">
          {confidenceFormula(bias)}
        </p>
      </CardContent>
    </Card>
  );
}


function ConditionsCard({
  bias,
  context
}: {
  bias: InstrumentBias;
  context: MarketContext;
}) {
  const conditions = conditionsScore(bias, context);
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Market conditions</CardTitle>
        <p className="text-xs text-ink/55">
          Do current conditions support a setup? Separate from your trade-record
          Edge Factor below.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-baseline gap-3">
          <span className="text-3xl font-semibold tabular-nums text-ink">
            {conditions.score}
          </span>
          <span
            className={cn(
              "text-sm font-medium",
              conditions.label === "Supported"
                ? "text-moss"
                : conditions.label === "Mixed"
                  ? "text-caution"
                  : "text-ink/60"
            )}
          >
            {conditions.label}
          </span>
        </div>
        <ul className="space-y-1.5 border-t border-line pt-2.5 text-xs">
          {conditions.components.map((component) => (
            <li className="flex items-baseline justify-between gap-3" key={component.label}>
              <span className="shrink-0 text-ink/70">
                {component.label} · {component.score}
              </span>
              <span className="text-right text-ink/50">{component.reason}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function MoodCard({ mood }: { mood: MarketMood }) {
  const label =
    mood.mood === "risk_on" ? "RISK-ON" : mood.mood === "risk_off" ? "RISK-OFF" : "MIXED";
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Market mood</CardTitle>
        <p
          className={cn(
            "text-lg font-semibold uppercase tracking-tight",
            mood.mood === "risk_on"
              ? "text-moss"
              : mood.mood === "risk_off"
                ? "text-loss"
                : "text-ink"
          )}
        >
          {label}
        </p>
      </CardHeader>
      <CardContent className="space-y-2.5">
        <p className="text-xs text-ink/65">{mood.summary}</p>
        <ul className="space-y-1 border-t border-line pt-2 text-xs">
          {mood.components.map((component) => (
            <li className="flex items-baseline justify-between gap-2" key={component.symbol}>
              <span className="text-ink/70">
                {component.label}
                <span className="ml-1 text-[10px] uppercase text-ink/40">
                  {component.role}
                </span>
              </span>
              <span
                className={cn(
                  "font-mono tabular-nums",
                  component.changePercent > 0
                    ? "text-moss"
                    : component.changePercent < 0
                      ? "text-loss"
                      : "text-ink/45"
                )}
              >
                {component.changePercent > 0 ? "+" : ""}
                {component.changePercent.toFixed(2)}%
              </span>
            </li>
          ))}
        </ul>
        {mood.unavailable.length > 0 && (
          <p className="text-[11px] text-ink/45">
            Unavailable: {mood.unavailable.join(", ")}
          </p>
        )}
        <p className="text-[11px] text-ink/45">{mood.caveat}</p>
      </CardContent>
    </Card>
  );
}

function InstrumentNewsCard({ bias }: { bias: InstrumentBias }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">News for {bias.symbol}</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="divide-y divide-line">
          {bias.news.map((item) => (
            <li key={item.url}>
              <a
                className="block py-2 hover:opacity-80"
                href={item.url}
                rel="noopener noreferrer"
                target="_blank"
              >
                <p className="text-sm leading-snug text-ink">{item.title}</p>
                <p className="mt-0.5 text-xs text-ink/50">
                  {item.source}
                  {item.ageLabel ? ` · ${item.ageLabel}` : ""}
                </p>
              </a>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
