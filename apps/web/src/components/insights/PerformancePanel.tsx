"use client";

import { useMemo, useState } from "react";

import {
  equityCurve,
  performanceStats,
  positionSize,
  strategyBreakdown,
  tradeMultiplier
} from "@/lib/analytics";
import type { TradeEntry } from "@/lib/types";

function money(value: number): string {
  return value.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
}

function EquityCurveChart({ trades }: { trades: TradeEntry[] }) {
  const curve = useMemo(() => equityCurve(trades), [trades]);
  if (curve.length < 2) {
    return (
      <p className="text-sm text-ink/50">
        Log at least two closed trades to see your equity curve.
      </p>
    );
  }

  const width = 640;
  const height = 180;
  const pad = 8;
  const values = curve.map((p) => p.cumulative);
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const range = max - min || 1;
  const x = (i: number) => pad + (i / (curve.length - 1)) * (width - pad * 2);
  const y = (v: number) => height - pad - ((v - min) / range) * (height - pad * 2);
  const zeroY = y(0);
  const line = curve.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.cumulative).toFixed(1)}`).join(" ");
  const area = `${line} L${x(curve.length - 1).toFixed(1)},${zeroY.toFixed(1)} L${x(0).toFixed(1)},${zeroY.toFixed(1)} Z`;
  const positive = values[values.length - 1] >= 0;
  const stroke = positive ? "var(--color-moss, #34d399)" : "var(--color-loss, #f87171)";

  return (
    <svg
      className="w-full"
      height={height}
      preserveAspectRatio="none"
      role="img"
      aria-label="Cumulative realized profit and loss over time"
      viewBox={`0 0 ${width} ${height}`}
    >
      <line stroke="currentColor" strokeDasharray="3 3" className="text-ink/15" x1={pad} x2={width - pad} y1={zeroY} y2={zeroY} />
      <path d={area} fill={stroke} opacity={0.12} />
      <path d={line} fill="none" stroke={stroke} strokeWidth={2} strokeLinejoin="round" />
    </svg>
  );
}

function StrategyBars({ trades }: { trades: TradeEntry[] }) {
  const rows = useMemo(() => strategyBreakdown(trades).slice(0, 6), [trades]);
  if (!rows.length) return null;
  const maxAbs = Math.max(...rows.map((r) => Math.abs(r.pnl)), 1);

  return (
    <div className="space-y-2">
      {rows.map((row) => {
        const pct = (Math.abs(row.pnl) / maxAbs) * 100;
        const up = row.pnl >= 0;
        return (
          <div key={row.name} className="text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="min-w-0 truncate text-ink">{row.name}</span>
              <span className={`shrink-0 ${up ? "text-moss" : "text-loss"}`}>{money(row.pnl)}</span>
            </div>
            <div className="mt-1.5 flex items-center gap-2">
              <div className="h-1.5 flex-1 rounded-full bg-ink/8">
                <div
                  className={`h-1.5 rounded-full ${up ? "bg-moss" : "bg-loss"}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="shrink-0 whitespace-nowrap text-xs text-ink/45">
                {row.count} · {Math.round(row.winRate * 100)}%
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" }) {
  const color = tone === "good" ? "text-moss" : tone === "bad" ? "text-loss" : "text-ink";
  return (
    <div className="rounded-md border border-line bg-card/60 p-3">
      <p className="text-xs uppercase tracking-[0.1em] text-ink/45">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${color}`}>{value}</p>
    </div>
  );
}

function PositionCalculator() {
  const [account, setAccount] = useState("10000");
  const [riskPct, setRiskPct] = useState("1");
  const [entry, setEntry] = useState("");
  const [stop, setStop] = useState("");
  const [multiplier, setMultiplier] = useState("1");

  const result = positionSize(
    Number(account),
    Number(riskPct),
    Number(entry),
    Number(stop),
    Number(multiplier) || 1
  );

  const input = "min-h-9 w-full rounded-md border border-line bg-card px-2 text-sm text-ink";
  const field = (label: string, value: string, set: (v: string) => void, ph?: string) => (
    <label className="text-xs text-ink/60">
      {label}
      <input className={`mt-1 ${input}`} value={value} onChange={(e) => set(e.target.value)} placeholder={ph} inputMode="decimal" />
    </label>
  );

  return (
    <div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {field("Account $", account, setAccount)}
        {field("Risk %", riskPct, setRiskPct)}
        {field("Multiplier", multiplier, setMultiplier)}
        {field("Entry", entry, setEntry, "price")}
        {field("Stop", stop, setStop, "price")}
      </div>
      <div className="mt-3 rounded-md border border-signal/25 bg-signal/5 p-3 text-sm">
        {result ? (
          <p className="text-ink">
            Size <span className="font-semibold">{result.quantity}</span> unit
            {result.quantity === 1 ? "" : "s"} to risk{" "}
            <span className="font-semibold">{money(result.riskAmount)}</span> ({money(result.perUnitRisk)}/unit).
          </p>
        ) : (
          <p className="text-ink/50">Enter account size, risk %, entry, and stop to size a position.</p>
        )}
      </div>
    </div>
  );
}

export function PerformancePanel({ trades }: { trades: TradeEntry[] }) {
  const stats = useMemo(() => performanceStats(trades), [trades]);
  const hasClosed = stats.count > 0;

  const profitFactor =
    stats.profitFactor === null
      ? "—"
      : stats.profitFactor === Infinity
        ? "∞"
        : stats.profitFactor.toFixed(2);
  const expectancy = stats.expectancyR === null ? "—" : `${stats.expectancyR.toFixed(2)}R`;

  const lastMultiplier = trades.length ? tradeMultiplier(trades[0]) : 1;

  return (
    <section className="rounded-lg border border-line bg-card/86 p-4 shadow-panel md:p-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-ink">Performance</h2>
          <p className="mt-0.5 text-xs text-ink/50">
            Realized, closed-trade only. {stats.count} closed trade{stats.count === 1 ? "" : "s"}.
          </p>
        </div>
      </div>

      <div className="mt-4">
        <EquityCurveChart trades={trades} />
      </div>

      {hasClosed && (
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
          <Stat label="Realized P&L" value={money(stats.realizedPnl)} tone={stats.realizedPnl >= 0 ? "good" : "bad"} />
          <Stat label="Win rate" value={`${Math.round(stats.winRate * 100)}%`} />
          <Stat label="Profit factor" value={profitFactor} />
          <Stat label="Expectancy" value={expectancy} />
          <Stat label="Max drawdown" value={money(stats.maxDrawdown)} tone={stats.maxDrawdown < 0 ? "bad" : undefined} />
          <Stat label="Avg win / loss" value={`${money(stats.avgWin)} / ${money(stats.avgLoss)}`} />
        </div>
      )}

      {stats.rSampleSize === 0 && hasClosed && (
        <p className="mt-2 text-xs text-ink/45">
          Add stops or a risk amount to your trades to see R-multiples and expectancy.
        </p>
      )}

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <div>
          <h3 className="text-sm font-semibold text-ink">By strategy</h3>
          <div className="mt-3">
            <StrategyBars trades={trades} />
            {!hasClosed && <p className="text-sm text-ink/45">No closed trades yet.</p>}
          </div>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-ink">Position sizer</h3>
          <p className="mt-0.5 text-xs text-ink/45">
            How many units to risk a fixed % on this setup.
            {lastMultiplier !== 1 ? ` (last trade multiplier ${lastMultiplier})` : ""}
          </p>
          <div className="mt-3">
            <PositionCalculator />
          </div>
        </div>
      </div>
    </section>
  );
}
