"use client";

// Journal visualizations: performance heatmap, weekday P&L, quality radar,
// and focus actions. All derived client-side from the trades already in state;
// below the evidence minimums each block says so instead of rendering noise.

import { useMemo } from "react";

import {
  dailyPnl,
  focusActions,
  tradeQualityAxes,
  weekdayPnl
} from "@/lib/journalInsights";
import type { TradeEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

const WEEKS_SHOWN = 12;

export function JournalInsights({ trades }: { trades: TradeEntry[] }) {
  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-2">
        <PerformanceHeatmap trades={trades} />
        <WeekdayBars trades={trades} />
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <QualityRadar trades={trades} />
        <FocusActions trades={trades} />
      </div>
    </div>
  );
}

function PerformanceHeatmap({ trades }: { trades: TradeEntry[] }) {
  const cells = useMemo(() => {
    const buckets = new Map(dailyPnl(trades).map((bucket) => [bucket.date, bucket]));
    const days: Array<{ date: string; pnl: number | null }> = [];
    const today = new Date();
    // Align the grid to whole weeks, Monday-first, ending this week.
    const end = new Date(today);
    end.setUTCDate(end.getUTCDate() + (7 - ((end.getUTCDay() + 6) % 7) - 1));
    for (let index = WEEKS_SHOWN * 7 - 1; index >= 0; index -= 1) {
      const day = new Date(end);
      day.setUTCDate(day.getUTCDate() - index);
      const key = day.toISOString().slice(0, 10);
      days.push({ date: key, pnl: buckets.get(key)?.pnl ?? null });
    }
    return days;
  }, [trades]);

  const maxAbs = Math.max(...cells.map((cell) => Math.abs(cell.pnl ?? 0)), 1);

  return (
    <section>
      <h3 className="mb-2 text-sm font-semibold text-ink">Performance heatmap</h3>
      <div className="grid grid-flow-col grid-rows-7 gap-[3px]">
        {cells.map((cell) => {
          const intensity = cell.pnl === null ? 0 : Math.abs(cell.pnl) / maxAbs;
          return (
            <div
              className={cn(
                "aspect-square w-full rounded-[3px]",
                cell.pnl === null && "bg-ink/5",
                cell.pnl !== null && cell.pnl >= 0 && "bg-moss",
                cell.pnl !== null && cell.pnl < 0 && "bg-loss"
              )}
              key={cell.date}
              style={
                cell.pnl !== null
                  ? { opacity: 0.25 + 0.75 * intensity }
                  : undefined
              }
              title={
                cell.pnl === null
                  ? `${cell.date} — no closed trades`
                  : `${cell.date} — ${cell.pnl >= 0 ? "+" : ""}${cell.pnl.toFixed(2)}`
              }
            />
          );
        })}
      </div>
      <p className="mt-1.5 text-[11px] text-ink/45">
        Realized P&amp;L per day, last {WEEKS_SHOWN} weeks. Empty cells had no
        closed trades.
      </p>
    </section>
  );
}

