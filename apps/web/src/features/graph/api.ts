import type { GraphNeighborhood, GraphSearchNode } from "./types";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function json<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    signal
  });
  if (!response.ok) {
    throw new Error(`API GET ${path} failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export function searchGraphNodes(
  query: string,
  limit = 8,
  signal?: AbortSignal
): Promise<GraphSearchNode[]> {
  return json<GraphSearchNode[]>(
    `/api/v1/graph/search?q=${encodeURIComponent(query)}&limit=${limit}`,
    signal
  );
}

export function getGraphNeighborhood(
  nodeId: string,
  depth: 1 | 2 | 3,
  signal?: AbortSignal
): Promise<GraphNeighborhood> {
  return json<GraphNeighborhood>(
    `/api/v1/graph/neighborhood/${encodeURIComponent(nodeId)}?depth=${depth}`,
    signal
  );
}
