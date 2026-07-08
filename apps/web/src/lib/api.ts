// Typed client for the Trading Intelligence OS API.
//
// The workspace is local-first: when the API is reachable it becomes the source
// of truth (data persists to Postgres/SQLite); when it is offline the UI falls
// back to browser storage. Every call maps between the API's rich schema and the
// compact shapes the UI works with, so nothing is lost on a round trip.

import type {
  AiRouterStatus,
  GeneratedStrategyInfo,
  JournalEntry,
  MarketQuote,
  SourceDetails,
  StrategyEvaluation,
  TradeEntry,
  TradeRecommendation,
  VaultItem
} from "@/lib/types";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Json = Record<string, unknown>;

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isUuid(value: string | undefined | null): value is string {
  return typeof value === "string" && UUID_RE.test(value);
}

// Real timestamps when the ticket supplies them, date resolution otherwise.
// A value already carrying a time component ("2026-07-08T14:30:00Z") is passed
// through unchanged; a bare date ("2026-07-08") is anchored to 00:00Z and the
// trade is flagged `time_resolution: "date"` so intraday/session analytics can
// tell true execution times from placeholders instead of trusting midnight.
function hasTimeComponent(value: string): boolean {
  return value.includes("T");
}

function tradeEntryTime(trade: Pick<TradeEntry, "entryDate">): string {
  return hasTimeComponent(trade.entryDate) ? trade.entryDate : `${trade.entryDate}T00:00:00Z`;
}

