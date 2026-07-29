// Wire types for the session desk endpoints (`/api/v1/desk/*`).
// These mirror app/schemas/desk.py; keep them in step with that module.

export type BiasDirection = "bullish" | "bearish" | "neutral";

export type BiasSignal = {
  label: string;
  /** bullish/bearish/neutral for directional signals; confirming/undercutting for confirmation ones. */
  direction: string;
  value: number;
  weight: number;
  detail: string;
  /** "directional" signals vote on the call; "confirmation" signals only adjust confidence. */
  role: "directional" | "confirmation" | string;
};

export type AssetClass = "fx" | "index" | "commodity" | "crypto" | "equity" | string;

export type InstrumentBias = {
  symbol: string;
  /** Descriptive grouping only; the bias engine is asset-class agnostic. */
  assetClass: AssetClass;
  direction: BiasDirection;
  /** Integer percent, capped server-side. Derived from data, never model-asserted. */
  confidence: number;
  strength: number;
  agreement: number;
  coverage: number;
  lastPrice: number;
  changePercent: number;
  signals: BiasSignal[];
  explanation: string;
  explanationMode: "derived" | "model" | string;
  asOf: string;
  provider: string;
  /** top_of_book | last_trade | indicative_mid — see market_data.PRICE_BASIS_*. */
  priceBasis: string;
  sampleSize: number;
  delayed: boolean;
  stale: boolean;
  proxyNote: string | null;
  limitations: string[];
  writerProviderId: string | null;
  writerModel: string | null;
  /** Retrieved headlines for this instrument (data, not prose). */
  news: NewsItem[];
  /** Engine output before calibration. `confidence` is the display value. */
  rawConfidence: number;
  calibrationApplied: boolean;
  calibrationSample: number;
  calibrationNote: string;
};

export type CalibrationBucket = {
  bucket: string;
  graded: number;
  correct: number;
  hitRate: number | null;
};

export type CalibrationStats = {
  buckets: CalibrationBucket[];
  decisiveShare: number | null;
  /** What a coin-flip would have scored on the same graded windows. */
  luckBaseline: number | null;
  totalGraded: number;
  minSample: number;
};

export type MacroDesk = {
  instruments: InstrumentBias[];
  /** Symbol -> reason it could not be loaded. Shown rather than silently dropped. */
  unavailable: Record<string, string>;
  generatedAt: string;
};

export type SessionPhase = "pre_market" | "open" | "after_hours" | "closed";

export type SessionState = {
  key: string;
  label: string;
  timezone: string;
  phase: SessionPhase;
  phaseLabel: string;
  localTime: string;
  isOpen: boolean;
  nextPhase: SessionPhase;
  nextPhaseLabel: string;
  nextTransitionAt: string;
  secondsToNext: number;
  countdown: string;
};

export type NewsItem = {
  title: string;
  url: string;
  source: string;
  publishedAt: string | null;
  ageLabel: string | null;
  summary: string | null;
  imageUrl: string | null;
  symbol: string | null;
};

export type NewsFeed = {
  items: NewsItem[];
  available: boolean;
  stale: boolean;
  reason: string | null;
  provider: string;
};

export type CurrencyStrength = {
  currency: string;
  /** Mean signed contribution across every pair the currency appears in. */
  score: number;
  /** Pairs behind the score. One pair is that pair restated, not a reading. */
  pairs: number;
  contributions: Array<[string, number]>;
};

export type FlowEntry = {
  symbol: string;
  changePercent: number;
  assetClass: AssetClass;
};

export type StrengthSnapshot = {
  currencies: CurrencyStrength[];
  flow: FlowEntry[];
  unavailable: Record<string, string>;
  window: string;
  generatedAt: string;
};

export type BriefingItem = {
  symbol: string;
  direction: BiasDirection;
  confidence: number;
  band: "HIGH" | "MEDIUM" | "LOW" | string;
  text: string;
  asOf: string;
};

export type Briefing = {
  headline: string;
  summary: string;
  regime: string;
  tone: string;
  items: BriefingItem[];
  generatedAt: string;
  caveats: string[];
  /** Genuine transitions since the last stored reading; empty on a first look. */
  changes: string[];
};
