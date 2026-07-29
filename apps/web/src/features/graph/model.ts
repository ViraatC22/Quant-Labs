import type {
  AtlasGraphEdge,
  AtlasGraphModel,
  AtlasGraphNode,
  GraphNeighborhood
} from "./types";

export const graphCanvasWidth = 1680;
export const graphCanvasHeight = 1040;
export const graphCenterX = graphCanvasWidth / 2;
export const graphCenterY = graphCanvasHeight / 2;

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isServerNodeId(value: string): boolean {
  return UUID_RE.test(value);
}

function canonicalNodeKey(node: Pick<AtlasGraphNode, "label" | "type">): string {
  return `${node.type.toLowerCase()}:${node.label.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()}`;
}

export function mergeAtlasGraphs(
  base: AtlasGraphModel,
  incoming: AtlasGraphModel
): AtlasGraphModel {
  const nodes = new Map(base.nodes.map((node) => [node.id, { ...node }]));
  const idByKey = new Map(base.nodes.map((node) => [canonicalNodeKey(node), node.id]));
  const aliases = new Map<string, string>();

  for (const next of incoming.nodes) {
    const existingId = idByKey.get(canonicalNodeKey(next));
    const existing = existingId ? nodes.get(existingId) : undefined;
    if (existing && existing.id !== next.id && next.remote) {
      aliases.set(existing.id, next.id);
      nodes.delete(existing.id);
      nodes.set(next.id, {
        ...existing,
        ...next,
        x: existing.x,
        y: existing.y,
        weight: Math.max(existing.weight, next.weight),
        openConflictCount: Math.max(
          existing.openConflictCount ?? 0,
          next.openConflictCount ?? 0
        )
      });
      idByKey.set(canonicalNodeKey(next), next.id);
      continue;
    }
    if (existing) {
      nodes.set(existing.id, {
        ...existing,
        ...next,
        id: existing.id,
        x: existing.x,
        y: existing.y,
        weight: Math.max(existing.weight, next.weight),
        openConflictCount: Math.max(
          existing.openConflictCount ?? 0,
          next.openConflictCount ?? 0
        )
      });
      continue;
    }
    nodes.set(next.id, { ...next });
    idByKey.set(canonicalNodeKey(next), next.id);
  }

  const edgeMap = new Map<string, AtlasGraphEdge>();
  for (const edge of [...base.edges, ...incoming.edges]) {
    const from = aliases.get(edge.from) ?? edge.from;
    const to = aliases.get(edge.to) ?? edge.to;
    if (from === to || !nodes.has(from) || !nodes.has(to)) continue;
    const key = edge.remote ? edge.id : `${from}->${to}:${edge.label}`;
    const current = edgeMap.get(key);
    edgeMap.set(key, {
      ...current,
      ...edge,
      from,
      to,
      evidenceCount: Math.max(current?.evidenceCount ?? 0, edge.evidenceCount ?? 0),
      contributingSources: Array.from(
        new Set([...(current?.contributingSources ?? []), ...(edge.contributingSources ?? [])])
      ),
      evidence: mergeEvidence(current?.evidence ?? [], edge.evidence ?? [])
    });
  }

  return { nodes: Array.from(nodes.values()), edges: Array.from(edgeMap.values()) };
}

function mergeEvidence(
  left: NonNullable<AtlasGraphEdge["evidence"]>,
  right: NonNullable<AtlasGraphEdge["evidence"]>
) {
  const rows = new Map(left.map((item) => [item.chunkId, item]));
  right.forEach((item) => rows.set(item.chunkId, item));
  return Array.from(rows.values());
}

