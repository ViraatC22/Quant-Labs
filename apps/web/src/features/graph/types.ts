export type AtlasEvidence = {
  chunkId: string;
  sourceDocumentId: string | null;
  sourceTitle: string;
  text: string;
};

export type AtlasGraphNode = {
  id: string;
  label: string;
  type: string;
  detail: string;
  weight: number;
  x: number;
  y: number;
  pnl?: number;
  confidence?: number | null;
  properties?: Record<string, unknown>;
  openConflictCount?: number;
  remote?: boolean;
};

export type AtlasGraphEdge = {
  id: string;
  from: string;
  to: string;
  label: string;
  confidence?: number | null;
  properties?: Record<string, unknown>;
  evidenceCount?: number;
  contributingSources?: string[];
  evidence?: AtlasEvidence[];
  remote?: boolean;
};

export type AtlasGraphModel = {
  nodes: AtlasGraphNode[];
  edges: AtlasGraphEdge[];
};

export type GraphSearchNode = {
  id: string;
  node_type: string;
  label: string;
  properties: Record<string, unknown>;
  confidence: number | null;
};

export type GraphNeighborhood = {
  root_id: string;
  depth: number;
  nodes: Array<{
    id: string;
    label: string;
    node_type: string;
    confidence: number | null;
    properties: Record<string, unknown>;
    open_conflict_count: number;
  }>;
  edges: Array<{
    id: string;
    edge_type: string;
    from_node_id: string;
    to_node_id: string;
    confidence: number | null;
    properties: Record<string, unknown>;
    evidence_chunk_ids: string[];
    evidence_count: number;
    contributing_sources: string[];
    evidence: Array<{
      chunk_id: string;
      source_document_id: string | null;
      source_title: string;
      text: string;
    }>;
  }>;
};