function tradeExitTime(trade: Pick<TradeEntry, "entryDate">): string {
  return tradeEntryTime(trade);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }
  });
  if (!response.ok) {
    throw new Error(`API ${init?.method ?? "GET"} ${path} failed: ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function checkHealth(signal?: AbortSignal): Promise<boolean> {
  try {
    const response = await fetch(`${apiBaseUrl}/health`, { cache: "no-store", signal });
    return response.ok;
  } catch {
    return false;
  }
}

export async function getAiRouterStatus(): Promise<AiRouterStatus> {
  return request<AiRouterStatus>("/api/v1/vault/ai/providers");
}

// ---------------------------------------------------------------- trades
type TradeDto = {
  id: string;
  symbol: string;
  asset_class: string;
  side: string;
  entry_time: string;
  entry_price: string;
  exit_price: string | null;
  quantity: string;
  contract_multiplier: string;
  fees: string;
  timeframe: string | null;
  session: string | null;
  planned_risk_amount: string | null;
  emotional_state_after: string | null;
  journal_summary: string | null;
  metadata: Json;
  created_at: string;
};

function metaString(meta: Json, key: string) {
  const value = meta[key];
  return typeof value === "string" && value ? value : null;
}

function metaNumber(meta: Json, key: string) {
  const value = meta[key];
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function tradeMetadata(trade: Partial<TradeEntry>): Json {
  return {
    strategy: trade.strategy,
    setup: trade.setup,
    emotion: trade.emotion,
    notes: trade.notes,
    status: trade.exitPrice === null ? "open" : trade.exitPrice === undefined ? trade.status : "closed",
    currentPrice: trade.currentPrice,
    quoteProvider: trade.quoteProvider,
    quoteTime: trade.quoteTime,
    quoteSymbol: trade.quoteSymbol,
    orderType: trade.orderType ?? "manual",
    paperOrder: Boolean(trade.paperOrder),
    contractMultiplier: trade.contractMultiplier,
    riskAmount: trade.riskAmount,
    stopPrice: trade.stopPrice,
    targetPrice: trade.targetPrice,
    exchange: trade.exchange,
    expirationDate: trade.expirationDate,
    optionType: trade.optionType,
    strikePrice: trade.strikePrice,
    underlyingSymbol: trade.underlyingSymbol,
    delta: trade.delta,
    impliedVolatility: trade.impliedVolatility,
    futuresContract: trade.futuresContract,
    tickSize: trade.tickSize,
    tickValue: trade.tickValue,
    leverage: trade.leverage,
    timeResolution: hasTimeComponent(trade.entryDate ?? "") ? "datetime" : "date"
  };
}

function tradeFromDto(dto: TradeDto): TradeEntry {
  const meta = dto.metadata ?? {};
  return {
    id: dto.id,
    symbol: dto.symbol,
    assetClass: dto.asset_class || metaString(meta, "assetClass") || "equity",
    side: dto.side === "short" ? "short" : "long",
    entryDate: dto.entry_time.slice(0, 10),
    entryPrice: Number(dto.entry_price),
    exitPrice: dto.exit_price === null ? null : Number(dto.exit_price),
    currentPrice: typeof meta.currentPrice === "number" ? meta.currentPrice : null,
    quoteProvider: metaString(meta, "quoteProvider"),
    quoteTime: metaString(meta, "quoteTime"),
    quoteSymbol: metaString(meta, "quoteSymbol"),
    status: dto.exit_price === null ? "open" : "closed",
    orderType: typeof meta.orderType === "string" ? meta.orderType : "manual",
    paperOrder: Boolean(meta.paperOrder),
    quantity: Number(dto.quantity),
    fees: Number(dto.fees),
    contractMultiplier:
      dto.contract_multiplier != null ? Number(dto.contract_multiplier) : metaNumber(meta, "contractMultiplier"),
    riskAmount:
      dto.planned_risk_amount === null ? metaNumber(meta, "riskAmount") : Number(dto.planned_risk_amount),
    stopPrice: metaNumber(meta, "stopPrice"),
    targetPrice: metaNumber(meta, "targetPrice"),
    timeframe: dto.timeframe ?? metaString(meta, "timeframe"),
    session: dto.session ?? metaString(meta, "session"),
    exchange: metaString(meta, "exchange"),
    expirationDate: metaString(meta, "expirationDate"),
    optionType: metaString(meta, "optionType"),
    strikePrice: metaNumber(meta, "strikePrice"),
    underlyingSymbol: metaString(meta, "underlyingSymbol"),
    delta: metaNumber(meta, "delta"),
    impliedVolatility: metaNumber(meta, "impliedVolatility"),
    futuresContract: metaString(meta, "futuresContract"),
    tickSize: metaNumber(meta, "tickSize"),
    tickValue: metaNumber(meta, "tickValue"),
    leverage: metaNumber(meta, "leverage"),
    strategy: String(meta.strategy ?? ""),
    setup: String(meta.setup ?? ""),
    emotion: String(meta.emotion ?? dto.emotional_state_after ?? "focused"),
    notes: String(meta.notes ?? dto.journal_summary ?? ""),
    createdAt: dto.created_at
  };
}

export async function listTrades(): Promise<TradeEntry[]> {
  const rows = await request<TradeDto[]>("/api/v1/trades");
  return rows.map(tradeFromDto);
}

export async function createTrade(trade: TradeEntry): Promise<TradeEntry> {
  const multiplier = trade.contractMultiplier && trade.contractMultiplier > 0 ? trade.contractMultiplier : 1;
  const body = {
    // Send the client UUID so an offline-created trade replays idempotently.
    id: isUuid(trade.id) ? trade.id : undefined,
    symbol: trade.symbol,
    asset_class: trade.assetClass ?? "equity",
    side: trade.side,
    entry_time: tradeEntryTime(trade),
    entry_price: String(trade.entryPrice),
    exit_price: trade.exitPrice === null ? null : String(trade.exitPrice),
    exit_time: trade.exitPrice === null ? null : tradeExitTime(trade),
    quantity: String(trade.quantity),
    contract_multiplier: String(multiplier),
    fees: String(trade.fees),
    timeframe: trade.timeframe || null,
    session: trade.session || null,
    planned_risk_amount: trade.riskAmount === null || trade.riskAmount === undefined ? null : String(trade.riskAmount),
    emotional_state_after: trade.emotion || null,
    journal_summary: trade.notes || null,
    metadata: {
      ...tradeMetadata(trade),
      assetClass: trade.assetClass ?? "equity",
      timeframe: trade.timeframe,
      session: trade.session
    }
  };
  const dto = await request<TradeDto>("/api/v1/trades", {
    method: "POST",
    body: JSON.stringify(body)
  });
  return tradeFromDto(dto);
}

export async function updateTrade(id: string, trade: Partial<TradeEntry>): Promise<TradeEntry> {
  const metadata: Json = {};
  if (trade.strategy !== undefined) metadata.strategy = trade.strategy;
  if (trade.setup !== undefined) metadata.setup = trade.setup;
  if (trade.emotion !== undefined) metadata.emotion = trade.emotion;
  if (trade.notes !== undefined) metadata.notes = trade.notes;
  if (trade.status !== undefined) metadata.status = trade.status;
  if (trade.exitPrice !== undefined) metadata.status = trade.exitPrice === null ? "open" : "closed";
  if (trade.currentPrice !== undefined) metadata.currentPrice = trade.currentPrice;
  if (trade.quoteProvider !== undefined) metadata.quoteProvider = trade.quoteProvider;
  if (trade.quoteTime !== undefined) metadata.quoteTime = trade.quoteTime;
  if (trade.quoteSymbol !== undefined) metadata.quoteSymbol = trade.quoteSymbol;
  if (trade.orderType !== undefined) metadata.orderType = trade.orderType;
  if (trade.paperOrder !== undefined) metadata.paperOrder = trade.paperOrder;
  if (trade.assetClass !== undefined) metadata.assetClass = trade.assetClass;
  if (trade.contractMultiplier !== undefined) metadata.contractMultiplier = trade.contractMultiplier;
  if (trade.riskAmount !== undefined) metadata.riskAmount = trade.riskAmount;
  if (trade.stopPrice !== undefined) metadata.stopPrice = trade.stopPrice;
  if (trade.targetPrice !== undefined) metadata.targetPrice = trade.targetPrice;
  if (trade.timeframe !== undefined) metadata.timeframe = trade.timeframe;
  if (trade.session !== undefined) metadata.session = trade.session;
  if (trade.exchange !== undefined) metadata.exchange = trade.exchange;
  if (trade.expirationDate !== undefined) metadata.expirationDate = trade.expirationDate;
  if (trade.optionType !== undefined) metadata.optionType = trade.optionType;
  if (trade.strikePrice !== undefined) metadata.strikePrice = trade.strikePrice;
  if (trade.underlyingSymbol !== undefined) metadata.underlyingSymbol = trade.underlyingSymbol;
  if (trade.delta !== undefined) metadata.delta = trade.delta;
  if (trade.impliedVolatility !== undefined) metadata.impliedVolatility = trade.impliedVolatility;
  if (trade.futuresContract !== undefined) metadata.futuresContract = trade.futuresContract;
  if (trade.tickSize !== undefined) metadata.tickSize = trade.tickSize;
  if (trade.tickValue !== undefined) metadata.tickValue = trade.tickValue;
  if (trade.leverage !== undefined) metadata.leverage = trade.leverage;

  const body: Json = {};
  if (trade.exitPrice !== undefined) body.exit_price = trade.exitPrice === null ? null : String(trade.exitPrice);
  if (trade.fees !== undefined) body.fees = String(trade.fees);
  if (trade.riskAmount !== undefined) {
    body.planned_risk_amount = trade.riskAmount === null ? null : String(trade.riskAmount);
  }
  if (trade.emotion !== undefined) body.emotional_state_after = trade.emotion;
  if (trade.notes !== undefined) body.journal_summary = trade.notes;
  if (Object.keys(metadata).length) body.metadata = metadata;

  const dto = await request<TradeDto>(`/api/v1/trades/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body)
  });
  return tradeFromDto(dto);
}

