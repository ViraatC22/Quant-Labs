// Shared local-first domain types used by the workspace UI and the API client.

export type GeneratedStrategyInfo = {
  name?: string | null;
  summary?: string | null;
  setup?: string | null;
  entry_rules?: string[];
  exit_rules?: string[];
  risk_rules?: string[];
  timeframe?: string | null;
  indicators?: string[];
  market?: string | null;
  technical_tags?: string[];
  technical_profile?: Record<string, string[]>;
  confidence?: number;
};

export type SourceLearningSummary = {
  chunk_count: number;
  node_count: number;
  edge_count: number;
  technical_count?: number;
  strategy?: string | null;
  map_labels: string[];
  status: string;
};

export type SourceDetails = {
  provider?: string;
  arxiv_id?: string;
  title?: string;
  authors?: string[];
  abstract?: string;
  submitted?: string | null;
  updated?: string | null;
  comments?: string | null;
  doi?: string | null;
  primary_category?: string | null;
  subjects?: string[];
  abs_url?: string;
  pdf_url?: string;
  implementation_notes?: string[];
};

export type VaultItem = {
  id: string;
  title: string;
  kind: string;
  source: string;
  body: string;
  tags: string[];
  aiTags?: string[];
  technicalTags?: string[];
  technicalProfile?: Record<string, string[]>;
  sourceDetails?: SourceDetails | null;
  strategyInfo?: GeneratedStrategyInfo | null;
  learningSummary?: SourceLearningSummary | null;
  createdAt: string;
};

export type AiProviderStatus = {
  id: string;
  label: string;
  configured: boolean;
  model: string;
  priority: number;
  protocol: string;
};

export type AiRouterStatus = {
  mode: "auto" | "local" | "off" | string;
  active_provider_id?: string | null;
  providers: AiProviderStatus[];
};

export type JournalEntry = {
  id: string;
  date: string;
  title: string;
  emotion: string;
  routineDone: boolean;
  body: string;
  tags: string[];
  createdAt: string;
};

export type TradeAssetClass = "equity" | "option" | "future" | "crypto" | "forex";

export type TradeEntry = {
  id: string;
  symbol: string;
  assetClass?: TradeAssetClass | string;
  side: "long" | "short";
  entryDate: string;
  entryPrice: number;
  exitPrice: number | null;
  currentPrice?: number | null;
  quoteProvider?: string | null;
  quoteTime?: string | null;
  quoteSymbol?: string | null;
  status?: "open" | "closed";
  orderType?: "manual" | "paper_market" | string;
  paperOrder?: boolean;
  quantity: number;
  fees: number;
  contractMultiplier?: number | null;
  riskAmount?: number | null;
  stopPrice?: number | null;
  targetPrice?: number | null;
  timeframe?: string | null;
  session?: string | null;
  exchange?: string | null;
  expirationDate?: string | null;
  optionType?: "call" | "put" | string | null;
  strikePrice?: number | null;
  underlyingSymbol?: string | null;
  delta?: number | null;
  impliedVolatility?: number | null;
  futuresContract?: string | null;
  tickSize?: number | null;
  tickValue?: number | null;
  leverage?: number | null;
  strategy: string;
  setup: string;
  emotion: string;
  notes: string;
  createdAt: string;
};

export type TradeRecommendation = {
  id: string;
  title: string;
  action: string;
  strategy?: string | null;
  setup?: string | null;
  confidence: number;
  technical_tags: string[];
  rationale: string;
  risk_notes: string[];
  evidence: string[];
  draft?: {
    symbol?: string;
    asset_class?: TradeAssetClass | string;
    quote_symbol?: string;
    side?: "long" | "short";
    strategy?: string;
    setup?: string;
    emotion?: string;
    quantity?: string;
    fees?: string;
    entry_price?: string;
    exit_price?: string;
    contract_multiplier?: string;
    risk_amount?: string;
    stop_price?: string;
    target_price?: string;
    timeframe?: string;
    session?: string;
    exchange?: string;
    expiration_date?: string;
    option_type?: "call" | "put" | string;
    strike_price?: string;
    underlying_symbol?: string;
    delta?: string;
    implied_volatility?: string;
    futures_contract?: string;
    tick_size?: string;
    tick_value?: string;
    leverage?: string;
    price_source?: string;
    price_time?: string;
    notes?: string;
    quick_text?: string;
  };
};

export type MarketQuote = {
  symbol: string;
  provider_symbol: string;
  provider: string;
  last_price: string;
  previous_close?: string | null;
  currency?: string | null;
  market_time?: string | null;
  delayed: boolean;
};

export type StrategyEvaluation = {
  title: string;
  decision: "beneficial" | "observe" | "weakens-edge" | "needs-structure" | string;
  score: number;
  confidence: number;
  rationale: string;
  technical_tags: string[];
  technical_profile: Record<string, string[]>;
  included: string[];
  excluded: string[];
  draft: NonNullable<TradeRecommendation["draft"]>;
  journal_entry_id?: string | null;
};

export type WorkspaceState = {
  vault: VaultItem[];
  journal: JournalEntry[];
  trades: TradeEntry[];
};
