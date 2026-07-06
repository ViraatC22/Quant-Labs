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
  confidence?: number;
};

export type VaultItem = {
  id: string;
  title: string;
  kind: string;
  source: string;
  body: string;
  tags: string[];
  aiTags?: string[];
  strategyInfo?: GeneratedStrategyInfo | null;
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

export type WorkspaceState = {
  vault: VaultItem[];
  journal: JournalEntry[];
  trades: TradeEntry[];
};
