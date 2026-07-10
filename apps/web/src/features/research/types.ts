// Wire types for the grounded research pipeline (Lattice L3/L4). These mirror
// the FastAPI response shapes in services/api/app/schemas/research.py.

export interface Citation {
  ref: string;
  kind: "chunk" | "claim";
  source_title: string;
  snippet: string;
}

export interface SpecialElement {
  type: string;
  [key: string]: unknown;
}

export interface ResearchAnswer {
  question: string;
  route: "connection" | "content" | "hybrid" | "analytics";
  answer_markdown: string;
  trust_score: number;
  citations: Citation[];
  special_elements: SpecialElement[];
  retrieved: Record<string, unknown>;
}

export interface SearchResult {
  chunk_id: string;
  source_id: string;
  source_title: string;
  text: string;
  score: number;
}

export interface Claim {
  id: string;
  subject_node_id: string;
  predicate: string;
  object_literal: string | null;
  statement_text: string;
  polarity: "supports" | "refutes" | "neutral";
  confidence: number | null;
  created_at: string;
}

export interface ClaimConflict {
  id: string;
  status: "open" | "resolved" | "dismissed";
  detected_at: string;
  claim_a: Claim;
  claim_b: Claim;
}
