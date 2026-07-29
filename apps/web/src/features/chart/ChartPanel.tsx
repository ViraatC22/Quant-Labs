"use client";

// Chart tab: a TradingView chart with Quant Labs' own price beside it.
//
// The two panes deliberately show *different* feeds, and the UI says so. The
// chart is TradingView's data; the quote card is what services/market_data.py
// returns and the only price the trade ticket will use. Where those diverge
// materially — spot gold on the chart versus the futures proxy in our feed —
// the divergence is called out rather than left to be discovered later.

import { AlertTriangle, LineChart, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import * as api from "@/lib/api";
import type { MarketQuote } from "@/lib/types";
import { cn } from "@/lib/utils";

import { TradingViewChart } from "./TradingViewChart";
import { toTradingViewSymbol } from "./tradingViewSymbols";

const DEFAULT_SYMBOLS = ["ES", "NQ", "XAUUSD", "CL", "EURUSD", "USDJPY", "BTC"];

const INTERVALS: Array<{ label: string; value: string }> = [
  { label: "15m", value: "15" },
  { label: "1H", value: "60" },
  { label: "4H", value: "240" },
  { label: "1D", value: "D" }
];

const PRICE_BASIS_LABELS: Record<string, string> = {
  top_of_book: "Top of book",
  last_trade: "Last trade",
  indicative_mid: "Indicative mid"
};

/** Track the `dark` class the theme toggle writes onto <html>. */
function useThemeMode(): "light" | "dark" {
  const [mode, setMode] = useState<"light" | "dark">("dark");

  useEffect(() => {
    const root = document.documentElement;
    function sync() {
      // Reading the live DOM class is the only way to learn the resolved
      // theme; the toggle stores it outside React.
      setMode(root.classList.contains("dark") ? "dark" : "light");
    }
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  return mode;
}

export function ChartPanel({
  onLogTrade
}: {
  onLogTrade?: (symbol: string, price: string) => void;
}) {
  const [symbol, setSymbol] = useState("EURUSD");
  const [input, setInput] = useState("");
  const [interval, setIntervalValue] = useState("60");
  const [quote, setQuote] = useState<MarketQuote | null>(null);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const theme = useThemeMode();
  const tv = toTradingViewSymbol(symbol);

  const loadQuote = useCallback(async () => {
    try {
      const result = await api.getQuote(symbol);
      setQuoteError(null);
      setQuote(result);
    } catch (cause) {
      setQuote(null);
      setQuoteError(
        cause instanceof Error ? cause.message : `No quote available for ${symbol}.`
      );
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    async function run() {
      await loadQuote();
    }
    void run();
    const timer = window.setInterval(() => void run(), 30_000);
    return () => window.clearInterval(timer);
  }, [loadQuote]);

  function submitSymbol(event: React.FormEvent) {
    event.preventDefault();
    const next = input.trim().toUpperCase();
    if (!next) return;
    setSymbol(next);
    setInput("");
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <LineChart aria-hidden="true" className="text-ink/50" size={19} strokeWidth={2.2} />
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Chart</h1>
        </div>
        <form className="flex items-center gap-2" onSubmit={submitSymbol}>
          <input
            aria-label="Chart symbol"
            className="w-36 rounded-md border border-line bg-card px-3 py-1.5 text-sm"
            onChange={(event) => setInput(event.target.value)}
            placeholder="Symbol…"
            value={input}
          />
          <button
            className="rounded-md border border-line bg-card px-3 py-1.5 text-sm text-ink/70 hover:text-ink"
            type="submit"
          >
            Load
          </button>
        </form>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        {DEFAULT_SYMBOLS.map((item) => (
          <button
            className={cn(
              "rounded-md border px-2.5 py-1 font-mono text-xs",
              item === symbol
                ? "border-signal bg-signal/10 text-signal"
                : "border-line text-ink/60 hover:text-ink"
            )}
            key={item}
            onClick={() => setSymbol(item)}
            type="button"
          >
            {item}
          </button>
        ))}
        <span className="mx-1 h-4 w-px bg-line" />
        {INTERVALS.map((item) => (
          <button
            className={cn(
              "rounded-md border px-2.5 py-1 text-xs",
              item.value === interval
                ? "border-signal bg-signal/10 text-signal"
                : "border-line text-ink/60 hover:text-ink"
            )}
            key={item.value}
            onClick={() => setIntervalValue(item.value)}
            type="button"
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
        <div className="space-y-3">
          <TradingViewChart interval={interval} theme={theme} ticker={tv.ticker} />
          <p className="text-[11px] text-ink/45">
            Chart data is TradingView&apos;s ({tv.ticker}). Quant Labs prices come from a
            separate feed shown on the right.
          </p>
        </div>

        <div className="space-y-3">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="text-sm">Quant Labs price</CardTitle>
                <button
                  aria-label="Refresh the quote"
                  className="text-ink/50 hover:text-ink"
                  onClick={() => void loadQuote()}
                  type="button"
                >
                  <RefreshCw
                    aria-hidden="true"
                    className={loading ? "animate-spin" : undefined}
                    size={14}
                    strokeWidth={2.2}
                  />
                </button>
              </div>
              <p className="text-xs text-ink/55">
                The only price the trade ticket will use.
              </p>
            </CardHeader>
            <CardContent className="space-y-3">
              {quoteError ? (
                <p className="text-sm text-ink/55">{quoteError}</p>
              ) : quote ? (
                <>
                  <p className="font-mono text-2xl font-semibold text-ink">
                    {quote.last_price}
                    {quote.currency ? (
                      <span className="ml-1.5 text-xs font-normal text-ink/45">
                        {quote.currency}
                      </span>
                    ) : null}
                  </p>

                  <div className="flex flex-wrap gap-1.5 text-[11px]">
                    <span className="rounded border border-line px-1.5 py-0.5 text-ink/60">
                      {PRICE_BASIS_LABELS[quote.price_basis] ?? quote.price_basis}
                    </span>
                    {quote.delayed && (
                      <span className="rounded border border-line px-1.5 py-0.5 text-ink/60">
                        Delayed
                      </span>
                    )}
                    {quote.stale && (
                      <span className="rounded border border-caution/40 px-1.5 py-0.5 text-caution">
                        Stale
                      </span>
                    )}
                    <Badge variant={quote.executable ? "success" : "outline"}>
                      {quote.executable ? "Executable" : "Not executable"}
                    </Badge>
                  </div>

                  <ul className="space-y-1 border-t border-line pt-2 text-xs">
                    <li className="flex justify-between gap-2">
                      <span className="text-ink/55">Bid / Ask</span>
                      <span className="font-mono text-ink/80">
                        {quote.bid && quote.ask ? `${quote.bid} / ${quote.ask}` : "no book"}
                      </span>
                    </li>
                    <li className="flex justify-between gap-2">
                      <span className="text-ink/55">Provider</span>
                      <span className="font-mono text-ink/80">
                        {quote.provider_symbol}
                      </span>
                    </li>
                  </ul>

                  {onLogTrade && (
                    <button
                      className="w-full rounded-md border border-signal bg-signal/10 px-3 py-2 text-sm font-medium text-signal hover:bg-signal/15"
                      onClick={() => onLogTrade(symbol, quote.last_price)}
                      type="button"
                    >
                      Log a trade at this price
                    </button>
                  )}
                </>
              ) : (
                <div className="h-16 animate-pulse rounded bg-ink/10" />
              )}
            </CardContent>
          </Card>

          {tv.divergesFromOurFeed && (
            <Card className="border-caution/30 bg-caution/5">
              <CardContent className="flex items-start gap-2 p-3 text-xs text-ink/70">
                <AlertTriangle
                  aria-hidden="true"
                  className="mt-0.5 shrink-0 text-caution"
                  size={13}
                  strokeWidth={2.2}
                />
                {tv.divergenceNote}
              </CardContent>
            </Card>
          )}

          {quote?.proxy_note && (
            <Card className="border-caution/30 bg-caution/5">
              <CardContent className="p-3 text-xs text-ink/70">{quote.proxy_note}</CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
