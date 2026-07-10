// Research API client. Self-contained (not routed through lib/api.ts) so the
// research feature stays isolated per the decomposition plan.

import type { ClaimConflict, ResearchAnswer, SearchResult } from "./types";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }
  });
  if (!response.ok) {
    throw new Error(`API ${init?.method ?? "GET"} ${path} failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export function askResearch(question: string): Promise<ResearchAnswer> {
  return json<ResearchAnswer>("/api/v1/research/ask", {
    method: "POST",
    body: JSON.stringify({ question })
  });
}

export function searchMemory(query: string): Promise<SearchResult[]> {
  return json<SearchResult[]>(`/api/v1/research/search?q=${encodeURIComponent(query)}`);
}

export function listConflicts(): Promise<ClaimConflict[]> {
  return json<ClaimConflict[]>("/api/v1/research/conflicts");
}
