"use client";

import {
  Activity,
  BookOpen,
  Crosshair,
  GitBranch,
  Layers3,
  LoaderCircle,
  Search,
  ShieldCheck,
  TriangleAlert,
  ZoomIn,
  ZoomOut
} from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import { getGraphNeighborhood, searchGraphNodes } from "./api";
import {
  graphCanvasHeight,
  graphCanvasWidth,
  graphCenterX,
  graphCenterY,
  hashNumber,
  isServerNodeId,
  mergeAtlasGraphs,
  neighborhoodToGraph,
  seededUnit
} from "./model";
import type {
  AtlasGraphEdge,
  AtlasGraphModel,
  AtlasGraphNode,
  GraphSearchNode
} from "./types";

type GraphViewport = { centerX: number; centerY: number; zoom: number };
type GraphDragState = {
  startX: number;
  startY: number;
  startView: GraphViewport;
};

type GraphExplorerProps = {
  initialGraph: AtlasGraphModel;
  online: boolean;
  focusRequest?: { nodeId: string; requestId: number } | null;
  onOpenSource?: (sourceDocumentId: string, sourceTitle: string) => void;
};

const galaxyOrbits = [
  { rx: 150, ry: 88, opacity: 0.18, strokeWidth: 1.4, rotate: -8 },
  { rx: 285, ry: 165, opacity: 0.13, strokeWidth: 1.1, rotate: 12 },
  { rx: 440, ry: 260, opacity: 0.1, strokeWidth: 0.9, rotate: -16 },
  { rx: 610, ry: 360, opacity: 0.075, strokeWidth: 0.8, rotate: 8 },
  { rx: 735, ry: 430, opacity: 0.05, strokeWidth: 0.7, rotate: -4 }
];

const galaxyStars = Array.from({ length: 150 }, (_, index) => ({
  id: `star-${index}`,
  x: Math.round(seededUnit(index, 3) * graphCanvasWidth),
  y: Math.round(seededUnit(index, 11) * graphCanvasHeight),
  r: Number((0.45 + seededUnit(index, 23) * 1.35).toFixed(2)),
  opacity: Number((0.16 + seededUnit(index, 31) * 0.58).toFixed(2)),
  delay: Number((-seededUnit(index, 43) * 7).toFixed(2)),
  duration: Number((3.8 + seededUnit(index, 59) * 5.2).toFixed(2))
}));