export async function deleteTrade(id: string): Promise<void> {
  await request<void>(`/api/v1/trades/${id}`, { method: "DELETE" });
}

export async function getQuote(symbol: string): Promise<MarketQuote> {
  return request<MarketQuote>(`/api/v1/trades/quotes/${encodeURIComponent(symbol)}`);
}

export async function listTradeRecommendations(): Promise<TradeRecommendation[]> {
  return request<TradeRecommendation[]>("/api/v1/trades/recommendations");
}

export async function getOptimalStrategy(): Promise<StrategyEvaluation> {
  return request<StrategyEvaluation>("/api/v1/trades/strategy/optimal");
}

export async function evaluateStrategyIdea(
  idea: string,
  symbol?: string
): Promise<StrategyEvaluation> {
  return request<StrategyEvaluation>("/api/v1/trades/strategy/evaluate", {
    method: "POST",
    body: JSON.stringify({ idea, symbol: symbol || null, save_journal: true })
  });
}

// --------------------------------------------------------------- journal
type JournalDto = {
  id: string;
  entry_date: string;
  title: string;
  body: string;
  emotional_state: string | null;
  tags: string[];
  metadata: Json;
  created_at: string;
};

function journalFromDto(dto: JournalDto): JournalEntry {
  const meta = dto.metadata ?? {};
  return {
    id: dto.id,
    date: dto.entry_date,
    title: dto.title,
    emotion: dto.emotional_state ?? "focused",
    routineDone: Boolean(meta.routineDone),
    body: dto.body,
    tags: dto.tags ?? [],
    createdAt: dto.created_at
  };
}

export async function listJournal(): Promise<JournalEntry[]> {
  const rows = await request<JournalDto[]>("/api/v1/vault/journal-entries");
  return rows.map(journalFromDto);
}

export async function createJournal(entry: JournalEntry): Promise<JournalEntry> {
  const body = {
    entry_date: entry.date,
    title: entry.title,
    body: entry.body,
    emotional_state: entry.emotion,
    tags: entry.tags,
    metadata: { routineDone: entry.routineDone }
  };
  const dto = await request<JournalDto>("/api/v1/vault/journal-entries", {
    method: "POST",
    body: JSON.stringify(body)
  });
  return journalFromDto(dto);
}

