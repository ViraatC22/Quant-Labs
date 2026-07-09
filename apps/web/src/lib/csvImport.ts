// Broker CSV -> trade rows. Pure and unit-tested (csvImport.test.ts). Auto-maps
// common column names from TradingView / IBKR / Webull / generic exports, so a
// user can drop in an export without configuring anything.

export type ParsedTrade = {
  symbol: string;
  side: "long" | "short";
  entryDate: string;
  entryPrice: number;
  exitPrice: number | null;
  quantity: number;
  fees: number;
  strategy: string;
  setup: string;
};

export type ParseResult = { trades: ParsedTrade[]; errors: string[] };

// Minimal RFC-4180-ish CSV: handles quoted fields, escaped quotes, CRLF.
export function parseCsvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      row.push(field);
      field = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i += 1;
      row.push(field);
      field = "";
      if (row.some((cell) => cell.trim() !== "")) rows.push(row);
      row = [];
    } else {
      field += ch;
    }
  }
  if (field !== "" || row.length) {
    row.push(field);
    if (row.some((cell) => cell.trim() !== "")) rows.push(row);
  }
  return rows;
}

type ColumnKey =
  | "symbol"
  | "side"
  | "quantity"
  | "entryPrice"
  | "exitPrice"
  | "fees"
  | "strategy"
  | "setup"
  | "date";

const COLUMN_ALIASES: Record<ColumnKey, string[]> = {
  symbol: ["symbol", "ticker", "instrument", "contract"],
  side: ["side", "action", "direction", "b/s", "buy/sell", "type"],
  quantity: ["quantity", "qty", "shares", "size", "contracts", "filledqty", "filled"],
  entryPrice: ["entryprice", "entry", "avgprice", "fillprice", "price", "openprice", "avgfillprice"],
  exitPrice: ["exitprice", "exit", "closeprice", "closingprice", "closingprc"],
  fees: ["fees", "fee", "commission", "comm", "commissions"],
  strategy: ["strategy"],
  setup: ["setup"],
  date: ["date", "entrytime", "opentime", "tradedate", "time", "datetime", "opened"]
};

function normalizeHeader(header: string): string {
  return header.toLowerCase().replace(/[^a-z/]/g, "");
}

function findColumn(headers: string[], aliases: string[]): number {
  const normalized = headers.map(normalizeHeader);
  for (const alias of aliases) {
    const idx = normalized.indexOf(alias);
    if (idx !== -1) return idx;
  }
  return -1;
}

function toSide(raw: string): "long" | "short" | null {
  const v = raw.trim().toLowerCase();
  if (["long", "buy", "b", "bot", "bought"].includes(v)) return "long";
  if (["short", "sell", "s", "sld", "sold"].includes(v)) return "short";
  return null;
}

function toNumber(raw: string): number | null {
  const cleaned = raw.replace(/[$,\s]/g, "").replace(/[()]/g, "");
  if (cleaned === "") return null;
  const negative = /^\(.*\)$/.test(raw.trim());
  const value = Number(cleaned);
  if (!Number.isFinite(value)) return null;
  return negative ? -Math.abs(value) : value;
}

function toDate(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  // Already ISO-ish date at the start.
  const iso = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
  // US M/D/Y.
  const us = trimmed.match(/^(\d{1,2})[/](\d{1,2})[/](\d{2,4})/);
  if (us) {
    const year = us[3].length === 2 ? `20${us[3]}` : us[3];
    return `${year}-${us[1].padStart(2, "0")}-${us[2].padStart(2, "0")}`;
  }
  const parsed = new Date(trimmed);
  if (!Number.isNaN(parsed.getTime())) return parsed.toISOString().slice(0, 10);
  return null;
}

export function parseCsvTrades(text: string): ParseResult {
  const rows = parseCsvRows(text);
  if (rows.length < 2) return { trades: [], errors: ["No data rows found in the file."] };

  const headers = rows[0];
  const col = {
    symbol: findColumn(headers, COLUMN_ALIASES.symbol),
    side: findColumn(headers, COLUMN_ALIASES.side),
    quantity: findColumn(headers, COLUMN_ALIASES.quantity),
    entryPrice: findColumn(headers, COLUMN_ALIASES.entryPrice),
    exitPrice: findColumn(headers, COLUMN_ALIASES.exitPrice),
    fees: findColumn(headers, COLUMN_ALIASES.fees),
    strategy: findColumn(headers, COLUMN_ALIASES.strategy),
    setup: findColumn(headers, COLUMN_ALIASES.setup),
    date: findColumn(headers, COLUMN_ALIASES.date)
  };

  const missing: string[] = [];
  if (col.symbol === -1) missing.push("symbol");
  if (col.quantity === -1) missing.push("quantity");
  if (col.entryPrice === -1) missing.push("entry price");
  if (missing.length) {
    return { trades: [], errors: [`Could not find a ${missing.join(", ")} column in the header.`] };
  }

  const trades: ParsedTrade[] = [];
  const errors: string[] = [];
  const cell = (row: string[], index: number) => (index >= 0 ? (row[index] ?? "") : "");

  rows.slice(1).forEach((row, i) => {
    const lineNo = i + 2;
    const symbol = cell(row, col.symbol).trim().toUpperCase();
    const quantity = toNumber(cell(row, col.quantity));
    const entryPrice = toNumber(cell(row, col.entryPrice));
    const side = col.side >= 0 ? toSide(cell(row, col.side)) : "long";

    if (!symbol) {
      errors.push(`Row ${lineNo}: missing symbol — skipped.`);
      return;
    }
    if (quantity === null || quantity === 0) {
      errors.push(`Row ${lineNo}: invalid quantity — skipped.`);
      return;
    }
    if (entryPrice === null) {
      errors.push(`Row ${lineNo}: invalid entry price — skipped.`);
      return;
    }

    trades.push({
      symbol,
      side: side ?? "long",
      entryDate: toDate(cell(row, col.date)) ?? new Date().toISOString().slice(0, 10),
      entryPrice,
      exitPrice: col.exitPrice >= 0 ? toNumber(cell(row, col.exitPrice)) : null,
      quantity: Math.abs(quantity),
      fees: (col.fees >= 0 ? toNumber(cell(row, col.fees)) : 0) ?? 0,
      strategy: cell(row, col.strategy).trim(),
      setup: cell(row, col.setup).trim()
    });
  });

  return { trades, errors };
}

export type ExistingKey = Pick<ParsedTrade, "symbol" | "entryDate" | "entryPrice" | "quantity">;

function key(t: ExistingKey): string {
  return `${t.symbol}|${t.entryDate}|${t.entryPrice}|${t.quantity}`;
}

// Drop rows that already exist (same symbol/date/entry/qty) or duplicate within
// the file itself.
export function dedupeTrades(parsed: ParsedTrade[], existing: ExistingKey[]): ParsedTrade[] {
  const seen = new Set(existing.map(key));
  const out: ParsedTrade[] = [];
  for (const trade of parsed) {
    const k = key(trade);
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(trade);
  }
  return out;
}
