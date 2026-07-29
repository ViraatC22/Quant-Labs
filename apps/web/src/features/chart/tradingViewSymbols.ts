// Mapping from Quant Labs symbols to TradingView ticker identifiers.
//
// This is a *display* mapping only. The TradingView widget draws TradingView's
// own data; Quant Labs prices come from services/market_data.py. The two are
// different feeds and will not agree tick for tick.
//
// One case where they disagree by a lot: XAUUSD. Quant Labs serves it from the
// front-month gold future (GC=F) because Yahoo has no spot metal series, while
// TradingView shows true spot. The gap is the futures basis — tens of dollars,
// not rounding. `divergesFromOurFeed` marks those so the UI can say so instead
// of leaving a user to discover it mid-trade.

export type TradingViewSymbol = {
  ticker: string;
  /** True when the widget is charting a materially different instrument. */
  divergesFromOurFeed?: boolean;
  divergenceNote?: string;
};

const MAP: Record<string, TradingViewSymbol> = {
  EURUSD: { ticker: "FX:EURUSD" },
  GBPUSD: { ticker: "FX:GBPUSD" },
  USDJPY: { ticker: "FX:USDJPY" },
  AUDUSD: { ticker: "FX:AUDUSD" },
  NZDUSD: { ticker: "FX:NZDUSD" },
  USDCAD: { ticker: "FX:USDCAD" },
  USDCHF: { ticker: "FX:USDCHF" },
  EURGBP: { ticker: "FX:EURGBP" },
  EURJPY: { ticker: "FX:EURJPY" },
  GBPJPY: { ticker: "FX:GBPJPY" },
  XAUUSD: {
    ticker: "OANDA:XAUUSD",
    divergesFromOurFeed: true,
    divergenceNote:
      "The chart shows spot gold; Quant Labs prices this from the front-month " +
      "future (GC=F). Expect a basis difference of tens of dollars."
  },
  XAGUSD: {
    ticker: "OANDA:XAGUSD",
    divergesFromOurFeed: true,
    divergenceNote:
      "The chart shows spot silver; Quant Labs prices this from the front-month " +
      "future (SI=F). Expect a basis difference."
  },
  // Index futures. Broker-style aliases point at the same contract so a user
  // typing US100 or NAS100 lands on the chart they expect.
  US500: { ticker: "CME_MINI:ES1!" },
  SPX500: { ticker: "CME_MINI:ES1!" },
  SP500: { ticker: "CME_MINI:ES1!" },
  US100: { ticker: "CME_MINI:NQ1!" },
  NAS100: { ticker: "CME_MINI:NQ1!" },
  NASDAQ: { ticker: "CME_MINI:NQ1!" },
  US30: { ticker: "CBOT_MINI:YM1!" },
  DOW: { ticker: "CBOT_MINI:YM1!" },
  US2000: { ticker: "CME_MINI:RTY1!" },
  RUSSELL: { ticker: "CME_MINI:RTY1!" },
  // Cash indices.
  SPX: { ticker: "SP:SPX" },
  NDX: { ticker: "NASDAQ:NDX" },
  DJI: { ticker: "DJ:DJI" },
  DAX: { ticker: "XETR:DAX" },
  GER40: { ticker: "XETR:DAX" },
  UK100: { ticker: "FTSE:UKX" },
  FTSE: { ticker: "FTSE:UKX" },
  JP225: { ticker: "TVC:NI225" },
  NIKKEI: { ticker: "TVC:NI225" },
  // Commodities. These chart the same futures contract Quant Labs prices from,
  // so unlike spot metals there is no basis divergence to warn about.
  GOLD: { ticker: "COMEX:GC1!" },
  SILVER: { ticker: "COMEX:SI1!" },
  PLATINUM: { ticker: "NYMEX:PL1!" },
  COPPER: { ticker: "COMEX:HG1!" },
  OIL: { ticker: "NYMEX:CL1!" },
  WTI: { ticker: "NYMEX:CL1!" },
  USOIL: { ticker: "NYMEX:CL1!" },
  BRENT: { ticker: "NYMEX:BZ1!" },
  UKOIL: { ticker: "NYMEX:BZ1!" },
  NATGAS: { ticker: "NYMEX:NG1!" },
  NGAS: { ticker: "NYMEX:NG1!" },
  NG: { ticker: "NYMEX:NG1!" },
  HG: { ticker: "COMEX:HG1!" },
  PL: { ticker: "NYMEX:PL1!" },
  BZ: { ticker: "NYMEX:BZ1!" },
  BTC: { ticker: "CRYPTO:BTCUSD" },
  ETH: { ticker: "CRYPTO:ETHUSD" },
  ES: { ticker: "CME_MINI:ES1!" },
  MES: { ticker: "CME_MINI:MES1!" },
  NQ: { ticker: "CME_MINI:NQ1!" },
  MNQ: { ticker: "CME_MINI:MNQ1!" },
  YM: { ticker: "CBOT_MINI:YM1!" },
  RTY: { ticker: "CME_MINI:RTY1!" },
  CL: { ticker: "NYMEX:CL1!" },
  GC: { ticker: "COMEX:GC1!" },
  SI: { ticker: "COMEX:SI1!" }
};

/**
 * Resolve a Quant Labs symbol for the widget. Unmapped symbols are passed
 * through bare — TradingView resolves most equity tickers on its own.
 */
export function toTradingViewSymbol(symbol: string): TradingViewSymbol {
  const normalized = symbol.trim().toUpperCase().replace("/", "");
  return MAP[normalized] ?? { ticker: normalized };
}
