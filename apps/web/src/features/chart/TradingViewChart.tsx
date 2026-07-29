"use client";

// TradingView Advanced Real-Time Chart widget.
//
// The free embeddable widget is used rather than the Charting Library because
// the library requires applying to TradingView for repository access. The
// trade-off is that the widget renders TradingView's own data and exposes no
// programmatic price API — so it is a *visual* surface only. Every number
// Quant Labs acts on still comes from services/market_data.py.

import { useEffect, useRef } from "react";

const WIDGET_SRC =
  "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";

export function TradingViewChart({
  ticker,
  interval = "60",
  theme,
  height = 480
}: {
  ticker: string;
  interval?: string;
  theme: "light" | "dark";
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // The widget script reads its config from its own innerHTML and then
    // injects an iframe as a sibling, so the whole subtree is rebuilt on every
    // symbol/theme change rather than mutated.
    container.innerHTML = "";
    const mount = document.createElement("div");
    mount.className = "tradingview-widget-container__widget";
    container.appendChild(mount);

    const script = document.createElement("script");
    script.src = WIDGET_SRC;
    script.async = true;
    script.type = "text/javascript";
    script.innerHTML = JSON.stringify({
      symbol: ticker,
      interval,
      theme,
      autosize: true,
      timezone: "Etc/UTC",
      style: "1",
      locale: "en",
      hide_side_toolbar: false,
      allow_symbol_change: false,
      save_image: false,
      calendar: false,
      support_host: "https://www.tradingview.com"
    });
    container.appendChild(script);

    return () => {
      container.innerHTML = "";
    };
  }, [ticker, interval, theme]);

  return (
    <div
      className="tradingview-widget-container overflow-hidden rounded-lg border border-line"
      ref={containerRef}
      style={{ height }}
    />
  );
}
