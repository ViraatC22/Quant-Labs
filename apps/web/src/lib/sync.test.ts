import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import { enqueue, flushQueue, loadQueue, newOp, QUEUE_KEY, type SyncHandlers } from "@/lib/sync";
import type { TradeEntry } from "@/lib/types";

function memoryStorage() {
  const map = new Map<string, string>();
  return {
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => void map.set(k, v)
  };
}

function sampleTrade(id: string): TradeEntry {
  return {
    id,
    symbol: "AAPL",
    side: "long",
    entryDate: "2026-07-08",
    entryPrice: 100,
    exitPrice: null,
    quantity: 1,
    fees: 0,
    strategy: "",
    setup: "",
    emotion: "focused",
    notes: "",
    createdAt: "2026-07-08T00:00:00Z"
  };
}

function noopHandlers(overrides: Partial<SyncHandlers> = {}): SyncHandlers {
  return {
    createTrade: async (r) => r,
    createJournal: async (r) => r,
    createDocument: async (r) => r,
    updateTrade: async (_id, _p) => sampleTrade("x"),
    updateJournal: async (_id, _p) => ({
      id: "x",
      date: "2026-07-09",
      title: "",
      emotion: "focused",
      routineDone: false,
      body: "",
      tags: [],
      createdAt: ""
    }),
    updateDocument: async (_id, _p) => ({
      id: "x",
      title: "",
      kind: "note",
      source: "",
      body: "",
      tags: [],
      createdAt: ""
    }),
    remove: async () => undefined,
    ...overrides
  };
}

describe("sync queue", () => {
  it("persists and reloads ops", () => {
    const storage = memoryStorage();
    enqueue(storage, newOp({ type: "create", collection: "trades", record: sampleTrade("a") }));
    expect(loadQueue(storage)).toHaveLength(1);
    expect(storage.getItem(QUEUE_KEY)).toContain("AAPL");
  });

  it("drains the whole queue when every op succeeds", async () => {
    const ops = [
      newOp({ type: "create", collection: "trades", record: sampleTrade("a") }),
      newOp({ type: "create", collection: "trades", record: sampleTrade("b") })
    ];
    const createTrade = vi.fn(async (r: TradeEntry) => r);
    const result = await flushQueue(ops, noopHandlers({ createTrade }));
    expect(createTrade).toHaveBeenCalledTimes(2);
    expect(result.remaining).toHaveLength(0);
    expect(result.appliedOpIds).toHaveLength(2);
  });

  it("stops and preserves order on a network failure (retryable)", async () => {
    const ops = [
      newOp({ type: "create", collection: "trades", record: sampleTrade("a") }),
      newOp({ type: "create", collection: "trades", record: sampleTrade("b") })
    ];
    const createTrade = vi
      .fn<(r: TradeEntry) => Promise<TradeEntry>>()
      .mockResolvedValueOnce(sampleTrade("a"))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));
    const result = await flushQueue(ops, noopHandlers({ createTrade }));
    // First applied, second kept for later (still at the head of the queue).
    expect(result.appliedOpIds).toEqual([ops[0].opId]);
    expect(result.remaining).toEqual([ops[1]]);
  });

  it("drops an op the server permanently rejects (4xx) and keeps going", async () => {
    const ops = [
      newOp({ type: "create", collection: "trades", record: sampleTrade("a") }),
      newOp({ type: "create", collection: "trades", record: sampleTrade("b") })
    ];
    const createTrade = vi
      .fn<(r: TradeEntry) => Promise<TradeEntry>>()
      .mockRejectedValueOnce(new ApiError(422, "invalid"))
      .mockResolvedValueOnce(sampleTrade("b"));
    const result = await flushQueue(ops, noopHandlers({ createTrade }));
    expect(result.remaining).toHaveLength(0);
    expect(result.dropped).toHaveLength(1);
    expect(result.dropped[0].op.opId).toBe(ops[0].opId);
  });

  it("treats a 409 conflict as a benign drop (idempotent replay)", async () => {
    const ops = [newOp({ type: "create", collection: "trades", record: sampleTrade("a") })];
    const createTrade = vi.fn(async () => {
      throw new ApiError(409, "already exists");
    });
    const result = await flushQueue(ops, noopHandlers({ createTrade }));
    expect(result.remaining).toHaveLength(0);
    expect(result.dropped).toHaveLength(1);
  });
});
