"use client";

import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  dedupeTrades,
  parseCsvTrades,
  type ExistingKey,
  type ParsedTrade
} from "@/lib/csvImport";

type BrokerImportDialogProps = {
  existing: ExistingKey[];
  onImport: (trades: ParsedTrade[]) => void;
  onClose: () => void;
};

function money(value: number | null): string {
  return value === null ? "—" : value.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function BrokerImportDialog({ existing, onImport, onClose }: BrokerImportDialogProps) {
  const [text, setText] = useState("");

  const { trades, errors, duplicates } = useMemo(() => {
    if (!text.trim()) return { trades: [] as ParsedTrade[], errors: [] as string[], duplicates: 0 };
    const result = parseCsvTrades(text);
    const deduped = dedupeTrades(result.trades, existing);
    return { trades: deduped, errors: result.errors, duplicates: result.trades.length - deduped.length };
  }, [text, existing]);

  function onFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setText(String(reader.result ?? ""));
    reader.readAsText(file);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 p-4 pt-[8vh]"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Import trades from CSV"
    >
      <div
        className="flex max-h-[84vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-line bg-card shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="border-b border-line px-4 py-3">
          <h2 className="text-base font-semibold text-ink">Import trades from CSV</h2>
          <p className="mt-0.5 text-xs text-ink/50">
            Upload a broker export (TradingView, IBKR, Webull, or any CSV with symbol, side,
            quantity, and price columns). Columns are auto-detected; duplicates are skipped.
          </p>
        </div>

        <div className="grid gap-3 overflow-y-auto px-4 py-3">
          <div className="flex flex-wrap items-center gap-3">
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-line bg-card px-3 py-1.5 text-sm text-ink/70 hover:text-ink">
              Choose CSV file
              <input type="file" accept=".csv,text/csv" className="hidden" onChange={onFile} />
            </label>
            <span className="text-xs text-ink/40">or paste below</span>
          </div>
          <textarea
            className="min-h-28 w-full rounded-md border border-line bg-card px-3 py-2 text-sm text-ink"
            placeholder="Symbol,Side,Qty,Entry,Exit,Date&#10;AAPL,long,10,210,214,2026-07-01"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />

          {errors.length > 0 && (
            <div className="rounded-md border border-caution/30 bg-caution/10 p-2 text-xs text-caution">
              {errors.slice(0, 5).map((error) => (
                <p key={error}>{error}</p>
              ))}
              {errors.length > 5 && <p>…and {errors.length - 5} more.</p>}
            </div>
          )}

          {text.trim() && (
            <p className="text-xs text-ink/55">
              {trades.length} new trade{trades.length === 1 ? "" : "s"} to import
              {duplicates > 0 ? ` · ${duplicates} duplicate${duplicates === 1 ? "" : "s"} skipped` : ""}.
            </p>
          )}

          {trades.length > 0 && (
            <div className="overflow-x-auto rounded-md border border-line">
              <table className="w-full text-left text-xs">
                <thead className="bg-paper/50 text-ink/50">
                  <tr>
                    <th className="px-2 py-1.5">Symbol</th>
                    <th className="px-2 py-1.5">Side</th>
                    <th className="px-2 py-1.5">Qty</th>
                    <th className="px-2 py-1.5">Entry</th>
                    <th className="px-2 py-1.5">Exit</th>
                    <th className="px-2 py-1.5">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {trades.slice(0, 50).map((trade, i) => (
                    <tr key={`${trade.symbol}-${i}`} className="text-ink/80">
                      <td className="px-2 py-1.5 font-medium text-ink">{trade.symbol}</td>
                      <td className="px-2 py-1.5">{trade.side}</td>
                      <td className="px-2 py-1.5">{trade.quantity}</td>
                      <td className="px-2 py-1.5">{money(trade.entryPrice)}</td>
                      <td className="px-2 py-1.5">{money(trade.exitPrice)}</td>
                      <td className="px-2 py-1.5">{trade.entryDate}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {trades.length > 50 && (
                <p className="px-2 py-1.5 text-xs text-ink/40">…and {trades.length - 50} more.</p>
              )}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-line px-4 py-3">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
            disabled={trades.length === 0}
            onClick={() => {
              onImport(trades);
              onClose();
            }}
          >
            Import {trades.length || ""} trade{trades.length === 1 ? "" : "s"}
          </Button>
        </div>
      </div>
    </div>
  );
}