function WeekdayBars({ trades }: { trades: TradeEntry[] }) {
  const rows = useMemo(() => weekdayPnl(trades), [trades]);
  const maxAbs = Math.max(...rows.map((row) => Math.abs(row.pnl)), 1);
  return (
    <section>
      <h3 className="mb-2 text-sm font-semibold text-ink">P&amp;L by weekday</h3>
      <div className="space-y-1.5">
        {rows.map((row) => (
          <div className="flex items-center gap-2 text-xs" key={row.weekday}>
            <span className="w-8 shrink-0 text-ink/60">{row.weekday}</span>
            <div className="relative h-3.5 flex-1">
              <div className="absolute inset-y-0 left-1/2 w-px bg-line" />
              <div
                className={cn(
                  "absolute inset-y-0 rounded-sm",
                  row.pnl >= 0 ? "left-1/2 bg-moss" : "right-1/2 bg-loss"
                )}
                style={{ width: `${(Math.abs(row.pnl) / maxAbs) * 50}%` }}
              />
            </div>
            <span
              className={cn(
                "w-20 shrink-0 text-right font-mono tabular-nums",
                row.pnl > 0 ? "text-moss" : row.pnl < 0 ? "text-loss" : "text-ink/40"
              )}
            >
              {row.count ? `${row.pnl >= 0 ? "+" : ""}${row.pnl.toFixed(2)}` : "—"}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function QualityRadar({ trades }: { trades: TradeEntry[] }) {
  const axes = useMemo(() => tradeQualityAxes(trades), [trades]);

  if (!axes.length) {
    return (
      <section>
        <h3 className="mb-2 text-sm font-semibold text-ink">Trade quality</h3>
        <p className="text-xs text-ink/55">
          Needs at least 3 closed trades before scoring anything.
        </p>
      </section>
    );
  }

  const size = 220;
  const center = size / 2;
  const radius = center - 34;
  const point = (index: number, value: number): [number, number] => {
    const angle = (Math.PI * 2 * index) / axes.length - Math.PI / 2;
    const distance = (value / 100) * radius;
    return [center + Math.cos(angle) * distance, center + Math.sin(angle) * distance];
  };
  const polygon = axes
    .map((axis, index) => point(index, axis.score).join(","))
    .join(" ");
  const overall = Math.round(
    axes.reduce((sum, axis) => sum + axis.score, 0) / axes.length
  );

  return (
    <section>
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-ink">Trade quality</h3>
        <span className="font-mono text-xs text-ink/55">{overall}/100</span>
      </div>
      <div className="flex flex-wrap items-center gap-4">
        <svg
          aria-label="Trade quality radar"
          height={size}
          role="img"
          width={size}
        >
          {[25, 50, 75, 100].map((ring) => (
            <polygon
              className="fill-none stroke-line"
              key={ring}
              points={axes
                .map((_, index) => point(index, ring).join(","))
                .join(" ")}
              strokeWidth={1}
            />
          ))}
          <polygon
            className="fill-signal/20 stroke-signal"
            points={polygon}
            strokeWidth={1.5}
          />
          {axes.map((axis, index) => {
            const [x, y] = point(index, 118);
            return (
              <text
                className="fill-current text-[9px] text-ink/60"
                dominantBaseline="middle"
                key={axis.label}
                textAnchor="middle"
                x={x}
                y={y}
              >
                {axis.label}
              </text>
            );
          })}
        </svg>
        <ul className="min-w-0 flex-1 space-y-1 text-[11px] text-ink/55">
          {axes.map((axis) => (
            <li key={axis.label}>
              <span className="font-medium text-ink/75">{axis.label}</span>{" "}
              {axis.score} — {axis.reason}
            </li>
          ))}
        </ul>
      </div>
      <p className="mt-1.5 text-[11px] text-ink/45">
        Every axis is measured from stored journal fields — this scores the
        record, not entry timing or skill.
      </p>
    </section>
  );
}

function FocusActions({ trades }: { trades: TradeEntry[] }) {
  const actions = useMemo(() => focusActions(trades), [trades]);
  return (
    <section>
      <h3 className="mb-2 text-sm font-semibold text-ink">Focus actions</h3>
      {actions.length === 0 ? (
        <p className="text-xs text-ink/55">
          No group has 3+ closed trades yet, so there is no pattern worth
          naming.
        </p>
      ) : (
        <ul className="space-y-2">
          {actions.map((action) => (
            <li
              className={cn(
                "rounded-md border p-2.5",
                action.tone === "positive"
                  ? "border-moss/30 bg-moss/5"
                  : "border-caution/30 bg-caution/5"
              )}
              key={action.title}
            >
              <p className="text-xs font-medium text-ink">{action.title}</p>
              <p className="mt-0.5 text-[11px] text-ink/60">{action.detail}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
