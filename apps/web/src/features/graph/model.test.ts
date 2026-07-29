import { describe, expect, it } from "vitest";

import { mergeAtlasGraphs, neighborhoodToGraph } from "./model";

describe("Atlas graph model", () => {
  it("replaces a matching local concept with its server identity", () => {
    const local = {
      nodes: [
        { id: "strategy:orb", label: "ORB", type: "strategy", detail: "local", weight: 1, x: 10, y: 20 },
        { id: "memory", label: "Trading Memory", type: "memory", detail: "", weight: 1, x: 0, y: 0 }
      ],
      edges: [{ id: "local-edge", from: "memory", to: "strategy:orb", label: "strategy" }]
    };
    const remote = {
      nodes: [
        { id: "00000000-0000-0000-0000-000000000001", label: "ORB", type: "strategy", detail: "remote", weight: 3, x: 50, y: 60, remote: true }
      ],
      edges: []
    };
    const merged = mergeAtlasGraphs(local, remote);
    expect(merged.nodes.some((node) => node.id === "strategy:orb")).toBe(false);
    expect(merged.nodes.find((node) => node.label === "ORB")).toMatchObject({
      id: "00000000-0000-0000-0000-000000000001",
      x: 10,
      y: 20,
      detail: "remote"
    });
    expect(merged.edges[0].to).toBe("00000000-0000-0000-0000-000000000001");
  });

  it("preserves neighborhood evidence and conflict counts", () => {
    const graph = neighborhoodToGraph({
      root_id: "00000000-0000-0000-0000-000000000001",
      depth: 1,
      nodes: [
        {
          id: "00000000-0000-0000-0000-000000000001",
          label: "ORB",
          node_type: "strategy",
          confidence: 0.8,
          properties: { summary: "Opening range breakout" },
          open_conflict_count: 2
        },
        {
          id: "00000000-0000-0000-0000-000000000002",
          label: "VWAP",
          node_type: "indicator",
          confidence: 0.7,
          properties: {},
          open_conflict_count: 0
        }
      ],
      edges: [
        {
          id: "00000000-0000-0000-0000-000000000003",
          edge_type: "uses_indicator",
          from_node_id: "00000000-0000-0000-0000-000000000001",
          to_node_id: "00000000-0000-0000-0000-000000000002",
          confidence: 0.7,
          properties: {},
          evidence_chunk_ids: ["00000000-0000-0000-0000-000000000004"],
          evidence_count: 1,
          contributing_sources: ["ORB source"],
          evidence: [
            {
              chunk_id: "00000000-0000-0000-0000-000000000004",
              source_document_id: "00000000-0000-0000-0000-000000000005",
              source_title: "ORB source",
              text: "Use VWAP as confirmation."
            }
          ]
        }
      ]
    });
    expect(graph.nodes[0].openConflictCount).toBe(2);
    expect(graph.edges[0]).toMatchObject({ evidenceCount: 1, contributingSources: ["ORB source"] });
    expect(graph.edges[0].evidence?.[0].text).toBe("Use VWAP as confirmation.");
  });
});
