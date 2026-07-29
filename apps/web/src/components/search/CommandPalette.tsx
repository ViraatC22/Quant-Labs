"use client";

import { useEffect, useMemo, useState } from "react";

import { searchGraphNodes } from "@/features/graph/api";
import type { WorkspaceState } from "@/lib/types";

type Tab = { key: string; label: string };

type Result = {
  id: string;
  group: string;
  title: string;
  subtitle: string;
  tab: string;
  graphNodeId?: string;
};

type CommandPaletteProps = {
  state: WorkspaceState;
  tabs: Tab[];
  onSelectTab: (tab: string) => void;
  onFocusGraphNode?: (nodeId: string) => void;
  onClose: () => void;
};

function buildResults(state: WorkspaceState, tabs: Tab[], query: string): Result[] {
  const q = query.trim().toLowerCase();
  const results: Result[] = [];

  for (const tab of tabs) {
    if (!q || tab.label.toLowerCase().includes(q)) {
      results.push({ id: `tab:${tab.key}`, group: "Go to", title: tab.label, subtitle: "Tab", tab: tab.key });
    }
  }
  if (!q) return results;

  for (const item of state.vault) {
    const hay = `${item.title} ${item.tags?.join(" ") ?? ""} ${item.kind}`.toLowerCase();
    if (hay.includes(q)) {
      results.push({ id: `vault:${item.id}`, group: "Sources", title: item.title, subtitle: item.kind, tab: "vault" });
    }
  }
  for (const trade of state.trades) {
    const hay = `${trade.symbol} ${trade.strategy} ${trade.setup}`.toLowerCase();
    if (hay.includes(q)) {
      results.push({
        id: `trade:${trade.id}`,
        group: "Trades",
        title: `${trade.symbol} ${trade.side}`,
        subtitle: trade.strategy || "trade",
        tab: "trades"
      });
    }
  }
  for (const entry of state.journal) {
    const hay = `${entry.title} ${entry.body} ${entry.tags?.join(" ") ?? ""}`.toLowerCase();
    if (hay.includes(q)) {
      results.push({ id: `journal:${entry.id}`, group: "Journal", title: entry.title, subtitle: entry.date, tab: "journal" });
    }
  }
  return results.slice(0, 40);
}

// Rendered only while open (mounted fresh each time), so there is no internal
// open state or reset effects to manage. The ⌘K/Escape shortcut lives in the
// parent, which controls mounting.
export function CommandPalette({
  state,
  tabs,
  onSelectTab,
  onFocusGraphNode,
  onClose
}: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [graphResultState, setGraphResultState] = useState<{
    query: string;
    results: Result[];
  }>({ query: "", results: [] });

  useEffect(() => {
    const value = query.trim();
    if (value.length < 2) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void searchGraphNodes(value, 8, controller.signal)
        .then((nodes) => {
          setGraphResultState({
            query: value,
            results: nodes.map((node) => ({
              id: `graph:${node.id}`,
              group: "Atlas entity",
              title: node.label,
              subtitle: node.node_type,
              tab: "graph",
              graphNodeId: node.id
            }))
          });
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setGraphResultState({ query: value, results: [] });
          }
        });
    }, 180);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  const results = useMemo(
    () => [
      ...buildResults(state, tabs, query),
      ...(query.trim().length >= 2 && graphResultState.query === query.trim()
        ? graphResultState.results
        : [])
    ].slice(0, 40),
    [graphResultState, query, state, tabs]
  );
  const clampedActive = Math.min(active, Math.max(0, results.length - 1));

  function choose(result: Result | undefined) {
    if (!result) return;
    if (result.graphNodeId && onFocusGraphNode) {
      onFocusGraphNode(result.graphNodeId);
    } else {
      onSelectTab(result.tab);
    }
    onClose();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 p-4 pt-[12vh]"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Search"
    >
      <div
        className="w-full max-w-lg overflow-hidden rounded-xl border border-line bg-card shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <input
          autoFocus
          className="w-full border-b border-line bg-transparent px-4 py-3 text-sm text-ink outline-none placeholder:text-ink/40"
          placeholder="Search sources, trades, journal, Atlas entities, or tabs…"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setActive(0);
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setActive((i) => Math.min(i + 1, results.length - 1));
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setActive((i) => Math.max(i - 1, 0));
            } else if (event.key === "Enter") {
              event.preventDefault();
              choose(results[clampedActive]);
            } else if (event.key === "Escape") {
              event.preventDefault();
              onClose();
            }
          }}
        />
        <ul className="max-h-[52vh] overflow-y-auto py-1">
          {results.length === 0 && (
            <li className="px-4 py-6 text-center text-sm text-ink/45">No matches.</li>
          )}
          {results.map((result, index) => (
            <li key={result.id}>
              <button
                type="button"
                className={`flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-sm ${
                  index === clampedActive ? "bg-signal/10" : "hover:bg-ink/5"
                }`}
                onMouseEnter={() => setActive(index)}
                onClick={() => choose(result)}
              >
                <span className="min-w-0">
                  <span className="block truncate text-ink">{result.title}</span>
                  <span className="block truncate text-xs text-ink/45">{result.subtitle}</span>
                </span>
                <span className="shrink-0 rounded bg-ink/5 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-ink/45">
                  {result.group}
                </span>
              </button>
            </li>
          ))}
        </ul>
        <div className="border-t border-line px-4 py-2 text-[11px] text-ink/40">
          ↑↓ to navigate · ↵ to open · esc to close · ⌘K to toggle
        </div>
      </div>
    </div>
  );
}
