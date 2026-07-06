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

export type TradeEntry = {
  id: string;
  symbol: string;
  side: "long" | "short";
  entryDate: string;
  entryPrice: number;
  exitPrice: number;
  quantity: number;
  fees: number;
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
};

export type WorkspaceState = {
  vault: VaultItem[];
  journal: JournalEntry[];
  trades: TradeEntry[];
};
