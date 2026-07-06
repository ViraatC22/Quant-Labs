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
  TradeEntry,
  TradeRecommendation,
  VaultItem
} from "@/lib/types";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Json = Record<string, unknown>;

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
  side: string;
  entry_time: string;
  entry_price: string;
  exit_price: string | null;
  quantity: string;
  fees: string;
  emotional_state_after: string | null;
  journal_summary: string | null;
  metadata: Json;
  created_at: string;
};

function tradeFromDto(dto: TradeDto): TradeEntry {
  const meta = dto.metadata ?? {};
  return {
    id: dto.id,
    symbol: dto.symbol,
    side: dto.side === "short" ? "short" : "long",
    entryDate: dto.entry_time.slice(0, 10),
    entryPrice: Number(dto.entry_price),
    exitPrice: Number(dto.exit_price ?? 0),
    quantity: Number(dto.quantity),
    fees: Number(dto.fees),
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
  const body = {
    symbol: trade.symbol,
    side: trade.side,
    entry_time: `${trade.entryDate}T00:00:00Z`,
    entry_price: String(trade.entryPrice),
    exit_price: String(trade.exitPrice),
    quantity: String(trade.quantity),
    fees: String(trade.fees),
    emotional_state_after: trade.emotion || null,
    journal_summary: trade.notes || null,
    metadata: {
      strategy: trade.strategy,
      setup: trade.setup,
      emotion: trade.emotion,
      notes: trade.notes
    }
  };
  const dto = await request<TradeDto>("/api/v1/trades", {
    method: "POST",
    body: JSON.stringify(body)
  });
  return tradeFromDto(dto);
}

export async function deleteTrade(id: string): Promise<void> {
  await request<void>(`/api/v1/trades/${id}`, { method: "DELETE" });
}

export async function listTradeRecommendations(): Promise<TradeRecommendation[]> {
  return request<TradeRecommendation[]>("/api/v1/trades/recommendations");
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
      (meta.technicalTags as string[]) ??
      (meta.technical_tags as string[]) ??
      ((meta.strategy_info as GeneratedStrategyInfo | null)?.technical_tags ?? []),
    technicalProfile:
      (meta.technicalProfile as Record<string, string[]>) ??
      (meta.technical_profile as Record<string, string[]>) ??
      ((meta.strategy_info as GeneratedStrategyInfo | null)?.technical_profile ?? {}),
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

export async function deleteDocument(id: string): Promise<void> {
  await request<void>(`/api/v1/vault/documents/${id}`, { method: "DELETE" });
}