export function neighborhoodToGraph(payload: GraphNeighborhood): AtlasGraphModel {
  const degree = new Map<string, number>();
  payload.edges.forEach((edge) => {
    degree.set(edge.from_node_id, (degree.get(edge.from_node_id) ?? 0) + 1);
    degree.set(edge.to_node_id, (degree.get(edge.to_node_id) ?? 0) + 1);
  });
  const nodes = payload.nodes.map((node) => {
    const position = positionForNode(node.id, node.node_type);
    return {
      id: node.id,
      label: node.label,
      type: node.node_type,
      detail: nodeDetail(node.node_type, node.properties),
      weight: Math.max(1, degree.get(node.id) ?? 0),
      confidence: node.confidence,
      properties: node.properties,
      openConflictCount: node.open_conflict_count,
      remote: true,
      ...position
    } satisfies AtlasGraphNode;
  });
  const edges = payload.edges.map(
    (edge): AtlasGraphEdge => ({
      id: edge.id,
      from: edge.from_node_id,
      to: edge.to_node_id,
      label: edge.edge_type,
      confidence: edge.confidence,
      properties: edge.properties,
      evidenceCount: edge.evidence_count,
      contributingSources: edge.contributing_sources,
      evidence: edge.evidence.map((item) => ({
        chunkId: item.chunk_id,
        sourceDocumentId: item.source_document_id,
        sourceTitle: item.source_title,
        text: item.text
      })),
      remote: true
    })
  );
  return { nodes, edges };
}

function nodeDetail(type: string, properties: Record<string, unknown>): string {
  for (const key of ["summary", "excerpt", "description", "source_title"]) {
    const value = properties[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  const sources = properties.source_titles;
  if (Array.isArray(sources) && sources.length) {
    return `Learned ${type} supported by ${sources.map(String).join(", ")}.`;
  }
  return `Learned ${type} from the server knowledge graph.`;
}

function positionForNode(id: string, type: string) {
  const config = orbitForType(type);
  const seed = hashNumber(id);
  const angle = config.phase + seededUnit(seed, 17) * Math.PI * 2;
  const radius = config.radius + (seededUnit(seed, 31) - 0.5) * config.jitter;
  return {
    x: graphCenterX + Math.cos(angle) * radius,
    y: graphCenterY + Math.sin(angle) * radius * config.squash
  };
}

function orbitForType(type: string) {
  const configs: Record<
    string,
    { radius: number; jitter: number; squash: number; phase: number }
  > = {
    strategy: { radius: 190, jitter: 42, squash: 0.68, phase: -0.6 },
    setup: { radius: 280, jitter: 54, squash: 0.64, phase: 0.3 },
    indicator: { radius: 315, jitter: 58, squash: 0.66, phase: 1.35 },
    technical: { radius: 345, jitter: 60, squash: 0.66, phase: 1.8 },
    rule: { radius: 390, jitter: 64, squash: 0.64, phase: 2.15 },
    source: { radius: 370, jitter: 62, squash: 0.62, phase: 2.5 },
    journal: { radius: 425, jitter: 58, squash: 0.66, phase: 2.95 },
    emotion: { radius: 360, jitter: 52, squash: 0.7, phase: 1.1 },
    market: { radius: 460, jitter: 56, squash: 0.6, phase: 0.8 },
    timeframe: { radius: 480, jitter: 52, squash: 0.6, phase: 1.2 },
    symbol: { radius: 500, jitter: 50, squash: 0.58, phase: 0.55 },
    trade: { radius: 535, jitter: 64, squash: 0.62, phase: -0.12 },
    tag: { radius: 610, jitter: 96, squash: 0.58, phase: 1.75 }
  };
  return configs[type] ?? { radius: 520, jitter: 110, squash: 0.62, phase: 2.4 };
}

export function hashNumber(value: string | number) {
  const text = String(value);
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return Math.abs(hash >>> 0);
}

export function seededUnit(value: string | number, salt: number) {
  const seed = typeof value === "number" ? value : hashNumber(value);
  const raw = Math.sin(seed * 12.9898 + salt * 78.233) * 43758.5453;
  return raw - Math.floor(raw);
}
