"use client";

// Currency strength and capital flow.
//
// Bars are scaled against the largest absolute value in the set rather than a
// fixed range, because the numbers are small (a strong session is well under
// 1%). A fixed axis would render every bar as a stub and hide the ranking,
// which is the only thing these panels exist to show.

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import type { AssetClass, StrengthSnapshot } from "./types";

/** Short tag so a cross-asset flow list stays readable at a glance. */
const ASSET_TAG: Record<AssetClass, string> = {
  fx: "FX",
  index: "IDX",
  commodity: "CMD",
  crypto: "CRY",
  equity: "EQ"
};

function scaleOf(values: number[]): number {
  const max = Math.max(...values.map((value) => Math.abs(value)), 0);
  // Floor keeps a dead-flat market from dividing by zero and from rendering
  // rounding noise as a full-width bar.
  return max < 0.01 ? 0.01 : max;
}

export function StrengthSection({ snapshot }: { snapshot: StrengthSnapshot | null }) {
  if (!snapshot) {
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        {[0, 1].map((index) => (
          <Card key={index}>
            <CardContent className="p-4">
              <div className="h-40 animate-pulse rounded bg-ink/10" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const strengthScale = scaleOf(snapshot.currencies.map((item) => item.score));
  const flowScale = scaleOf(snapshot.flow.map((item) => item.changePercent));

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Currency strength</CardTitle>
          <p className="text-xs text-ink/55">
            Each pair move split across both of its currencies · {snapshot.window}
          </p>
        </CardHeader>
        <CardContent className="space-y-1.5">
          {snapshot.currencies.map((item) => (
            <div className="flex items-center gap-2 text-xs" key={item.currency}>
              <span className="w-9 shrink-0 font-mono font-semibold text-ink">
                {item.currency}
              </span>
              <div className="relative h-3 flex-1">
                <div className="absolute inset-y-0 left-1/2 w-px bg-line" />
                <div
                  className={cn(
                    "absolute inset-y-0 rounded-sm",
                    item.score >= 0 ? "left-1/2 bg-moss" : "right-1/2 bg-loss"
                  )}
                  style={{
                    width: `${(Math.abs(item.score) / strengthScale) * 50}%`
                  }}
                />
              </div>
              <span
                className={cn(
                  "w-14 shrink-0 text-right font-mono tabular-nums",
                  item.score > 0 ? "text-moss" : item.score < 0 ? "text-loss" : "text-ink/45"
                )}
              >
                {item.score > 0 ? "+" : ""}
                {item.score.toFixed(3)}
              </span>
              <span
                className="w-10 shrink-0 text-right text-[10px] text-ink/35"
                title={`${item.pairs} pairs: ${item.contributions
                  .map(([pair]) => pair)
                  .join(", ")}`}
              >
                {item.pairs}p
              </span>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Capital flow</CardTitle>
          <p className="text-xs text-ink/55">
            Cross-asset: indices, commodities, and FX · {snapshot.window}
          </p>
        </CardHeader>
        <CardContent className="max-h-72 space-y-1.5 overflow-y-auto">
          {snapshot.flow.map((item) => (
            <div className="flex items-center gap-2 text-xs" key={item.symbol}>
              <span className="w-16 shrink-0 font-mono text-ink/75">{item.symbol}</span>
              <span className="w-8 shrink-0 text-[9px] uppercase text-ink/35">
                {ASSET_TAG[item.assetClass] ?? ""}
              </span>
              <div className="relative h-3 flex-1">
                <div className="absolute inset-y-0 left-1/2 w-px bg-line" />
                <div
                  className={cn(
                    "absolute inset-y-0 rounded-sm",
                    item.changePercent >= 0 ? "left-1/2 bg-moss" : "right-1/2 bg-loss"
                  )}
                  style={{
                    width: `${(Math.abs(item.changePercent) / flowScale) * 50}%`
                  }}
                />
              </div>
              <span
                className={cn(
                  "w-16 shrink-0 text-right font-mono tabular-nums",
                  item.changePercent > 0
                    ? "text-moss"
                    : item.changePercent < 0
                      ? "text-loss"
                      : "text-ink/45"
                )}
              >
                {item.changePercent > 0 ? "+" : ""}
                {item.changePercent.toFixed(3)}%
              </span>
            </div>
          ))}
          {Object.keys(snapshot.unavailable).length > 0 && (
            <p className="border-t border-line pt-2 text-[11px] text-ink/45">
              Unavailable: {Object.keys(snapshot.unavailable).join(", ")}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