export function GraphExplorer({
  initialGraph,
  online,
  focusRequest,
  onOpenSource
}: GraphExplorerProps) {
  const [expandedGraph, setExpandedGraph] = React.useState<AtlasGraphModel>({
    nodes: [],
    edges: []
  });
  const graph = React.useMemo(
    () => mergeAtlasGraphs(initialGraph, expandedGraph),
    [expandedGraph, initialGraph]
  );
  const graphRef = React.useRef(graph);
  const [selectedNodeId, setSelectedNodeId] = React.useState("memory");
  const [selectedEdgeId, setSelectedEdgeId] = React.useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = React.useState<string | null>(null);
  const [motionPaused, setMotionPaused] = React.useState(false);
  const [graphTick, setGraphTick] = React.useState(0);
  const [view, setView] = React.useState<GraphViewport>({
    centerX: graphCenterX,
    centerY: graphCenterY,
    zoom: 1
  });
  const [drag, setDrag] = React.useState<GraphDragState | null>(null);
  const [depth, setDepth] = React.useState<1 | 2 | 3>(1);
  const [loadingNodeId, setLoadingNodeId] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [showConflicts, setShowConflicts] = React.useState(true);
  const [colorByEvidence, setColorByEvidence] = React.useState(false);
  const [searchText, setSearchText] = React.useState("");
  const [searchResults, setSearchResults] = React.useState<GraphSearchNode[]>([]);
  const [searching, setSearching] = React.useState(false);

  React.useEffect(() => {
    graphRef.current = graph;
  }, [graph]);

  React.useEffect(() => {
    if (motionPaused) return;
    const intervalId = window.setInterval(() => {
      setGraphTick((current) => current + 0.075);
    }, 80);
    return () => window.clearInterval(intervalId);
  }, [motionPaused]);

  const renderedNodes = React.useMemo(
    () =>
      graph.nodes.map((node) => {
        const offset = graphDrift(node, graphTick);
        return { ...node, x: node.x + offset.x, y: node.y + offset.y };
      }),
    [graph.nodes, graphTick]
  );
  const nodeLookup = React.useMemo(
    () => new Map(renderedNodes.map((node) => [node.id, node])),
    [renderedNodes]
  );
  const selectedNode = nodeLookup.get(selectedNodeId) ?? renderedNodes[0];
  const selectedEdge = graph.edges.find((edge) => edge.id === selectedEdgeId) ?? null;
  const activeNode = hoveredNodeId ? nodeLookup.get(hoveredNodeId) ?? selectedNode : selectedNode;
  const selectedNodeEdges = React.useMemo(
    () =>
      selectedNode
        ? graph.edges.filter(
            (edge) => edge.from === selectedNode.id || edge.to === selectedNode.id
          )
        : [],
    [graph.edges, selectedNode]
  );
  const activeNodeEdges = React.useMemo(
    () =>
      activeNode
        ? graph.edges.filter((edge) => edge.from === activeNode.id || edge.to === activeNode.id)
        : [],
    [activeNode, graph.edges]
  );
  const focusedNodeIds = React.useMemo(() => {
    const ids = new Set<string>();
    if (activeNode) ids.add(activeNode.id);
    activeNodeEdges.forEach((edge) => {
      ids.add(edge.from);
      ids.add(edge.to);
    });
    return ids;
  }, [activeNode, activeNodeEdges]);
  const focusMode = Boolean(activeNode && activeNode.type !== "memory");
  const viewBox = React.useMemo(() => {
    const width = graphCanvasWidth / view.zoom;
    const height = graphCanvasHeight / view.zoom;
    return `${view.centerX - width / 2} ${view.centerY - height / 2} ${width} ${height}`;
  }, [view]);

  const focusNode = React.useCallback((node: AtlasGraphNode) => {
    setView((current) => ({
      centerX: node.x,
      centerY: node.y,
      zoom: Math.max(1.35, current.zoom)
    }));
  }, []);

  const expandServerNode = React.useCallback(
    async (nodeId: string) => {
      if (!online) return;
      setLoadingNodeId(nodeId);
      setNotice(null);
      try {
        const neighborhood = await getGraphNeighborhood(nodeId, depth);
        const addition = neighborhoodToGraph(neighborhood);
        const merged = mergeAtlasGraphs(graphRef.current, addition);
        setExpandedGraph((current) => mergeAtlasGraphs(current, addition));
        setSelectedNodeId(nodeId);
        setSelectedEdgeId(null);
        const target = merged.nodes.find((node) => node.id === nodeId);
        if (target) focusNode(target);
      } catch {
        setNotice("The server graph could not expand this entity. Your local Atlas is still available.");
      } finally {
        setLoadingNodeId(null);
      }
    },
    [depth, focusNode, online]
  );

  React.useEffect(() => {
    if (!focusRequest || !online) return;
    const timer = window.setTimeout(() => {
      void expandServerNode(focusRequest.nodeId);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [expandServerNode, focusRequest, online]);

  async function resolveAndExpand(node: AtlasGraphNode) {
    if (!online) return;
    if (isServerNodeId(node.id)) {
      await expandServerNode(node.id);
      return;
    }
    setLoadingNodeId(node.id);
    setNotice(null);
    try {
      const matches = await searchGraphNodes(node.label, 6);
      const exact = matches.find(
        (match) =>
          match.label.localeCompare(node.label, undefined, { sensitivity: "base" }) === 0 &&
          match.node_type === node.type
      );
      const match = exact ?? matches.find((candidate) => candidate.node_type === node.type);
      if (!match) {
        setNotice(`“${node.label}” is local-only; no learned server entity matched it yet.`);
        return;
      }
      await expandServerNode(match.id);
    } catch {
      setNotice("Entity lookup is unavailable. The offline Atlas remains usable.");
    } finally {
      setLoadingNodeId(null);
    }
  }

  function selectNode(node: AtlasGraphNode, expand = true) {
    setSelectedNodeId(node.id);
    setSelectedEdgeId(null);
    setMotionPaused(true);
    focusNode(node);
    if (expand) void resolveAndExpand(node);
  }

  async function runSearch(event: React.FormEvent) {
    event.preventDefault();
    const query = searchText.trim();
    if (!query || !online) return;
    setSearching(true);
    setNotice(null);
    try {
      setSearchResults(await searchGraphNodes(query, 8));
    } catch {
      setNotice("Atlas search could not reach the API.");
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }

  function zoom(delta: number) {
    setView((current) => ({
      ...current,
      zoom: Math.min(2.4, Math.max(0.7, Number((current.zoom + delta).toFixed(2))))
    }));
  }

  function resetView() {
    setView({ centerX: graphCenterX, centerY: graphCenterY, zoom: 1 });
    setMotionPaused(false);
    setSelectedEdgeId(null);
  }

  function pan(event: React.PointerEvent<SVGSVGElement>) {
    if (!drag) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const unitX = graphCanvasWidth / rect.width / drag.startView.zoom;
    const unitY = graphCanvasHeight / rect.height / drag.startView.zoom;
    setView({
      ...drag.startView,
      centerX: drag.startView.centerX - (event.clientX - drag.startX) * unitX,
      centerY: drag.startView.centerY - (event.clientY - drag.startY) * unitY
    });
  }

  return (
    <section
      aria-labelledby="graph-tab"
      className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]"
      id="graph-panel"
      role="tabpanel"
    >
      <section className="rounded-lg border border-line bg-card/86 p-4 shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-ink">Strategy Atlas</h2>
            <p className="mt-1 text-sm text-ink/58">
              {graph.nodes.length} nodes / {graph.edges.length} edges · click a node to expand
              {online ? " learned memory" : " local memory"}
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <label className="flex h-9 items-center gap-2 rounded-md border border-line bg-card px-2 text-xs font-semibold text-ink/60">
              Depth
              <select
                aria-label="Neighborhood depth"
                className="bg-transparent text-ink outline-none"
                onChange={(event) => setDepth(Number(event.target.value) as 1 | 2 | 3)}
                value={depth}
              >
                <option value={1}>1 hop</option>
                <option value={2}>2 hops</option>
                <option value={3}>3 hops</option>
              </select>
            </label>
            <IconButton
              active={showConflicts}
              label={showConflicts ? "Hide conflict badges" : "Show conflict badges"}
              onClick={() => setShowConflicts((current) => !current)}
            >
              <TriangleAlert aria-hidden="true" size={17} />
            </IconButton>
            <IconButton
              active={colorByEvidence}
              label={colorByEvidence ? "Use neutral edge colors" : "Color edges by evidence count"}
              onClick={() => setColorByEvidence((current) => !current)}
            >
              <Layers3 aria-hidden="true" size={17} />
            </IconButton>
            <IconButton
              label={motionPaused ? "Resume drift" : "Pause drift"}
              onClick={() => setMotionPaused((current) => !current)}
            >
              <Activity aria-hidden="true" size={17} strokeWidth={2.2} />
            </IconButton>
            <IconButton label="Zoom in" onClick={() => zoom(0.18)}>
              <ZoomIn aria-hidden="true" size={17} />
            </IconButton>
            <IconButton label="Zoom out" onClick={() => zoom(-0.18)}>
              <ZoomOut aria-hidden="true" size={17} />
            </IconButton>
            <IconButton
              label="Focus selected node"
              onClick={() => selectedNode && focusNode(selectedNode)}
            >
              <Crosshair aria-hidden="true" size={17} />
            </IconButton>
            <IconButton label="Recenter" onClick={resetView}>
              <GitBranch aria-hidden="true" size={17} />
            </IconButton>
          </div>
        </div>

        <form className="mt-4 flex gap-2" onSubmit={runSearch}>
          <Input
            aria-label="Search learned Atlas entities"
            disabled={!online}
            onChange={(event) => setSearchText(event.target.value)}
            placeholder={online ? "Search learned entities…" : "Connect the API to search learned entities"}
            value={searchText}
          />
          <Button disabled={!online || searching || !searchText.trim()} type="submit" variant="outline">
            {searching ? (
              <LoaderCircle aria-hidden="true" className="animate-spin" size={16} />
            ) : (
              <Search aria-hidden="true" size={16} />
            )}
            Search
          </Button>
        </form>
        {searchResults.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2" aria-label="Atlas search results">
            {searchResults.map((result) => (
              <button
                className="rounded-md border border-line bg-card px-2.5 py-1.5 text-left text-xs transition hover:bg-paper"
                key={result.id}
                onClick={() => {
                  setSearchResults([]);
                  void expandServerNode(result.id);
                }}
                type="button"
              >
                <span className="font-semibold text-ink">{result.label}</span>
                <span className="ml-2 uppercase text-ink/45">{result.node_type}</span>
              </button>
            ))}
          </div>
        )}
        {notice && <p className="mt-2 text-xs font-medium text-caution">{notice}</p>}

        <div className="mt-4 overflow-hidden rounded-lg border border-ink/10 bg-[#060911]">
          <svg
            aria-label="Trading relationship atlas"
            className="h-[min(78vh,780px)] min-h-[640px] w-full cursor-grab touch-none active:cursor-grabbing"
            onPointerDown={(event) => {
              if ((event.target as Element).closest("[data-graph-interactive='true']")) return;
              setDrag({ startX: event.clientX, startY: event.clientY, startView: view });
            }}
            onPointerLeave={() => setDrag(null)}
            onPointerMove={pan}
            onPointerUp={() => setDrag(null)}
            onWheel={(event) => {
              event.preventDefault();
              zoom(event.deltaY > 0 ? -0.12 : 0.12);
            }}
            role="img"
            viewBox={viewBox}
          >
            <defs>
              <radialGradient id="atlasGalaxyCore" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#f7f3ea" stopOpacity="0.52" />
                <stop offset="30%" stopColor="#7bd7e8" stopOpacity="0.15" />
                <stop offset="72%" stopColor="#6d5bd0" stopOpacity="0.07" />
                <stop offset="100%" stopColor="#060911" stopOpacity="0" />
              </radialGradient>
              <filter id="atlasStarGlow" height="220%" width="220%" x="-60%" y="-60%">
                <feGaussianBlur stdDeviation="3" />
              </filter>
            </defs>
            <rect fill="#060911" height="3000" width="3600" x="-960" y="-980" />
            <circle
              cx={graphCenterX}
              cy={graphCenterY}
              fill="url(#atlasGalaxyCore)"
              opacity="0.95"
              r="560"
            />
            <g className={motionPaused ? "galaxy-paused" : ""}>
              {galaxyStars.map((star) => (
                <circle
                  className="galaxy-star-twinkle"
                  cx={star.x}
                  cy={star.y}
                  fill="#f7f3ea"
                  key={star.id}
                  opacity={star.opacity}
                  r={star.r}
                  style={{
                    animationDelay: `${star.delay}s`,
                    animationDuration: `${star.duration}s`
                  }}
                />
              ))}
              {galaxyOrbits.map((orbit, index) => (
                <ellipse
                  className="galaxy-orbit-drift"
                  cx={graphCenterX}
                  cy={graphCenterY}
                  fill="none"
                  key={`orbit-${index}`}
                  opacity={orbit.opacity}
                  rx={orbit.rx}
                  ry={orbit.ry}
                  stroke="#8dd6e5"
                  strokeDasharray="4 12"
                  strokeWidth={orbit.strokeWidth}
                  style={{
                    animationDelay: `${index * -2.6}s`,
                    animationDuration: `${24 + index * 8}s`,
                    transform: `rotate(${orbit.rotate}deg)`,
                    transformBox: "fill-box",
                    transformOrigin: "center"
                  }}
                />
              ))}
            </g>
            {renderedNodes
              .filter((node) => node.type === "memory")
              .map((node) => (
                <circle
                  cx={node.x}
                  cy={node.y}
                  fill="#f7f3ea"
                  filter="url(#atlasStarGlow)"
                  key={`${node.id}-glow`}
                  opacity="0.35"
                  r={graphNodeRadius(node) * 2.1}
                />
              ))}
            {graph.edges.map((edge) => {
              const from = nodeLookup.get(edge.from);
              const to = nodeLookup.get(edge.to);
              if (!from || !to) return null;
              const active =
                edge.id === selectedEdge?.id ||
                (focusMode && (edge.from === activeNode?.id || edge.to === activeNode?.id));
              const memoryEdge = from.type === "memory" || to.type === "memory";
              const opacity = active ? 0.94 : focusMode ? 0.035 : memoryEdge ? 0.1 : 0.18;
              const color = colorByEvidence
                ? evidenceColor(edge.evidenceCount ?? 0)
                : active
                  ? "#f7f3ea"
                  : "#d8d1c3";
              const path = graphEdgePath(from, to);
              return (
                <g key={edge.id}>
                  <path
                    d={path}
                    data-graph-interactive="true"
                    fill="none"
                    onClick={(event) => {
                      event.stopPropagation();
                      setSelectedEdgeId(edge.id);
                      setMotionPaused(true);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelectedEdgeId(edge.id);
                      }
                    }}
                    role="button"
                    stroke="transparent"
                    strokeWidth="12"
                    tabIndex={0}
                  >
                    <title>{`${from.label} — ${edge.label} → ${to.label}`}</title>
                  </path>
                  <path
                    d={path}
                    fill="none"
                    opacity={opacity}
                    pointerEvents="none"
                    stroke={color}
                    strokeLinecap="round"
                    strokeWidth={active ? 2.4 : colorByEvidence ? evidenceWidth(edge.evidenceCount ?? 0) : 0.9}
                  />
                </g>
              );
            })}
            {renderedNodes.map((node) => {
              const style = graphNodeStyle(node.type);
              const selected = selectedNode?.id === node.id;
              const focused = focusedNodeIds.has(node.id);
              const labelVisible = graphLabelVisible(node, selected, focused, focusMode);
              const muted = focusMode && !focused;
              const radius = graphNodeRadius(node);
              const loading = loadingNodeId === node.id;
              return (
                <g
                  className="cursor-pointer outline-none"
                  data-graph-interactive="true"
                  key={node.id}
                  onClick={() => selectNode(node)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      selectNode(node);
                    }
                  }}
                  onMouseEnter={() => setHoveredNodeId(node.id)}
                  onMouseLeave={() => setHoveredNodeId(null)}
                  role="button"
                  tabIndex={0}
                >
                  <title>{`${node.label}${node.remote ? " · click to expand" : ""}`}</title>
                  <circle
                    cx={node.x}
                    cy={node.y}
                    fill={style.fill}
                    opacity={muted ? 0.38 : 1}
                    r={radius}
                    stroke={selected ? "#ffffff" : style.stroke}
                    strokeDasharray={node.remote ? undefined : "3 2"}
                    strokeWidth={selected ? 3 : focused ? 2 : 1.25}
                  />
                  <circle
                    cx={node.x}
                    cy={node.y}
                    fill="none"
                    opacity={muted ? 0.08 : selected ? 0.45 : 0.18}
                    r={radius + 7}
                    stroke={selected ? "#ffffff" : style.stroke}
                    strokeWidth="1"
                  />
                  {loading && (
                    <circle
                      className="animate-pulse"
                      cx={node.x}
                      cy={node.y}
                      fill="none"
                      r={radius + 12}
                      stroke="#8dd6e5"
                      strokeWidth="2"
                    />
                  )}
                  {showConflicts && (node.openConflictCount ?? 0) > 0 && (
                    <g aria-label={`${node.openConflictCount} open conflicts`}>
                      <circle
                        cx={node.x + radius - 1}
                        cy={node.y - radius + 1}
                        fill="#9f3f46"
                        r="9"
                        stroke="#f7f3ea"
                        strokeWidth="1.5"
                      />
                      <text
                        fill="#ffffff"
                        fontSize="9"
                        fontWeight="700"
                        textAnchor="middle"
                        x={node.x + radius - 1}
                        y={node.y - radius + 4}
                      >
                        {node.openConflictCount}
                      </text>
                    </g>
                  )}
                  {labelVisible && (
                    <text
                      fill="#f7f3ea"
                      fontSize={selected ? "13" : "12"}
                      fontWeight={selected ? 700 : 600}
                      opacity={selected ? 1 : focused ? 0.9 : 0.68}
                      textAnchor="middle"
                      x={node.x}
                      y={node.y + radius + 15}
                    >
                      {graphLabelLines(node.label, node.type).map((line, index) => (
                        <tspan
                          dy={index === 0 ? 0 : 13}
                          key={`${node.id}-label-${index}`}
                          x={node.x}
                        >
                          {line}
                        </tspan>
                      ))}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        </div>
        <p className="mt-2 text-xs text-ink/42">
          Solid nodes are learned server entities; dashed nodes are local-only. Edge width reflects
          stored evidence when evidence coloring is enabled.
        </p>
      </section>

      <section className="h-fit rounded-lg border border-line bg-card/72 p-3 shadow-panel xl:sticky xl:top-6">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-ink">
            {selectedEdge ? "Edge Evidence" : "Node Detail"}
          </h2>
          {selectedEdge ? (
            <BookOpen aria-hidden="true" className="text-signal" size={20} />
          ) : (
            <ShieldCheck aria-hidden="true" className="text-moss" size={20} strokeWidth={2.1} />
          )}
        </div>
        {selectedEdge ? (
          <EdgeInspector
            edge={selectedEdge}
            nodeLookup={nodeLookup}
            onOpenSource={onOpenSource}
            onSelectNode={(node) => selectNode(node)}
          />
        ) : (
          <NodeInspector
            edges={selectedNodeEdges}
            loading={Boolean(selectedNode && loadingNodeId === selectedNode.id)}
            node={selectedNode}
            nodeLookup={nodeLookup}
            online={online}
            onExpand={(node) => void resolveAndExpand(node)}
            onSelectEdge={setSelectedEdgeId}
          />
        )}
      </section>
    </section>
  );
}

function IconButton({
  active = false,
  children,
  label,
  onClick
}: {
  active?: boolean;
  children: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-label={label}
      aria-pressed={active}
      className={[
        "grid h-9 w-9 place-items-center rounded-md border transition",
        active
          ? "border-signal/40 bg-signal/10 text-signal"
          : "border-line bg-card text-ink/70 hover:bg-paper"
      ].join(" ")}
      onClick={onClick}
      title={label}
      type="button"
    >
      {children}
    </button>
  );
}

function NodeInspector({
  node,
  edges,
  nodeLookup,
  online,
  loading,
  onExpand,
  onSelectEdge
}: {
  node: AtlasGraphNode | undefined;
  edges: AtlasGraphEdge[];
  nodeLookup: Map<string, AtlasGraphNode>;
  online: boolean;
  loading: boolean;
  onExpand: (node: AtlasGraphNode) => void;
  onSelectEdge: (edgeId: string) => void;
}) {
  if (!node) return null;
  const sources = sourceTitles(node.properties);
  return (
    <div className="mt-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-paper px-2 py-1 text-xs font-semibold uppercase text-ink/54">
          {node.type}
        </span>
        {node.remote && (
          <span className="rounded-md bg-moss/10 px-2 py-1 text-xs font-semibold text-moss">
            learned
          </span>
        )}
        {(node.openConflictCount ?? 0) > 0 && (
          <span className="rounded-md bg-loss/10 px-2 py-1 text-xs font-semibold text-loss">
            {node.openConflictCount} open conflict{node.openConflictCount === 1 ? "" : "s"}
          </span>
        )}
      </div>
      <h3 className="mt-3 text-xl font-semibold leading-tight text-ink">{node.label}</h3>
      <p className="mt-2 text-sm leading-6 text-ink/64">{truncate(node.detail, 360)}</p>
      {node.confidence !== undefined && node.confidence !== null && (
        <p className="mt-2 text-xs font-medium text-ink/48">
          {formatPercent(node.confidence)} extraction confidence
        </p>
      )}
      {node.pnl !== undefined && (
        <p className={`mt-3 text-sm font-semibold ${node.pnl >= 0 ? "text-moss" : "text-loss"}`}>
          {new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(node.pnl)}
        </p>
      )}
      {sources.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {sources.map((source) => (
            <span className="rounded bg-paper px-2 py-1 text-xs text-ink/58" key={source}>
              {source}
            </span>
          ))}
        </div>
      )}
      {node.type !== "memory" && (
        <Button
          className="mt-4 w-full"
          disabled={!online || loading}
          onClick={() => onExpand(node)}
          size="sm"
          type="button"
          variant="outline"
        >
          {loading ? <LoaderCircle className="animate-spin" size={15} /> : <Layers3 size={15} />}
          Expand neighborhood
        </Button>
      )}
      <div className="mt-5 border-t border-line pt-4">
        <h3 className="text-sm font-semibold text-ink">Connections</h3>
        <div className="mt-3 grid gap-2">
          {edges.slice(0, 16).map((edge) => {
            const otherId = edge.from === node.id ? edge.to : edge.from;
            const other = nodeLookup.get(otherId);
            return (
              <button
                className="flex min-h-10 items-center justify-between gap-3 rounded-md border border-line bg-card px-3 text-left text-sm transition hover:bg-paper"
                key={edge.id}
                onClick={() => onSelectEdge(edge.id)}
                type="button"
              >
                <span className="min-w-0 truncate font-medium text-ink">
                  {other?.label ?? "Unknown"}
                </span>
                <span className="shrink-0 text-xs font-medium text-ink/48">
                  {edge.label.replaceAll("_", " ")}
                  {(edge.evidenceCount ?? 0) > 0 ? ` · ${edge.evidenceCount}` : ""}
                </span>
              </button>
            );
          })}
          {!edges.length && (
            <div className="rounded-md border border-line bg-paper/60 px-3 py-3 text-sm font-medium text-ink/52">
              No connections yet
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function EdgeInspector({
  edge,
  nodeLookup,
  onOpenSource,
  onSelectNode
}: {
  edge: AtlasGraphEdge;
  nodeLookup: Map<string, AtlasGraphNode>;
  onOpenSource?: (sourceDocumentId: string, sourceTitle: string) => void;
  onSelectNode: (node: AtlasGraphNode) => void;
}) {
  const from = nodeLookup.get(edge.from);
  const to = nodeLookup.get(edge.to);
  return (
    <div className="mt-4">
      <span className="rounded-md bg-paper px-2 py-1 text-xs font-semibold uppercase text-ink/54">
        {edge.label.replaceAll("_", " ")}
      </span>
      <div className="mt-3 grid grid-cols-[1fr_auto_1fr] items-center gap-2 text-sm">
        <button
          className="truncate rounded-md border border-line bg-card px-2 py-2 text-left font-semibold text-ink hover:bg-paper"
          disabled={!from}
          onClick={() => from && onSelectNode(from)}
          type="button"
        >
          {from?.label ?? "Unknown"}
        </button>
        <span className="text-ink/36">→</span>
        <button
          className="truncate rounded-md border border-line bg-card px-2 py-2 text-left font-semibold text-ink hover:bg-paper"
          disabled={!to}
          onClick={() => to && onSelectNode(to)}
          type="button"
        >
          {to?.label ?? "Unknown"}
        </button>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <div className="rounded-md bg-paper/70 p-2.5">
          <p className="text-[11px] uppercase tracking-wide text-ink/42">Evidence</p>
          <p className="mt-1 text-lg font-semibold text-ink">{edge.evidenceCount ?? 0}</p>
        </div>
        <div className="rounded-md bg-paper/70 p-2.5">
          <p className="text-[11px] uppercase tracking-wide text-ink/42">Confidence</p>
          <p className="mt-1 text-lg font-semibold text-ink">
            {edge.confidence === undefined || edge.confidence === null
              ? "—"
              : formatPercent(edge.confidence)}
          </p>
        </div>
      </div>
      {(edge.contributingSources ?? []).length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-ink/46">
            Contributing sources
          </h3>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {edge.contributingSources?.map((source) => (
              <span className="rounded bg-paper px-2 py-1 text-xs text-ink/62" key={source}>
                {source}
              </span>
            ))}
          </div>
        </div>
      )}
      <div className="mt-5 border-t border-line pt-4">
        <h3 className="text-sm font-semibold text-ink">Evidence chunks</h3>
        <div className="mt-3 grid gap-2">
          {(edge.evidence ?? []).map((item) => (
            <article className="rounded-md border border-line bg-card p-3" key={item.chunkId}>
              <div className="flex items-start justify-between gap-2">
                <p className="text-xs font-semibold text-ink">{item.sourceTitle}</p>
                {item.sourceDocumentId && onOpenSource && (
                  <button
                    className="shrink-0 text-xs font-semibold text-signal hover:underline"
                    onClick={() => onOpenSource(item.sourceDocumentId as string, item.sourceTitle)}
                    type="button"
                  >
                    Open source
                  </button>
                )}
              </div>
              <p className="mt-2 text-xs leading-5 text-ink/58">{truncate(item.text, 320)}</p>
            </article>
          ))}
          {!(edge.evidence ?? []).length && (
            <p className="rounded-md bg-paper/60 p-3 text-sm text-ink/52">
              This edge has no stored evidence chunk yet.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function sourceTitles(properties: Record<string, unknown> | undefined): string[] {
  if (!properties) return [];
  const titles = new Set<string>();
  const multiple = properties.source_titles;
  if (Array.isArray(multiple)) multiple.forEach((value) => titles.add(String(value)));
  if (typeof properties.source_title === "string") titles.add(properties.source_title);
  return Array.from(titles).filter(Boolean);
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function truncate(value: string, limit: number) {
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized.length > limit ? `${normalized.slice(0, limit - 1).trimEnd()}…` : normalized;
}

function evidenceColor(count: number) {
  if (count >= 5) return "#94d8b9";
  if (count >= 2) return "#e0c36e";
  if (count === 1) return "#8dd6e5";
  return "#665f75";
}

function evidenceWidth(count: number) {
  return Math.min(3.2, 0.8 + Math.sqrt(count) * 0.7);
}

function graphDrift(node: AtlasGraphNode, tick: number) {
  if (node.type === "memory") return { x: 0, y: 0 };
  const seed = hashNumber(node.id);
  const amplitude = 4 + seededUnit(seed, 5) * 10;
  const speed = 0.42 + seededUnit(seed, 9) * 0.5;
  const phase = seededUnit(seed, 13) * Math.PI * 2;
  return {
    x: Math.cos(tick * speed + phase) * amplitude,
    y: Math.sin(tick * (speed * 0.82) + phase * 0.7) * amplitude * 0.72
  };
}

function graphNodeStyle(type: string) {
  const styles: Record<string, { fill: string; stroke: string }> = {
    memory: { fill: "#f7f3ea", stroke: "#ffffff" },
    strategy: { fill: "#266f83", stroke: "#8dd6e5" },
    trade: { fill: "#a85f32", stroke: "#e2a06f" },
    symbol: { fill: "#476a4d", stroke: "#9cc69f" },
    market: { fill: "#476a4d", stroke: "#9cc69f" },
    setup: { fill: "#b48924", stroke: "#e0c36e" },
    indicator: { fill: "#b48924", stroke: "#e0c36e" },
    timeframe: { fill: "#856b2b", stroke: "#d9bd74" },
    rule: { fill: "#7f5738", stroke: "#d69b70" },
    technical: { fill: "#745193", stroke: "#bda0db" },
    emotion: { fill: "#9f3f46", stroke: "#e79399" },
    source: { fill: "#6d5bd0", stroke: "#b8adff" },
    journal: { fill: "#2f7f62", stroke: "#94d8b9" },
    tag: { fill: "#6f6b5f", stroke: "#d8d1c3" }
  };
  return styles[type] ?? { fill: "#556477", stroke: "#a7b7ca" };
}

function graphNodeRadius(node: AtlasGraphNode) {
  if (node.type === "memory") return 34;
  return Math.min(22, 9 + Math.sqrt(node.weight) * 3);
}

function graphEdgePath(from: AtlasGraphNode, to: AtlasGraphNode) {
  const sourceX = from.x < to.x ? from.x + graphNodeRadius(from) : from.x - graphNodeRadius(from);
  const targetX = from.x < to.x ? to.x - graphNodeRadius(to) : to.x + graphNodeRadius(to);
  const midX = sourceX + (targetX - sourceX) / 2;
  const verticalBias = Math.abs(from.y - to.y) > 260 ? 36 : 0;
  return `M ${sourceX} ${from.y} C ${midX} ${from.y + verticalBias}, ${midX} ${to.y - verticalBias}, ${targetX} ${to.y}`;
}

function graphLabelVisible(
  node: AtlasGraphNode,
  selected: boolean,
  focused: boolean,
  focusMode: boolean
) {
  if (selected) return true;
  if (focusMode) return focused;
  if (["memory", "strategy", "source"].includes(node.type)) return true;
  if (["trade", "setup", "symbol", "emotion", "journal"].includes(node.type)) {
    return node.weight > 1;
  }
  return node.weight > 2;
}

function graphLabelLines(value: string, type: string) {
  const normalized = value.replace(/\s+/g, " ").trim();
  const maxChars = type === "trade" ? 14 : type === "tag" ? 13 : 16;
  if (normalized.length <= maxChars) return [normalized];
  const words = normalized.split(" ");
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    if (lines.length >= 2) break;
    const next = current ? `${current} ${word}` : word;
    if (next.length <= maxChars) {
      current = next;
    } else if (current) {
      lines.push(current);
      current = word;
    } else {
      lines.push(word.slice(0, maxChars));
    }
  }
  if (current && lines.length < 2) lines.push(current);
  if (lines.join(" ").length < normalized.length && lines.length) {
    const last = lines.length - 1;
    lines[last] = `${lines[last].slice(0, maxChars - 1).trimEnd()}…`;
  }
  return lines.slice(0, 2);
}
