// Offline write queue for the local-first workspace.
//
// The old behaviour flipped the whole app "offline" on any API error and, on
// the next reload, overwrote local state entirely from the server — silently
// destroying anything created while "offline". This module fixes that: every
// mutation is optimistically applied locally and, if the API cannot be reached,
// recorded in a durable queue (localStorage). When the API is reachable the
// queue is replayed in order before hydrating from the server, so nothing is
// lost and a genuine server rejection is surfaced instead of hidden.

import { ApiError } from "@/lib/api";
import type { JournalEntry, TradeEntry, VaultItem } from "@/lib/types";

export type SyncCollection = "trades" | "journal" | "vault";

export type SyncOp =
  | { opId: string; type: "create"; collection: "trades"; record: TradeEntry }
  | { opId: string; type: "create"; collection: "journal"; record: JournalEntry }
  | { opId: string; type: "create"; collection: "vault"; record: VaultItem }
  | { opId: string; type: "update"; collection: "trades"; id: string; patch: Partial<TradeEntry> }
  | { opId: string; type: "update"; collection: "journal"; id: string; patch: Partial<JournalEntry> }
  | { opId: string; type: "update"; collection: "vault"; id: string; patch: Partial<VaultItem> }
  | { opId: string; type: "delete"; collection: SyncCollection; id: string };

export type SyncHandlers = {
  createTrade: (record: TradeEntry) => Promise<TradeEntry>;
  createJournal: (record: JournalEntry) => Promise<JournalEntry>;
  createDocument: (record: VaultItem) => Promise<VaultItem>;
  updateTrade: (id: string, patch: Partial<TradeEntry>) => Promise<TradeEntry>;
  updateJournal: (id: string, patch: Partial<JournalEntry>) => Promise<JournalEntry>;
  updateDocument: (id: string, patch: Partial<VaultItem>) => Promise<VaultItem>;
  remove: (collection: SyncCollection, id: string) => Promise<void>;
};

export type FlushResult = {
  remaining: SyncOp[];
  appliedOpIds: string[];
  dropped: { op: SyncOp; reason: string }[];
};

export const QUEUE_KEY = "trading-os-sync-queue-v1";

type StorageLike = Pick<Storage, "getItem" | "setItem">;

function makeOpId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

// Distributive so each union member keeps its own fields (a plain Omit over a
// union collapses to only the shared keys).
type DistributiveOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never;

export function newOp(op: DistributiveOmit<SyncOp, "opId">): SyncOp {
  return { ...op, opId: makeOpId() } as SyncOp;
}

export function loadQueue(storage: StorageLike): SyncOp[] {
  try {
    const raw = storage.getItem(QUEUE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as SyncOp[]) : [];
  } catch {
    return [];
  }
}

export function saveQueue(storage: StorageLike, ops: SyncOp[]): void {
  storage.setItem(QUEUE_KEY, JSON.stringify(ops));
}

export function enqueue(storage: StorageLike, op: SyncOp): SyncOp[] {
  const next = [...loadQueue(storage), op];
  saveQueue(storage, next);
  return next;
}

// A network failure (fetch could not reach the server) or a 5xx is retryable:
// keep the op queued. A 4xx means the server rejected it — retrying will fail
// forever, so the op is dropped and reported. A 409 means the record already
// exists (idempotent replay already succeeded), which is a benign drop.
export function isRetryable(error: unknown): boolean {
  if (error instanceof ApiError) return error.status >= 500;
  return true;
}

async function dispatch(op: SyncOp, handlers: SyncHandlers): Promise<void> {
  if (op.type === "create") {
    if (op.collection === "trades") await handlers.createTrade(op.record);
    else if (op.collection === "journal") await handlers.createJournal(op.record);
    else await handlers.createDocument(op.record);
    return;
  }
  if (op.type === "update") {
    if (op.collection === "trades") await handlers.updateTrade(op.id, op.patch);
    else if (op.collection === "journal") await handlers.updateJournal(op.id, op.patch);
    else await handlers.updateDocument(op.id, op.patch);
    return;
  }
  await handlers.remove(op.collection, op.id);
}

// Replay queued ops in order. Stops at the first retryable failure (so ordering
// is preserved and we don't hammer a down server), dropping any op the server
// permanently rejected.
export async function flushQueue(ops: SyncOp[], handlers: SyncHandlers): Promise<FlushResult> {
  const appliedOpIds: string[] = [];
  const dropped: { op: SyncOp; reason: string }[] = [];

  for (let index = 0; index < ops.length; index += 1) {
    const op = ops[index];
    try {
      await dispatch(op, handlers);
      appliedOpIds.push(op.opId);
    } catch (error) {
      if (isRetryable(error)) {
        return { remaining: ops.slice(index), appliedOpIds, dropped };
      }
      const reason = error instanceof ApiError ? error.message : String(error);
      appliedOpIds.push(op.opId);
      dropped.push({ op, reason });
    }
  }

  return { remaining: [], appliedOpIds, dropped };
}