export async function updateJournal(id: string, patch: Partial<JournalEntry>): Promise<JournalEntry> {
  const body: Json = {};
  if (patch.date !== undefined) body.entry_date = patch.date;
  if (patch.title !== undefined) body.title = patch.title;
  if (patch.body !== undefined) body.body = patch.body;
  if (patch.emotion !== undefined) body.emotional_state = patch.emotion;
  if (patch.tags !== undefined) body.tags = patch.tags;
  if (patch.routineDone !== undefined) body.metadata = { routineDone: patch.routineDone };
  const dto = await request<JournalDto>(`/api/v1/vault/journal-entries/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body)
  });
  return journalFromDto(dto);
}

export async function deleteJournal(id: string): Promise<void> {
  await request<void>(`/api/v1/vault/journal-entries/${id}`, { method: "DELETE" });
}

// ------------------------------------------------------------- documents
type DocumentDto = {
  id: string;
  title: string;
  document_type: string;
  uri: string | null;
  content_text: string | null;
  metadata: Json;
  created_at: string;
};

function documentFromDto(dto: DocumentDto): VaultItem {
  const meta = dto.metadata ?? {};
  return {
    id: dto.id,
    title: dto.title,
    kind: dto.document_type,
    source: dto.uri ?? String(meta.source ?? ""),
    body: dto.content_text ?? "",
    tags: (meta.tags as string[]) ?? [],
    aiTags: (meta.aiTags as string[]) ?? (meta.generated_tags as string[]) ?? [],
    technicalTags:
      (meta.technical_tags as string[]) ??
      (meta.technicalTags as string[]) ??
      ((meta.strategy_info as GeneratedStrategyInfo | null)?.technical_tags ?? []),
    technicalProfile:
      (meta.technical_profile as Record<string, string[]>) ??
      (meta.technicalProfile as Record<string, string[]>) ??
      ((meta.strategy_info as GeneratedStrategyInfo | null)?.technical_profile ?? {}),
    sourceDetails:
      (meta.sourceDetails as SourceDetails | null) ??
      (meta.source_details as SourceDetails | null) ??
      null,
    strategyInfo:
      (meta.strategyInfo as GeneratedStrategyInfo | null) ??
      (meta.strategy_info as GeneratedStrategyInfo | null) ??
      null,
    learningSummary:
      (meta.learned_memory as VaultItem["learningSummary"] | null) ??
      (meta.learningSummary as VaultItem["learningSummary"] | null) ??
      null,
    createdAt: dto.created_at
  };
}

export async function listDocuments(): Promise<VaultItem[]> {
  const rows = await request<DocumentDto[]>("/api/v1/vault/documents");
  return rows.map(documentFromDto);
}

export async function createDocument(item: VaultItem): Promise<VaultItem> {
  const body = {
    title: item.title,
    document_type: item.kind,
    uri: item.source?.startsWith("http") ? item.source : null,
    content_text: item.body,
    metadata: {
      source: item.source,
      tags: item.tags,
      aiTags: item.aiTags ?? [],
      technicalTags: item.technicalTags ?? [],
      technicalProfile: item.technicalProfile ?? {},
      technical_tags: item.technicalTags ?? [],
      technical_profile: item.technicalProfile ?? {},
      sourceDetails: item.sourceDetails ?? null,
      source_details: item.sourceDetails ?? null,
      strategyInfo: item.strategyInfo ?? null,
      strategy_info: item.strategyInfo ?? null,
      generated_tags: item.aiTags ?? [],
      learned_memory: item.learningSummary ?? null
    }
  };
  const dto = await request<DocumentDto>("/api/v1/vault/documents", {
    method: "POST",
    body: JSON.stringify(body)
  });
  return documentFromDto(dto);
}

export async function updateDocument(id: string, patch: Partial<VaultItem>): Promise<VaultItem> {
  const body: Json = {};
  if (patch.title !== undefined) body.title = patch.title;
  if (patch.kind !== undefined) body.document_type = patch.kind;
  if (patch.body !== undefined) body.content_text = patch.body;
  if (patch.tags !== undefined) body.metadata = { tags: patch.tags };
  const dto = await request<DocumentDto>(`/api/v1/vault/documents/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body)
  });
  return documentFromDto(dto);
}

export async function deleteDocument(id: string): Promise<void> {
  await request<void>(`/api/v1/vault/documents/${id}`, { method: "DELETE" });
}
