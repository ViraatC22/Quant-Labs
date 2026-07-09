import { describe, expect, it } from "vitest";

import { dedupeTrades, parseCsvRows, parseCsvTrades } from "@/lib/csvImport";

describe("csv import", () => {
  it("parses quoted fields and CRLF", () => {
    const rows = parseCsvRows('a,b\r\n"x,y",z\r\n');
    expect(rows).toEqual([
      ["a", "b"],
      ["x,y", "z"]
    ]);
  });

  it("maps common broker columns and normalizes side/date/price", () => {
    const csv = [
      "Symbol,Action,Qty,Entry Price,Exit Price,Commission,Date",
      "aapl,Buy,10,$210.00,214,1.00,07/01/2026",
      "TSLA,Sell,15,260,256,1,2026-07-06"
    ].join("\n");
    const { trades, errors } = parseCsvTrades(csv);
    expect(errors).toHaveLength(0);
    expect(trades).toHaveLength(2);
    expect(trades[0]).toMatchObject({
      symbol: "AAPL",
      side: "long",
      quantity: 10,
      entryPrice: 210,
      exitPrice: 214,
      fees: 1,
      entryDate: "2026-07-01"
    });
    expect(trades[1]).toMatchObject({ symbol: "TSLA", side: "short", entryDate: "2026-07-06" });
  });

  it("reports a clear error when required columns are missing", () => {
    const { trades, errors } = parseCsvTrades("foo,bar\n1,2");
    expect(trades).toHaveLength(0);
    expect(errors[0]).toMatch(/symbol/);
  });

  it("skips invalid rows but keeps valid ones", () => {
    const csv = "symbol,qty,price\nAAPL,10,100\n,5,100\nMSFT,0,100\nNVDA,3,120";
    const { trades, errors } = parseCsvTrades(csv);
    expect(trades.map((t) => t.symbol)).toEqual(["AAPL", "NVDA"]);
    expect(errors).toHaveLength(2);
  });

  it("dedupes against existing trades and within the file", () => {
    const csv = "symbol,qty,price,date\nAAPL,10,100,2026-07-01\nAAPL,10,100,2026-07-01\nSPY,5,400,2026-07-02";
    const { trades } = parseCsvTrades(csv);
    const deduped = dedupeTrades(trades, [
      { symbol: "SPY", entryDate: "2026-07-02", entryPrice: 400, quantity: 5 }
    ]);
    // Both AAPL rows collapse to one; the SPY row already exists.
    expect(deduped.map((t) => t.symbol)).toEqual(["AAPL"]);
  });
});
