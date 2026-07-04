"use client";

import {
  Activity,
  BookMarked,
  BrainCircuit,
  CalendarCheck,
  Download,
  FileText,
  GitBranch,
  Link2,
  LineChart,
  Plus,
  Search,
  ShieldCheck,
  Trash2,
  Upload
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";

import { MetricTile } from "@/components/MetricTile";

type TabKey = "vault" | "journal" | "trades" | "insights" | "graph";

type VaultItem = {
  id: string;
  title: string;
  kind: string;
  source: string;
  body: string;
  tags: string[];
  aiTags?: string[];
  strategyInfo?: GeneratedStrategyInfo | null;
  createdAt: string;
};

type GeneratedStrategyInfo = {
  name?: string | null;
  summary?: string | null;
  setup?: string | null;
  entry_rules?: string[];
  exit_rules?: string[];
  risk_rules?: string[];
  timeframe?: string | null;
  indicators?: string[];
  market?: string | null;
  confidence?: number;
};

type ImportedVaultItem = {
  title: string;
  kind: string;
  source: string;
  body: string;
  tags: string[];
  ai_tags?: string[];
  strategy_info?: GeneratedStrategyInfo | null;
  metadata?: Record<string, unknown>;
};

type JournalEntry = {
  id: string;
  date: string;
  title: string;
  emotion: string;
  routineDone: boolean;
  body: string;
  tags: string[];
  createdAt: string;
};

type TradeEntry = {
  id: string;
  symbol: string;
  side: "long" | "short";
  entryDate: string;
  entryPrice: number;
  exitPrice: number;
  quantity: number;
  fees: number;
  strategy: string;
  setup: string;
  emotion: string;
  notes: string;
  createdAt: string;
};

type WorkspaceState = {
  vault: VaultItem[];
  journal: JournalEntry[];
  trades: TradeEntry[];
};

type StrategyStat = {
  name: string;
  count: number;
  wins: number;
  losses: number;
  winRate: number;
  totalPnl: number;
  avgPnl: number;
  symbols: string[];
  setups: string[];
  bestTrade: TradeEntry;
  worstTrade: TradeEntry;
};

type LabelStat = {
  label: string;
  count: number;
  wins: number;
  winRate: number;
  totalPnl: number;
  avgPnl: number;
};

type TradingInsight = {
  title: string;
  value: string;
  detail: string;
  tone: "good" | "warn" | "bad" | "neutral";
};

type GraphNodeType =
  | "memory"
  | "strategy"
  | "trade"
  | "symbol"
  | "setup"
  | "emotion"
  | "source"
  | "journal"
  | "tag";

type GraphNode = {
  id: string;
  label: string;
  type: GraphNodeType;
  detail: string;
  weight: number;
  pnl?: number;
};

type PositionedGraphNode = GraphNode & {
  x: number;
  y: number;
};

type GraphEdge = {
  id: string;
  from: string;
  to: string;
  label: string;
};

type GraphModel = {
  nodes: PositionedGraphNode[];
  edges: GraphEdge[];
};

const storageKey = "quant-labs.workspace.v1";

const tabs: Array<{ key: TabKey; label: string; icon: typeof BookMarked }> = [
  { key: "vault", label: "Vault", icon: BookMarked },
  { key: "journal", label: "Journal", icon: CalendarCheck },
  { key: "trades", label: "Trades", icon: LineChart },
  { key: "insights", label: "Insights", icon: BrainCircuit },
  { key: "graph", label: "Map", icon: GitBranch }
];

const emptyState: WorkspaceState = {
  vault: [],
  journal: [],
  trades: []
};

const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const textLikeExtensions = [".txt", ".md", ".markdown", ".csv", ".json", ".log", ".pine", ".py"];
const semanticTagRules = [
  ["opening range", "orb"],
  ["opening range breakout", "orb"],
  ["mean reversion", "mean-reversion"],
  ["trend following", "trend-following"],
  ["vwap pullback", "vwap-pullback"],
  ["stop loss", "stop-loss"],
  ["take profit", "take-profit"],
  ["risk reward", "risk-reward"],
  ["position size", "position-sizing"]
] as const;
const singleWordTags = [
  "atr",
  "backtest",
  "breakdown",
  "breakout",
  "crypto",
  "ema",
  "entry",
  "exit",
  "fomc",
  "futures",
  "journal",
  "liquidity",
  "macd",
  "momentum",
  "options",
  "orb",
  "pullback",
  "resistance",
  "reversal",
  "risk",
  "rsi",
  "scalp",
  "setup",
  "sma",
  "stop",
  "strategy",
  "support",
  "swing",
  "target",
  "trade",
  "trend",
  "volume",
  "vwap"
];
const setupRules = [
  ["opening range breakout", "Opening range breakout"],
  ["opening range", "Opening range breakout"],
  ["orb", "Opening range breakout"],
  ["vwap pullback", "VWAP pullback"],
  ["pullback", "Pullback continuation"],
  ["mean reversion", "Mean reversion"],
  ["trend following", "Trend following"],
  ["breakout", "Breakout continuation"],
  ["breakdown", "Breakdown continuation"],
  ["reversal", "Reversal"]
] as const;
const indicatorRules = [
  ["vwap", "VWAP"],
  ["ema", "EMA"],
  ["sma", "SMA"],
  ["rsi", "RSI"],
  ["macd", "MACD"],
  ["atr", "ATR"],
  ["volume", "Volume"]
] as const;
const marketRules = [
  ["futures", "futures"],
  ["options", "options"],
  ["crypto", "crypto"],
  ["forex", "forex"],
  ["equity", "equities"],
  ["stock", "equities"],
  ["spy", "equities"],
  ["qqq", "equities"],
  ["es", "futures"],
  ["nq", "futures"]
] as const;

function newId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function splitTags(value: string) {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function uniqueTags(values: Array<string | undefined | null>) {
  return Array.from(
    new Set(
      values
        .map((value) => value?.trim())
        .filter((value): value is string => Boolean(value))
    )
  );
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2
  }).format(value);
}

function tradePnl(trade: TradeEntry) {
  const direction = trade.side === "long" ? 1 : -1;
  return (trade.exitPrice - trade.entryPrice) * trade.quantity * direction - trade.fees;
}

function Field({
  label,
  children
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="grid gap-1.5 text-sm font-medium text-ink/72">
      {label}
      {children}
    </label>
  );
}

function textInputClass() {
  return "min-h-10 rounded-md border border-line bg-white px-3 text-sm text-ink outline-none transition placeholder:text-ink/35 focus:border-signal focus:ring-2 focus:ring-signal/15";
}

function textareaClass() {
  return "min-h-28 rounded-md border border-line bg-white px-3 py-2 text-sm text-ink outline-none transition placeholder:text-ink/35 focus:border-signal focus:ring-2 focus:ring-signal/15";
}

function tagChip(tag: string) {
  return (
    <span key={tag} className="rounded-md bg-paper px-2 py-1 text-xs font-medium text-ink/68">
      {tag}
    </span>
  );
}

function vaultItemFromImport(item: ImportedVaultItem): VaultItem {
  const aiTags = uniqueTags(item.ai_tags ?? []);
  const strategyInfo = item.strategy_info ?? null;

  return {
    id: newId(),
    title: item.title || "Untitled source",
    kind: item.kind || "note",
    source: item.source || "local upload",
    body: item.body || "Imported source",
    tags: uniqueTags([...(item.tags ?? []), ...aiTags]),
    aiTags,
    strategyInfo,
    createdAt: new Date().toISOString()
  };
}

function textContainsWord(text: string, word: string) {
  return new RegExp(`\\b${word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i").test(text);
}

function sourceSentences(text: string) {
  return text
    .replace(/\s+/g, " ")
    .split(/(?<=[.!?])\s+|\n+|(?:^|\s)[-*]\s+/)
    .map((sentence) => sentence.trim().replace(/^-+/, "").trim())
    .filter((sentence) => sentence.length >= 8);
}

function matchingRules(sentences: string[], needles: string[], limit = 3) {
  const rules: string[] = [];
  sentences.forEach((sentence) => {
    const lowered = sentence.toLowerCase();
    if (rules.length < limit && needles.some((needle) => lowered.includes(needle))) {
      rules.push(sentence.slice(0, 220));
    }
  });
  return rules;
}

function firstMatchingRule(
  text: string,
  rules: readonly (readonly [string, string])[]
) {
  const lowered = text.toLowerCase();
  return rules.find(([needle]) => lowered.includes(needle))?.[1] ?? null;
}

function generatedTagsForImport(item: ImportedVaultItem) {
  const text = `${item.title} ${item.source} ${item.body.slice(0, 6000)}`.toLowerCase();
  const tags = [
    ...singleWordTags.filter((tag) => textContainsWord(text, tag)),
    ...semanticTagRules.filter(([needle]) => text.includes(needle)).map(([, tag]) => tag)
  ];
  const setup = firstMatchingRule(text, setupRules);
  const market = firstMatchingRule(text, marketRules);
  if (setup) tags.push(setup.toLowerCase().replaceAll(" ", "-"));
  if (market) tags.push(market);
  indicatorRules.forEach(([needle, label]) => {
    if (textContainsWord(text, needle)) tags.push(label.toLowerCase());
  });
  if (item.kind === "strategy" || item.kind === "broker_import") tags.push(item.kind);
  if (/\b(?:1|2|3|5|10|15|30|60)[ -]?(?:m|min|minute|minutes)\b/i.test(text)) tags.push("timeframe");
  return uniqueTags(tags).sort();
}

function strategyInfoForImport(item: ImportedVaultItem, aiTags: string[]): GeneratedStrategyInfo | null {
  const text = `${item.title}\n${item.body.slice(0, 9000)}`;
  const lowered = text.toLowerCase();
  const sentences = sourceSentences(text);
  const setup = firstMatchingRule(text, setupRules);
  const indicators = indicatorRules
    .filter(([needle]) => textContainsWord(lowered, needle))
    .map(([, label]) => label)
    .sort();
  const market = firstMatchingRule(text, marketRules);
  const timeframe = text.match(/\b(?:1|2|3|5|10|15|30|60)[ -]?(?:m|min|minute|minutes)\b/i)?.[0] ?? null;
  const entryRules = matchingRules(sentences, [
    "entry",
    "enter",
    "buy",
    "long",
    "short",
    "trigger",
    "break",
    "reclaim",
    "confirmation"
  ]);
  const exitRules = matchingRules(sentences, ["exit", "target", "take profit", "profit", "sell", "cover", "trail"]);
  const riskRules = matchingRules(sentences, ["risk", "stop", "invalidation", "max loss", "position size", "size", "atr"]);
  const signalCount = [
    setup,
    indicators.length,
    timeframe,
    market,
    entryRules.length,
    exitRules.length,
    riskRules.length,
    item.kind === "strategy",
    aiTags.includes("strategy")
  ].filter(Boolean).length;

  if (signalCount < 2) return null;

  return {
    name: item.title,
    summary:
      sentences.find((sentence) => sentence.length >= 24)?.slice(0, 260) ??
      `Generated strategy context for ${item.title}.`,
    setup,
    entry_rules: entryRules,
    exit_rules: exitRules,
    risk_rules: riskRules,
    timeframe,
    indicators,
    market,
    confidence: Math.min(0.95, Number((0.25 + signalCount * 0.08).toFixed(2)))
  };
}

function enrichImportedItem(item: ImportedVaultItem): ImportedVaultItem {
  const aiTags = generatedTagsForImport(item);
  const strategyInfo = strategyInfoForImport(item, aiTags);

  return {
    ...item,
    tags: uniqueTags([...(item.tags ?? []), ...aiTags]).sort(),
    ai_tags: aiTags,
    strategy_info: strategyInfo,
    metadata: {
      ...item.metadata,
      generated_tags: aiTags,
      strategy_info: strategyInfo,
      enrichment_method: "client_semantic_rules"
    }
  };
}

function hostFromUrl(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "link";
  }
}

function fallbackLinkImport(url: string): ImportedVaultItem {
  const parsed = new URL(url);
  const pathTitle = parsed.pathname.split("/").filter(Boolean).pop()?.replaceAll("-", " ");
  const title = pathTitle || parsed.hostname.replace(/^www\./, "");
  return enrichImportedItem({
    title,
    kind: "article",
    source: url,
    body: `Imported link: ${url}`,
    tags: ["article", hostFromUrl(url)],
    metadata: { import_method: "client_url_fallback" }
  });
}

async function fallbackFileImport(file: File): Promise<ImportedVaultItem> {
  const extension = file.name.includes(".") ? `.${file.name.split(".").pop()?.toLowerCase()}` : "";
  const kind = file.type.startsWith("image/")
    ? "screenshot"
    : file.type === "application/pdf" || extension === ".pdf"
      ? "pdf"
      : extension === ".csv"
        ? "broker_import"
        : extension === ".pine" || extension === ".py"
          ? "strategy"
          : "note";
  const canReadText = file.type.startsWith("text/") || textLikeExtensions.includes(extension);
  const body = canReadText
    ? (await file.text()).slice(0, 24000)
    : `Uploaded ${kind} file: ${file.name} (${Math.max(1, Math.round(file.size / 1024))} KB).`;

  return enrichImportedItem({
    title: file.name.replace(/\.[^.]+$/, "").replaceAll("-", " ").replaceAll("_", " "),
    kind,
    source: file.name,
    body,
    tags: Array.from(new Set([kind, extension.replace(".", ""), file.type.split("/")[0]].filter(Boolean))),
    metadata: {
      import_method: "client_file_fallback",
      content_type: file.type || "application/octet-stream",
      byte_count: file.size
    }
  });
}

export function WorkspaceApp() {
  const [activeTab, setActiveTab] = useState<TabKey>("vault");
  const [state, setState] = useState<WorkspaceState>(() => {
    if (typeof window === "undefined") return emptyState;

    const saved = window.localStorage.getItem(storageKey);
    if (!saved) return emptyState;

    try {
      const parsed = JSON.parse(saved) as WorkspaceState;
      return {
        vault: parsed.vault ?? [],
        journal: parsed.journal ?? [],
        trades: parsed.trades ?? []
      };
    } catch {
      return emptyState;
    }
  });
  const [query, setQuery] = useState("");
  const [vaultUrl, setVaultUrl] = useState("");
  const [importStatus, setImportStatus] = useState<{
    tone: "idle" | "loading" | "success" | "error";
    message: string;
  }>({ tone: "idle", message: "Waiting for a link or file." });
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState("memory");

  useEffect(() => {
    window.localStorage.setItem(storageKey, JSON.stringify(state));
  }, [state]);

  const metrics = useMemo(() => {
    const netPnl = state.trades.reduce((sum, trade) => sum + tradePnl(trade), 0);
    const wins = state.trades.filter((trade) => tradePnl(trade) > 0).length;
    const winRate = state.trades.length ? Math.round((wins / state.trades.length) * 100) : 0;
    const memoryCount = state.vault.length + state.journal.length + state.trades.length;

    return [
      {
        label: "Vault",
        value: String(state.vault.length),
        detail: "documents",
        icon: <BookMarked aria-hidden="true" size={20} strokeWidth={2.1} />
      },
      {
        label: "Trades",
        value: String(state.trades.length),
        detail: `${winRate}% win rate`,
        icon: <Activity aria-hidden="true" size={20} strokeWidth={2.1} />
      },
      {
        label: "P&L",
        value: formatCurrency(netPnl),
        detail: "closed trades",
        icon: <LineChart aria-hidden="true" size={20} strokeWidth={2.1} />
      },
      {
        label: "Memory",
        value: String(memoryCount),
        detail: "local records",
        icon: <BrainCircuit aria-hidden="true" size={20} strokeWidth={2.1} />
      }
    ];
  }, [state]);

  const filteredVault = useMemo(() => {
    const needle = query.toLowerCase().trim();
    if (!needle) return state.vault;

    return state.vault.filter((item) =>
      [
        item.title,
        item.kind,
        item.source,
        item.body,
        item.tags.join(" "),
        item.aiTags?.join(" ") ?? "",
        JSON.stringify(item.strategyInfo ?? {})
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle)
    );
  }, [query, state.vault]);

  const strategyStats = useMemo(() => buildStrategyStats(state.trades), [state.trades]);
  const tradingInsights = useMemo(
    () => buildTradingInsights(state, strategyStats),
    [state, strategyStats]
  );
  const graph = useMemo(() => buildGraphModel(state), [state]);
  const graphNodeLookup = useMemo(
    () => new Map(graph.nodes.map((node) => [node.id, node])),
    [graph.nodes]
  );
  const selectedGraphNode = graphNodeLookup.get(selectedGraphNodeId) ?? graph.nodes[0];
  const selectedGraphEdges = selectedGraphNode
    ? graph.edges.filter((edge) => edge.from === selectedGraphNode.id || edge.to === selectedGraphNode.id)
    : [];

  function saveImportedVaultItem(item: ImportedVaultItem) {
    const vaultItem = vaultItemFromImport(item);
    setState((current) => ({ ...current, vault: [vaultItem, ...current.vault] }));
    setImportStatus({
      tone: "success",
      message: `Imported "${vaultItem.title}" with ${vaultItem.tags.length} tags${
        vaultItem.strategyInfo ? " and strategy fields" : ""
      }.`
    });
  }

  async function importVaultUrl(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const url = vaultUrl.trim();
    if (!url) return;
    try {
      const parsed = new URL(url);
      if (!["http:", "https:"].includes(parsed.protocol)) {
        throw new Error("Unsupported URL protocol");
      }
    } catch {
      setImportStatus({
        tone: "error",
        message: "Use a full http:// or https:// link."
      });
      return;
    }

    setImportStatus({ tone: "loading", message: "Reading link and extracting vault fields..." });
    try {
      const response = await fetch(`${apiBaseUrl}/api/v1/vault/import-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
      });
      if (!response.ok) throw new Error(await response.text());
      saveImportedVaultItem((await response.json()) as ImportedVaultItem);
    } catch {
      saveImportedVaultItem(fallbackLinkImport(url));
      setImportStatus({
        tone: "success",
        message: "Captured the link locally. Full text extraction needs the API to reach that URL."
      });
    }
    setVaultUrl("");
  }

  async function importVaultFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    setImportStatus({ tone: "loading", message: `Uploading ${file.name} and extracting fields...` });
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`${apiBaseUrl}/api/v1/vault/import-file`, {
        method: "POST",
        body: form
      });
      if (!response.ok) throw new Error(await response.text());
      saveImportedVaultItem((await response.json()) as ImportedVaultItem);
    } catch {
      saveImportedVaultItem(await fallbackFileImport(file));
      setImportStatus({
        tone: "success",
        message: "Imported the file locally. Rich parsing will improve when parser workers are added."
      });
    }
    event.target.value = "";
  }

  function addJournalEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const title = String(form.get("title") ?? "").trim();
    const body = String(form.get("body") ?? "").trim();
    if (!title || !body) return;

    const entry: JournalEntry = {
      id: newId(),
      date: String(form.get("date") || new Date().toISOString().slice(0, 10)),
      title,
      emotion: String(form.get("emotion") ?? "focused"),
      routineDone: form.get("routineDone") === "on",
      body,
      tags: splitTags(String(form.get("tags") ?? "")),
      createdAt: new Date().toISOString()
    };

    setState((current) => ({ ...current, journal: [entry, ...current.journal] }));
    event.currentTarget.reset();
  }

  function addTrade(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const symbol = String(form.get("symbol") ?? "").trim().toUpperCase();
    const entryPrice = Number(form.get("entryPrice"));
    const exitPrice = Number(form.get("exitPrice"));
    const quantity = Number(form.get("quantity"));
    if (!symbol || !entryPrice || !exitPrice || !quantity) return;

    const trade: TradeEntry = {
      id: newId(),
      symbol,
      side: String(form.get("side") ?? "long") as TradeEntry["side"],
      entryDate: String(form.get("entryDate") || new Date().toISOString().slice(0, 10)),
      entryPrice,
      exitPrice,
      quantity,
      fees: Number(form.get("fees")) || 0,
      strategy: String(form.get("strategy") ?? "").trim(),
      setup: String(form.get("setup") ?? "").trim(),
      emotion: String(form.get("emotion") ?? "focused"),
      notes: String(form.get("notes") ?? "").trim(),
      createdAt: new Date().toISOString()
    };

    setState((current) => ({ ...current, trades: [trade, ...current.trades] }));
    event.currentTarget.reset();
  }

  function removeItem(collection: keyof WorkspaceState, id: string) {
    setState((current) => ({
      ...current,
      [collection]: current[collection].filter((item) => item.id !== id)
    }));
  }

  function exportWorkspace() {
    const data = JSON.stringify(state, null, 2);
    const blob = new Blob([data], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `quant-labs-workspace-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function importWorkspace(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      const parsed = JSON.parse(String(reader.result)) as WorkspaceState;
      setState({
        vault: parsed.vault ?? [],
        journal: parsed.journal ?? [],
        trades: parsed.trades ?? []
      });
    };
    reader.readAsText(file);
    event.target.value = "";
  }

  return (
    <>
      <nav className="flex gap-2 overflow-x-auto border-b border-line bg-white/78 px-4 py-3 backdrop-blur">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.key;

          return (
            <button
              key={tab.key}
              className={[
                "inline-flex min-h-10 items-center gap-2 rounded-md border px-3 text-sm font-medium transition",
                active
                  ? "border-signal/30 bg-signal/10 text-signal"
                  : "border-transparent text-ink/62 hover:border-line hover:bg-paper"
              ].join(" ")}
              onClick={() => setActiveTab(tab.key)}
              type="button"
              title={tab.label}
            >
              <Icon aria-hidden="true" size={17} strokeWidth={2.2} />
              {tab.label}
            </button>
          );
        })}
      </nav>

      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[1fr_340px]">
        <section className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {metrics.map((metric) => (
              <MetricTile
                key={metric.label}
                label={metric.label}
                value={metric.value}
                detail={metric.detail}
                icon={metric.icon}
              />
            ))}
          </div>

          {activeTab === "vault" && (
            <section className="grid gap-4 xl:grid-cols-[360px_1fr]">
              <section className="rounded-lg border border-line bg-white/86 p-4 shadow-panel">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold text-ink">Auto Capture</h2>
                  <Upload aria-hidden="true" className="text-signal" size={20} strokeWidth={2.1} />
                </div>
                <form className="mt-4 grid gap-3" onSubmit={importVaultUrl}>
                  <label className="grid gap-1.5 text-sm font-medium text-ink/72">
                    Link
                    <div className="flex gap-2">
                      <input
                        className={`${textInputClass()} min-w-0 flex-1`}
                        onChange={(event) => setVaultUrl(event.target.value)}
                        placeholder="https://..."
                        type="url"
                        value={vaultUrl}
                      />
                      <button
                        className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-ink px-3 text-sm font-semibold text-white transition hover:bg-ink/88"
                        disabled={importStatus.tone === "loading"}
                        type="submit"
                      >
                        <Link2 aria-hidden="true" size={17} strokeWidth={2.3} />
                        Import
                      </button>
                    </div>
                  </label>
                </form>

                <div className="mt-4 grid gap-3 border-t border-line pt-4">
                  <label className="grid cursor-pointer gap-2 rounded-lg border border-dashed border-line bg-paper/45 p-4 text-center transition hover:border-signal/40 hover:bg-signal/5">
                    <Upload aria-hidden="true" className="mx-auto text-signal" size={24} strokeWidth={2.1} />
                    <span className="text-sm font-semibold text-ink">Upload a file</span>
                    <span className="text-xs text-ink/55">PDF, image, CSV, Markdown, text, JSON, Pine, Python</span>
                    <input
                      accept=".txt,.md,.markdown,.csv,.json,.pdf,.pine,.py,image/*,text/*,application/pdf"
                      className="hidden"
                      onChange={importVaultFile}
                      type="file"
                    />
                  </label>
                  <div
                    className={[
                      "rounded-md border px-3 py-2 text-sm",
                      importStatus.tone === "error"
                        ? "border-loss/25 bg-loss/10 text-loss"
                        : importStatus.tone === "success"
                          ? "border-moss/25 bg-moss/10 text-moss"
                          : "border-line bg-paper/60 text-ink/58"
                    ].join(" ")}
                  >
                    {importStatus.message}
                  </div>
                </div>

                <div className="mt-4 rounded-md border border-line bg-white p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink/48">
                    Auto-filled fields
                  </p>
                  <div className="mt-3 grid gap-2 text-sm text-ink/64">
                    <div className="flex items-center justify-between gap-3">
                      <span>Title</span>
                      <span className="font-medium text-ink">file/link metadata</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span>Type</span>
                      <span className="font-medium text-ink">MIME / extension</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span>Body</span>
                      <span className="font-medium text-ink">extracted text</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span>Tags</span>
                      <span className="font-medium text-ink">generated + source</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span>Strategy</span>
                      <span className="font-medium text-ink">setup + rules</span>
                    </div>
                  </div>
                </div>
              </section>

              <section className="rounded-lg border border-line bg-white/86 shadow-panel">
                <div className="flex flex-col gap-3 border-b border-line px-4 py-3 md:flex-row md:items-center md:justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-ink">Learning Vault</h2>
                    <p className="mt-1 text-sm text-ink/58">{filteredVault.length} records</p>
                  </div>
                  <label className="flex min-h-10 items-center gap-2 rounded-md border border-line bg-white px-3 text-sm text-ink/62">
                    <Search aria-hidden="true" size={17} />
                    <input
                      className="w-44 bg-transparent outline-none placeholder:text-ink/35"
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder="Search"
                      value={query}
                    />
                  </label>
                </div>
                <div className="divide-y divide-line">
                  {filteredVault.map((item) => {
                    const aiTags = item.aiTags ?? [];
                    const strategyInfo = item.strategyInfo;

                    return (
                      <article key={item.id} className="p-4">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <h3 className="text-sm font-semibold text-ink">{item.title}</h3>
                              <span className="rounded-md bg-signal/10 px-2 py-1 text-xs font-medium text-signal">
                                {item.kind}
                              </span>
                              {aiTags.length > 0 && (
                                <span className="rounded-md bg-caution/10 px-2 py-1 text-xs font-medium text-caution">
                                  AI tags
                                </span>
                              )}
                            </div>
                            <p className="mt-2 text-sm leading-6 text-ink/68">
                              {item.body.length > 900 ? `${item.body.slice(0, 900)}...` : item.body}
                            </p>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {item.source && tagChip(item.source)}
                              {item.tags.map(tagChip)}
                            </div>
                            {aiTags.length > 0 && (
                              <div className="mt-4 border-l-2 border-caution/35 pl-3">
                                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink/48">
                                  Generated Tags
                                </p>
                                <div className="mt-2 flex flex-wrap gap-2">{aiTags.map(tagChip)}</div>
                              </div>
                            )}
                            {strategyInfo && (
                              <StrategyInfoSummary strategyInfo={strategyInfo} />
                            )}
                          </div>
                          <button
                            className="rounded-md p-2 text-ink/45 transition hover:bg-paper hover:text-loss"
                            onClick={() => removeItem("vault", item.id)}
                            title="Delete"
                            type="button"
                          >
                            <Trash2 aria-hidden="true" size={17} />
                          </button>
                        </div>
                      </article>
                    );
                  })}
                  {!filteredVault.length && (
                    <div className="grid min-h-64 place-items-center p-6 text-center text-sm font-medium text-ink/55">
                      Vault is empty
                    </div>
                  )}
                </div>
              </section>
            </section>
          )}

          {activeTab === "journal" && (
            <section className="grid gap-4 xl:grid-cols-[360px_1fr]">
              <form
                className="rounded-lg border border-line bg-white/86 p-4 shadow-panel"
                onSubmit={addJournalEntry}
              >
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold text-ink">Journal Entry</h2>
                  <FileText aria-hidden="true" className="text-signal" size={20} strokeWidth={2.1} />
                </div>
                <div className="mt-4 grid gap-3">
                  <Field label="Date">
                    <input
                      className={textInputClass()}
                      defaultValue={new Date().toISOString().slice(0, 10)}
                      name="date"
                      type="date"
                    />
                  </Field>
                  <Field label="Title">
                    <input className={textInputClass()} name="title" required />
                  </Field>
                  <Field label="State">
                    <select className={textInputClass()} name="emotion">
                      <option value="focused">Focused</option>
                      <option value="patient">Patient</option>
                      <option value="frustrated">Frustrated</option>
                      <option value="revenge">Revenge</option>
                      <option value="tired">Tired</option>
                    </select>
                  </Field>
                  <Field label="Tags">
                    <input className={textInputClass()} name="tags" placeholder="prep, fomc, routine" />
                  </Field>
                  <label className="flex items-center gap-2 text-sm font-medium text-ink/72">
                    <input className="h-4 w-4 accent-signal" name="routineDone" type="checkbox" />
                    Routine complete
                  </label>
                  <Field label="Review">
                    <textarea className={textareaClass()} name="body" required />
                  </Field>
                  <button
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-ink px-3 text-sm font-semibold text-white transition hover:bg-ink/88"
                    type="submit"
                  >
                    <Plus aria-hidden="true" size={17} strokeWidth={2.3} />
                    Save entry
                  </button>
                </div>
              </form>

              <section className="rounded-lg border border-line bg-white/86 shadow-panel">
                <div className="border-b border-line px-4 py-3">
                  <h2 className="text-base font-semibold text-ink">Journal</h2>
                  <p className="mt-1 text-sm text-ink/58">{state.journal.length} entries</p>
                </div>
                <div className="divide-y divide-line">
                  {state.journal.map((entry) => (
                    <article key={entry.id} className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-sm font-semibold text-ink">{entry.title}</h3>
                            <span className="text-xs font-medium text-ink/50">{entry.date}</span>
                            <span className="rounded-md bg-paper px-2 py-1 text-xs font-medium text-ink/68">
                              {entry.emotion}
                            </span>
                            {entry.routineDone && (
                              <span className="rounded-md bg-moss/10 px-2 py-1 text-xs font-medium text-moss">
                                routine
                              </span>
                            )}
                          </div>
                          <p className="mt-2 text-sm leading-6 text-ink/68">{entry.body}</p>
                          <div className="mt-3 flex flex-wrap gap-2">{entry.tags.map(tagChip)}</div>
                        </div>
                        <button
                          className="rounded-md p-2 text-ink/45 transition hover:bg-paper hover:text-loss"
                          onClick={() => removeItem("journal", entry.id)}
                          title="Delete"
                          type="button"
                        >
                          <Trash2 aria-hidden="true" size={17} />
                        </button>
                      </div>
                    </article>
                  ))}
                  {!state.journal.length && (
                    <div className="grid min-h-64 place-items-center p-6 text-center text-sm font-medium text-ink/55">
                      Journal is empty
                    </div>
                  )}
                </div>
              </section>
            </section>
          )}

          {activeTab === "trades" && (
            <section className="grid gap-4 xl:grid-cols-[360px_1fr]">
              <form
                className="rounded-lg border border-line bg-white/86 p-4 shadow-panel"
                onSubmit={addTrade}
              >
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold text-ink">Trade Log</h2>
                  <Activity aria-hidden="true" className="text-signal" size={20} strokeWidth={2.1} />
                </div>
                <div className="mt-4 grid gap-3">
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Symbol">
                      <input className={textInputClass()} name="symbol" required />
                    </Field>
                    <Field label="Side">
                      <select className={textInputClass()} name="side">
                        <option value="long">Long</option>
                        <option value="short">Short</option>
                      </select>
                    </Field>
                  </div>
                  <Field label="Date">
                    <input
                      className={textInputClass()}
                      defaultValue={new Date().toISOString().slice(0, 10)}
                      name="entryDate"
                      type="date"
                    />
                  </Field>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Entry">
                      <input className={textInputClass()} name="entryPrice" required step="0.01" type="number" />
                    </Field>
                    <Field label="Exit">
                      <input className={textInputClass()} name="exitPrice" required step="0.01" type="number" />
                    </Field>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Qty">
                      <input className={textInputClass()} name="quantity" required step="0.01" type="number" />
                    </Field>
                    <Field label="Fees">
                      <input className={textInputClass()} name="fees" step="0.01" type="number" />
                    </Field>
                  </div>
                  <Field label="Strategy">
                    <input className={textInputClass()} name="strategy" placeholder="VWAP Pullback" />
                  </Field>
                  <Field label="Setup">
                    <input className={textInputClass()} name="setup" placeholder="Reclaim, ORB, fade" />
                  </Field>
                  <Field label="State">
                    <select className={textInputClass()} name="emotion">
                      <option value="focused">Focused</option>
                      <option value="patient">Patient</option>
                      <option value="chased">Chased</option>
                      <option value="frustrated">Frustrated</option>
                      <option value="tired">Tired</option>
                    </select>
                  </Field>
                  <Field label="Notes">
                    <textarea className={textareaClass()} name="notes" />
                  </Field>
                  <button
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-ink px-3 text-sm font-semibold text-white transition hover:bg-ink/88"
                    type="submit"
                  >
                    <Plus aria-hidden="true" size={17} strokeWidth={2.3} />
                    Log trade
                  </button>
                </div>
              </form>

              <section className="overflow-hidden rounded-lg border border-line bg-white/86 shadow-panel">
                <div className="border-b border-line px-4 py-3">
                  <h2 className="text-base font-semibold text-ink">Trades</h2>
                  <p className="mt-1 text-sm text-ink/58">{state.trades.length} closed trades</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[760px] border-collapse text-left text-sm">
                    <thead className="bg-paper text-xs uppercase text-ink/54">
                      <tr>
                        <th className="px-4 py-3">Date</th>
                        <th className="px-4 py-3">Symbol</th>
                        <th className="px-4 py-3">Side</th>
                        <th className="px-4 py-3">Strategy</th>
                        <th className="px-4 py-3">P&L</th>
                        <th className="px-4 py-3">State</th>
                        <th className="px-4 py-3" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {state.trades.map((trade) => {
                        const pnl = tradePnl(trade);

                        return (
                          <tr key={trade.id}>
                            <td className="px-4 py-3 text-ink/62">{trade.entryDate}</td>
                            <td className="px-4 py-3 font-semibold text-ink">{trade.symbol}</td>
                            <td className="px-4 py-3 capitalize text-ink/68">{trade.side}</td>
                            <td className="px-4 py-3 text-ink/68">{trade.strategy || "Untitled"}</td>
                            <td
                              className={[
                                "px-4 py-3 font-semibold",
                                pnl >= 0 ? "text-moss" : "text-loss"
                              ].join(" ")}
                            >
                              {formatCurrency(pnl)}
                            </td>
                            <td className="px-4 py-3 text-ink/68">{trade.emotion}</td>
                            <td className="px-4 py-3 text-right">
                              <button
                                className="rounded-md p-2 text-ink/45 transition hover:bg-paper hover:text-loss"
                                onClick={() => removeItem("trades", trade.id)}
                                title="Delete"
                                type="button"
                              >
                                <Trash2 aria-hidden="true" size={17} />
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  {!state.trades.length && (
                    <div className="grid min-h-64 place-items-center p-6 text-center text-sm font-medium text-ink/55">
                      Trade log is empty
                    </div>
                  )}
                </div>
              </section>
            </section>
          )}

          {activeTab === "insights" && (
            <section className="grid gap-4 xl:grid-cols-[1fr_380px]">
              <section className="rounded-lg border border-line bg-white/86 p-4 shadow-panel">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <h2 className="text-base font-semibold text-ink">Trading Insights</h2>
                    <p className="mt-1 text-sm text-ink/58">
                      {state.trades.length} trades, {strategyStats.length} strategies
                    </p>
                  </div>
                  <BrainCircuit aria-hidden="true" className="text-signal" size={21} strokeWidth={2.1} />
                </div>

                <div className="mt-5 grid gap-3 md:grid-cols-2">
                  {tradingInsights.map((insight) => (
                    <InsightCard insight={insight} key={insight.title} />
                  ))}
                </div>
              </section>

              <section className="overflow-hidden rounded-lg border border-line bg-white/86 shadow-panel">
                <div className="flex items-center justify-between border-b border-line px-4 py-3">
                  <div>
                    <h2 className="text-base font-semibold text-ink">Strategy Scoreboard</h2>
                    <p className="mt-1 text-sm text-ink/58">ranked by realized P&L</p>
                  </div>
                  <ShieldCheck aria-hidden="true" className="text-moss" size={20} strokeWidth={2.1} />
                </div>
                <div className="divide-y divide-line">
                  {strategyStats.map((stat) => (
                    <article key={stat.name} className="p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="text-sm font-semibold text-ink">{stat.name}</h3>
                          <p className="mt-1 text-xs font-medium text-ink/52">
                            {stat.count} trades / {stat.winRate}% win rate
                          </p>
                        </div>
                        <span
                          className={[
                            "rounded-md px-2 py-1 text-xs font-semibold",
                            stat.totalPnl >= 0 ? "bg-moss/10 text-moss" : "bg-loss/10 text-loss"
                          ].join(" ")}
                        >
                          {formatCurrency(stat.totalPnl)}
                        </span>
                      </div>
                      <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
                        <SnapshotRow label="Avg" value={formatCurrency(stat.avgPnl)} />
                        <SnapshotRow label="Best" value={formatCurrency(tradePnl(stat.bestTrade))} />
                        <SnapshotRow label="Worst" value={formatCurrency(tradePnl(stat.worstTrade))} />
                      </div>
                      <div className="mt-4 flex flex-wrap gap-2">
                        {stat.symbols.slice(0, 4).map(tagChip)}
                        {stat.setups.slice(0, 3).map(tagChip)}
                      </div>
                    </article>
                  ))}
                  {!strategyStats.length && (
                    <div className="grid min-h-64 place-items-center p-6 text-center text-sm font-medium text-ink/55">
                      No strategy stats yet
                    </div>
                  )}
                </div>
              </section>
            </section>
          )}

          {activeTab === "graph" && (
            <section className="grid gap-4 xl:grid-cols-[1fr_360px]">
              <section className="rounded-lg border border-line bg-white/86 p-4 shadow-panel">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <h2 className="text-base font-semibold text-ink">Obsidian Map</h2>
                    <p className="mt-1 text-sm text-ink/58">
                      {graph.nodes.length} nodes / {graph.edges.length} edges
                    </p>
                  </div>
                  <GitBranch aria-hidden="true" className="text-signal" size={21} strokeWidth={2.1} />
                </div>

                <div className="mt-5 overflow-hidden rounded-lg border border-ink/10 bg-[#171a1d]">
                  <svg
                    aria-label="Trading relationship map"
                    className="h-[520px] w-full"
                    role="img"
                    viewBox="0 0 920 560"
                  >
                    <rect fill="#171a1d" height="560" width="920" x="0" y="0" />
                    {graph.edges.map((edge) => {
                      const from = graphNodeLookup.get(edge.from);
                      const to = graphNodeLookup.get(edge.to);
                      if (!from || !to) return null;

                      return (
                        <line
                          key={edge.id}
                          opacity={selectedGraphNode && (edge.from === selectedGraphNode.id || edge.to === selectedGraphNode.id) ? 0.72 : 0.22}
                          stroke="#d8d1c3"
                          strokeWidth={selectedGraphNode && (edge.from === selectedGraphNode.id || edge.to === selectedGraphNode.id) ? 1.6 : 1}
                          x1={from.x}
                          x2={to.x}
                          y1={from.y}
                          y2={to.y}
                        />
                      );
                    })}
                    {graph.nodes.map((node) => {
                      const style = graphNodeStyle(node.type);
                      const selected = selectedGraphNode?.id === node.id;

                      return (
                        <g
                          className="cursor-pointer outline-none"
                          key={node.id}
                          onClick={() => setSelectedGraphNodeId(node.id)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              setSelectedGraphNodeId(node.id);
                            }
                          }}
                          role="button"
                          tabIndex={0}
                        >
                          <circle
                            cx={node.x}
                            cy={node.y}
                            fill={style.fill}
                            r={graphNodeRadius(node)}
                            stroke={selected ? "#ffffff" : style.stroke}
                            strokeWidth={selected ? 3 : 1.5}
                          />
                          <text
                            fill="#f7f3ea"
                            fontSize="11"
                            fontWeight={600}
                            opacity={selected ? 1 : 0.78}
                            textAnchor="middle"
                            x={node.x}
                            y={node.y + graphNodeRadius(node) + 16}
                          >
                            {shortLabel(node.label, node.type === "trade" ? 12 : 18)}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                </div>
              </section>

              <section className="rounded-lg border border-line bg-white/86 p-4 shadow-panel">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold text-ink">Node Detail</h2>
                  <ShieldCheck aria-hidden="true" className="text-moss" size={20} strokeWidth={2.1} />
                </div>
                {selectedGraphNode && (
                  <div className="mt-4">
                    <span className="rounded-md bg-paper px-2 py-1 text-xs font-semibold uppercase text-ink/54">
                      {selectedGraphNode.type}
                    </span>
                    <h3 className="mt-3 text-lg font-semibold text-ink">{selectedGraphNode.label}</h3>
                    <p className="mt-2 text-sm leading-6 text-ink/64">{selectedGraphNode.detail}</p>
                    {selectedGraphNode.pnl !== undefined && (
                      <p
                        className={[
                          "mt-3 text-sm font-semibold",
                          selectedGraphNode.pnl >= 0 ? "text-moss" : "text-loss"
                        ].join(" ")}
                      >
                        {formatCurrency(selectedGraphNode.pnl)}
                      </p>
                    )}
                  </div>
                )}

                <div className="mt-5 border-t border-line pt-4">
                  <h3 className="text-sm font-semibold text-ink">Connections</h3>
                  <div className="mt-3 grid gap-2">
                    {selectedGraphEdges.slice(0, 12).map((edge) => {
                      const otherId = edge.from === selectedGraphNode?.id ? edge.to : edge.from;
                      const other = graphNodeLookup.get(otherId);

                      return (
                        <button
                          className="flex min-h-10 items-center justify-between gap-3 rounded-md border border-line bg-white px-3 text-left text-sm transition hover:bg-paper"
                          key={edge.id}
                          onClick={() => other && setSelectedGraphNodeId(other.id)}
                          type="button"
                        >
                          <span className="font-medium text-ink">{other?.label ?? "Unknown"}</span>
                          <span className="text-xs font-medium text-ink/48">{edge.label}</span>
                        </button>
                      );
                    })}
                    {!selectedGraphEdges.length && (
                      <div className="rounded-md border border-line bg-paper/60 px-3 py-3 text-sm font-medium text-ink/52">
                        No connections yet
                      </div>
                    )}
                  </div>
                </div>
              </section>
            </section>
          )}
        </section>

        <aside className="space-y-6">
          <section className="rounded-lg border border-line bg-white/86 p-4 shadow-panel">
            <h2 className="text-base font-semibold text-ink">Workspace</h2>
            <div className="mt-4 grid gap-2">
              <button
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-line bg-white px-3 text-sm font-semibold text-ink transition hover:bg-paper"
                onClick={exportWorkspace}
                type="button"
              >
                <Download aria-hidden="true" size={17} strokeWidth={2.2} />
                Export JSON
              </button>
              <label className="inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-md border border-line bg-white px-3 text-sm font-semibold text-ink transition hover:bg-paper">
                <Upload aria-hidden="true" size={17} strokeWidth={2.2} />
                Import JSON
                <input accept="application/json" className="hidden" onChange={importWorkspace} type="file" />
              </label>
            </div>
          </section>

          <section className="rounded-lg border border-line bg-white/86 p-4 shadow-panel">
            <h2 className="text-base font-semibold text-ink">Pattern Snapshot</h2>
            <div className="mt-4 space-y-3 text-sm">
              <SnapshotRow label="Best trade" value={bestTradeLabel(state.trades)} />
              <SnapshotRow label="Worst trade" value={worstTradeLabel(state.trades)} />
              <SnapshotRow label="Top strategy" value={topStrategyLabel(state.trades)} />
              <SnapshotRow label="Routine days" value={String(state.journal.filter((entry) => entry.routineDone).length)} />
            </div>
          </section>
        </aside>
      </div>
    </>
  );
}

function StrategyInfoSummary({ strategyInfo }: { strategyInfo: GeneratedStrategyInfo }) {
  const detailRows = [
    ["Setup", strategyInfo.setup],
    ["Timeframe", strategyInfo.timeframe],
    ["Market", strategyInfo.market],
    ["Confidence", strategyInfo.confidence !== undefined ? `${Math.round(strategyInfo.confidence * 100)}%` : null]
  ].filter((row): row is [string, string] => Boolean(row[1]));

  return (
    <div className="mt-4 border-l-2 border-signal/35 pl-3">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink/48">
        Strategy Info
      </p>
      {strategyInfo.summary && (
        <p className="mt-2 text-sm leading-6 text-ink/68">{strategyInfo.summary}</p>
      )}
      {detailRows.length > 0 && (
        <div className="mt-3 grid gap-2 text-sm md:grid-cols-2">
          {detailRows.map(([label, value]) => (
            <div className="flex items-center justify-between gap-3" key={label}>
              <span className="text-ink/55">{label}</span>
              <span className="text-right font-medium text-ink">{value}</span>
            </div>
          ))}
        </div>
      )}
      {strategyInfo.indicators?.length ? (
        <div className="mt-3 flex flex-wrap gap-2">{strategyInfo.indicators.map(tagChip)}</div>
      ) : null}
      <StrategyRuleList label="Entry" values={strategyInfo.entry_rules ?? []} />
      <StrategyRuleList label="Exit" values={strategyInfo.exit_rules ?? []} />
      <StrategyRuleList label="Risk" values={strategyInfo.risk_rules ?? []} />
    </div>
  );
}

function StrategyRuleList({ label, values }: { label: string; values: string[] }) {
  if (!values.length) return null;

  return (
    <div className="mt-3">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink/45">{label}</p>
      <ul className="mt-1 grid gap-1 text-sm leading-6 text-ink/66">
        {values.map((value) => (
          <li key={value}>{value}</li>
        ))}
      </ul>
    </div>
  );
}

function InsightCard({ insight }: { insight: TradingInsight }) {
  const toneClass: Record<TradingInsight["tone"], string> = {
    good: "border-moss/25 bg-moss/10",
    warn: "border-caution/30 bg-caution/10",
    bad: "border-loss/25 bg-loss/10",
    neutral: "border-line bg-paper/58"
  };
  const valueClass: Record<TradingInsight["tone"], string> = {
    good: "text-moss",
    warn: "text-caution",
    bad: "text-loss",
    neutral: "text-ink"
  };

  return (
    <article className={`min-h-36 rounded-lg border p-4 ${toneClass[insight.tone]}`}>
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink/50">{insight.title}</p>
      <p className={`mt-3 text-2xl font-semibold leading-none ${valueClass[insight.tone]}`}>
        {insight.value}
      </p>
      <p className="mt-3 text-sm leading-6 text-ink/66">{insight.detail}</p>
    </article>
  );
}

function SnapshotRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-ink/58">{label}</span>
      <span className="text-right font-medium text-ink">{value}</span>
    </div>
  );
}

function buildStrategyStats(trades: TradeEntry[]): StrategyStat[] {
  const groups = trades.reduce<Record<string, TradeEntry[]>>((acc, trade) => {
    const key = trade.strategy.trim() || "Untitled strategy";
    acc[key] = [...(acc[key] ?? []), trade];
    return acc;
  }, {});

  return Object.entries(groups)
    .map(([name, group]) => {
      const sorted = [...group].sort((a, b) => tradePnl(b) - tradePnl(a));
      const bestTrade = sorted[0];
      const worstTrade = sorted[sorted.length - 1];
      if (!bestTrade || !worstTrade) return null;

      const pnls = group.map(tradePnl);
      const totalPnl = pnls.reduce((sum, pnl) => sum + pnl, 0);
      const wins = pnls.filter((pnl) => pnl > 0).length;
      const losses = pnls.filter((pnl) => pnl < 0).length;
      const symbols = Array.from(new Set(group.map((trade) => trade.symbol).filter(Boolean)));
      const setups = Array.from(new Set(group.map((trade) => trade.setup).filter(Boolean)));

      return {
        name,
        count: group.length,
        wins,
        losses,
        winRate: Math.round((wins / group.length) * 100),
        totalPnl,
        avgPnl: totalPnl / group.length,
        symbols,
        setups,
        bestTrade,
        worstTrade
      };
    })
    .filter((stat): stat is StrategyStat => Boolean(stat))
    .sort((a, b) => b.totalPnl - a.totalPnl);
}

function buildLabelStats(trades: TradeEntry[], labelFor: (trade: TradeEntry) => string): LabelStat[] {
  const groups = trades.reduce<Record<string, TradeEntry[]>>((acc, trade) => {
    const key = labelFor(trade).trim() || "Unlabeled";
    acc[key] = [...(acc[key] ?? []), trade];
    return acc;
  }, {});

  return Object.entries(groups)
    .map(([label, group]) => {
      const pnls = group.map(tradePnl);
      const totalPnl = pnls.reduce((sum, pnl) => sum + pnl, 0);
      const wins = pnls.filter((pnl) => pnl > 0).length;

      return {
        label,
        count: group.length,
        wins,
        winRate: Math.round((wins / group.length) * 100),
        totalPnl,
        avgPnl: totalPnl / group.length
      };
    })
    .sort((a, b) => b.totalPnl - a.totalPnl);
}

function buildTradingInsights(state: WorkspaceState, strategyStats: StrategyStat[]): TradingInsight[] {
  if (!state.trades.length) {
    const strategySources = state.vault.filter((item) => item.strategyInfo);

    return [
      {
        title: "Strategy Edge",
        value: "Waiting",
        detail: "Log closed trades with strategy, setup, and state labels to calculate edge.",
        tone: "neutral"
      },
      {
        title: "Strategy Research",
        value: `${strategySources.length} sources`,
        detail: strategySources.length
          ? "Generated strategy fields are ready in the vault and map."
          : "Upload strategy notes or links to generate setup, entry, exit, and risk fields.",
        tone: strategySources.length ? "good" : "neutral"
      },
      {
        title: "Vault Coverage",
        value: `${state.vault.length} sources`,
        detail: "Captured links and uploads will appear on the map as evidence nodes.",
        tone: state.vault.length ? "good" : "neutral"
      }
    ];
  }

  const totalPnl = state.trades.reduce((sum, trade) => sum + tradePnl(trade), 0);
  const wins = state.trades.filter((trade) => tradePnl(trade) > 0).length;
  const winRate = Math.round((wins / state.trades.length) * 100);
  const setupStats = buildLabelStats(state.trades, (trade) => trade.setup || "No setup");
  const emotionStats = buildLabelStats(state.trades, (trade) => trade.emotion || "No state");
  const bestStrategy = strategyStats[0];
  const worstStrategy = [...strategyStats].sort((a, b) => a.totalPnl - b.totalPnl)[0];
  const bestSetup = setupStats[0];
  const worstEmotion = [...emotionStats].sort((a, b) => a.totalPnl - b.totalPnl)[0];
  const routineDates = new Set(state.journal.filter((entry) => entry.routineDone).map((entry) => entry.date));
  const routineTrades = state.trades.filter((trade) => routineDates.has(trade.entryDate));
  const nonRoutineTrades = state.trades.filter((trade) => !routineDates.has(trade.entryDate));
  const strategySources = state.vault.filter((item) => item.strategyInfo);
  const insights: TradingInsight[] = [
    {
      title: "Net Edge",
      value: formatCurrency(totalPnl),
      detail: `${state.trades.length} closed trades at ${winRate}% win rate.`,
      tone: totalPnl > 0 ? "good" : totalPnl < 0 ? "bad" : "neutral"
    }
  ];

  if (strategySources.length) {
    const generatedTagCount = strategySources.reduce((sum, item) => sum + (item.aiTags?.length ?? 0), 0);
    insights.push({
      title: "Strategy Research",
      value: `${strategySources.length} sources`,
      detail: `${generatedTagCount} generated tags connected to the map.`,
      tone: "good"
    });
  }

  if (bestStrategy) {
    insights.push({
      title: "Best Strategy",
      value: bestStrategy.name,
      detail: `${formatCurrency(bestStrategy.totalPnl)} across ${bestStrategy.count} trades; ${bestStrategy.winRate}% win rate.`,
      tone: bestStrategy.totalPnl >= 0 ? "good" : "warn"
    });
  }

  if (worstStrategy) {
    insights.push({
      title: worstStrategy.totalPnl < 0 ? "Strategy Leak" : "Weakest Sample",
      value: worstStrategy.name,
      detail: `${formatCurrency(worstStrategy.totalPnl)} total, ${formatCurrency(worstStrategy.avgPnl)} average trade.`,
      tone: worstStrategy.totalPnl < 0 ? "bad" : "warn"
    });
  }

  if (bestSetup) {
    insights.push({
      title: "Best Setup",
      value: bestSetup.label,
      detail: `${formatCurrency(bestSetup.totalPnl)} across ${bestSetup.count} trades; ${bestSetup.winRate}% win rate.`,
      tone: bestSetup.totalPnl >= 0 ? "good" : "warn"
    });
  }

  if (worstEmotion) {
    insights.push({
      title: "State Drag",
      value: worstEmotion.label,
      detail: `${formatCurrency(worstEmotion.totalPnl)} total when this state was tagged.`,
      tone: worstEmotion.totalPnl < 0 ? "bad" : "neutral"
    });
  }

  if (routineTrades.length && nonRoutineTrades.length) {
    const routineAverage = averagePnl(routineTrades);
    const nonRoutineAverage = averagePnl(nonRoutineTrades);
    const delta = routineAverage - nonRoutineAverage;
    insights.push({
      title: "Routine Effect",
      value: formatCurrency(delta),
      detail: `${formatCurrency(routineAverage)} avg on routine days vs ${formatCurrency(nonRoutineAverage)} otherwise.`,
      tone: delta > 0 ? "good" : delta < 0 ? "bad" : "neutral"
    });
  } else {
    insights.push({
      title: "Journal Coverage",
      value: `${state.journal.length} entries`,
      detail: "Routine comparisons activate once trades exist on both routine and non-routine days.",
      tone: state.journal.length ? "warn" : "neutral"
    });
  }

  return insights.slice(0, 6);
}

function averagePnl(trades: TradeEntry[]) {
  if (!trades.length) return 0;
  return trades.reduce((sum, trade) => sum + tradePnl(trade), 0) / trades.length;
}

function buildGraphModel(state: WorkspaceState): GraphModel {
  const nodes = new Map<string, GraphNode>();
  const edgeIds = new Set<string>();
  const edges: GraphEdge[] = [];
  const memoryId = "memory";

  addGraphNode(nodes, {
    id: memoryId,
    label: "Trading Memory",
    type: "memory",
    detail: `${state.trades.length} trades, ${state.journal.length} journal entries, ${state.vault.length} vault sources.`,
    weight: Math.max(1, state.trades.length + state.journal.length + state.vault.length)
  });

  buildStrategyStats(state.trades).forEach((stat) => {
    addGraphNode(nodes, {
      id: graphId("strategy", stat.name),
      label: stat.name,
      type: "strategy",
      detail: `${formatCurrency(stat.totalPnl)} across ${stat.count} trades; ${stat.winRate}% win rate.`,
      weight: stat.count,
      pnl: stat.totalPnl
    });
    addGraphEdge(edges, edgeIds, memoryId, graphId("strategy", stat.name), "strategy");
  });

  state.trades.forEach((trade) => {
    const pnl = tradePnl(trade);
    const tradeId = `trade:${trade.id}`;
    const strategyLabel = trade.strategy.trim() || "Untitled strategy";
    const strategyId = graphId("strategy", strategyLabel);
    const symbolId = graphId("symbol", trade.symbol);
    const setupLabel = trade.setup.trim() || "No setup";
    const setupId = graphId("setup", setupLabel);
    const emotionLabel = trade.emotion.trim() || "No state";
    const emotionId = graphId("emotion", emotionLabel);

    addGraphNode(nodes, {
      id: tradeId,
      label: `${trade.symbol} ${trade.entryDate}`,
      type: "trade",
      detail: `${trade.side} trade using ${strategyLabel}. ${trade.notes || "No notes captured."}`,
      weight: 1,
      pnl
    });
    addGraphNode(nodes, {
      id: symbolId,
      label: trade.symbol,
      type: "symbol",
      detail: "Symbol traded in this workspace.",
      weight: 1,
      pnl
    });
    addGraphNode(nodes, {
      id: setupId,
      label: setupLabel,
      type: "setup",
      detail: "Execution setup label from the trade log.",
      weight: 1,
      pnl
    });
    addGraphNode(nodes, {
      id: emotionId,
      label: emotionLabel,
      type: "emotion",
      detail: "Trader state captured with trades or journal entries.",
      weight: 1,
      pnl
    });

    addGraphEdge(edges, edgeIds, memoryId, tradeId, "trade");
    addGraphEdge(edges, edgeIds, tradeId, strategyId, "strategy");
    addGraphEdge(edges, edgeIds, tradeId, symbolId, "symbol");
    addGraphEdge(edges, edgeIds, tradeId, setupId, "setup");
    addGraphEdge(edges, edgeIds, tradeId, emotionId, "state");
  });

  state.journal.forEach((entry) => {
    const journalId = `journal:${entry.id}`;
    const emotionId = graphId("emotion", entry.emotion || "No state");

    addGraphNode(nodes, {
      id: journalId,
      label: entry.title,
      type: "journal",
      detail: `${entry.date}. ${entry.body}`,
      weight: 1
    });
    addGraphNode(nodes, {
      id: emotionId,
      label: entry.emotion || "No state",
      type: "emotion",
      detail: "Trader state captured with trades or journal entries.",
      weight: 1
    });
    addGraphEdge(edges, edgeIds, memoryId, journalId, "journal");
    addGraphEdge(edges, edgeIds, journalId, emotionId, "state");

    if (entry.routineDone) {
      const routineId = graphId("tag", "routine complete");
      addGraphNode(nodes, {
        id: routineId,
        label: "routine complete",
        type: "tag",
        detail: "Journal entries marked with completed routine.",
        weight: 1
      });
      addGraphEdge(edges, edgeIds, journalId, routineId, "routine");
    }

    entry.tags.forEach((tag) => {
      const tagId = graphId("tag", tag);
      addGraphNode(nodes, {
        id: tagId,
        label: tag,
        type: "tag",
        detail: "Journal or vault tag.",
        weight: 1
      });
      addGraphEdge(edges, edgeIds, journalId, tagId, "tag");
    });
  });

  state.vault.forEach((item) => {
    const sourceId = `source:${item.id}`;
    const strategyInfo = item.strategyInfo;
    addGraphNode(nodes, {
      id: sourceId,
      label: item.title,
      type: "source",
      detail: `${item.kind} from ${item.source || "local upload"}. ${item.body.slice(0, 220)}`,
      weight: 1
    });
    addGraphEdge(edges, edgeIds, memoryId, sourceId, "source");

    if (
      strategyInfo ||
      item.kind === "strategy" ||
      item.tags.some((tag) => tag.toLowerCase().includes("strategy"))
    ) {
      const strategyName = strategyInfo?.name || item.title;
      const strategyId = graphId("strategy", strategyName);
      addGraphNode(nodes, {
        id: strategyId,
        label: strategyName,
        type: "strategy",
        detail: strategyInfo?.summary || "Strategy research captured in the vault.",
        weight: 1
      });
      addGraphEdge(edges, edgeIds, sourceId, strategyId, strategyInfo ? "strategy info" : "strategy note");

      if (strategyInfo?.setup) {
        const setupId = graphId("setup", strategyInfo.setup);
        addGraphNode(nodes, {
          id: setupId,
          label: strategyInfo.setup,
          type: "setup",
          detail: "Generated setup from imported strategy information.",
          weight: 1
        });
        addGraphEdge(edges, edgeIds, strategyId, setupId, "setup");
      }

      [strategyInfo?.market, strategyInfo?.timeframe, ...(strategyInfo?.indicators ?? [])]
        .filter((tag): tag is string => Boolean(tag))
        .forEach((tag) => {
          const tagId = graphId("tag", tag);
          addGraphNode(nodes, {
            id: tagId,
            label: tag,
            type: "tag",
            detail: "Generated strategy attribute.",
            weight: 1
          });
          addGraphEdge(edges, edgeIds, strategyId, tagId, "attribute");
        });
    }

    uniqueTags([item.kind, ...item.tags, ...(item.aiTags ?? [])]).forEach((tag) => {
      const tagId = graphId("tag", tag);
      addGraphNode(nodes, {
        id: tagId,
        label: tag,
        type: "tag",
        detail: "Journal or vault tag.",
        weight: 1
      });
      addGraphEdge(edges, edgeIds, sourceId, tagId, "tag");
    });
  });

  return {
    nodes: positionGraphNodes(Array.from(nodes.values())),
    edges
  };
}

function addGraphNode(nodes: Map<string, GraphNode>, next: GraphNode) {
  const current = nodes.get(next.id);
  if (!current) {
    nodes.set(next.id, next);
    return;
  }

  current.weight += next.weight;
  if (next.pnl !== undefined) {
    current.pnl = (current.pnl ?? 0) + next.pnl;
  }
}

function addGraphEdge(edges: GraphEdge[], edgeIds: Set<string>, from: string, to: string, label: string) {
  if (from === to) return;
  const id = `${from}->${to}:${label}`;
  if (edgeIds.has(id)) return;
  edgeIds.add(id);
  edges.push({ id, from, to, label });
}

function graphId(type: GraphNodeType, value: string) {
  const slug = value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `${type}:${slug || "untitled"}`;
}

function positionGraphNodes(nodes: GraphNode[]): PositionedGraphNode[] {
  const centerX = 460;
  const centerY = 280;
  const config: Record<GraphNodeType, { radius: number; offset: number }> = {
    memory: { radius: 0, offset: 0 },
    strategy: { radius: 112, offset: -0.8 },
    trade: { radius: 176, offset: 0.15 },
    symbol: { radius: 238, offset: -1.2 },
    setup: { radius: 232, offset: 0.72 },
    emotion: { radius: 144, offset: 1.8 },
    source: { radius: 216, offset: 2.7 },
    journal: { radius: 198, offset: -2.7 },
    tag: { radius: 248, offset: 2.05 }
  };
  const types: GraphNodeType[] = [
    "strategy",
    "trade",
    "symbol",
    "setup",
    "emotion",
    "source",
    "journal",
    "tag"
  ];
  const order = new Map<string, { index: number; total: number }>();

  types.forEach((type) => {
    const group = nodes
      .filter((node) => node.type === type)
      .sort((a, b) => b.weight - a.weight || a.label.localeCompare(b.label));
    group.forEach((node, index) => order.set(node.id, { index, total: group.length }));
  });

  return nodes.map((node) => {
    if (node.type === "memory") {
      return { ...node, x: centerX, y: centerY };
    }

    const nodeOrder = order.get(node.id) ?? { index: 0, total: 1 };
    const nodeConfig = config[node.type];
    const angle = nodeConfig.offset + (Math.PI * 2 * nodeOrder.index) / Math.max(1, nodeOrder.total);
    const radius = Math.min(252, nodeConfig.radius + Math.min(18, nodeOrder.total * 0.45));

    return {
      ...node,
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius
    };
  });
}

function graphNodeStyle(type: GraphNodeType) {
  const styles: Record<GraphNodeType, { fill: string; stroke: string }> = {
    memory: { fill: "#f7f3ea", stroke: "#ffffff" },
    strategy: { fill: "#266f83", stroke: "#8dd6e5" },
    trade: { fill: "#a85f32", stroke: "#e2a06f" },
    symbol: { fill: "#476a4d", stroke: "#9cc69f" },
    setup: { fill: "#b48924", stroke: "#e0c36e" },
    emotion: { fill: "#9f3f46", stroke: "#e79399" },
    source: { fill: "#6d5bd0", stroke: "#b8adff" },
    journal: { fill: "#2f7f62", stroke: "#94d8b9" },
    tag: { fill: "#6f6b5f", stroke: "#d8d1c3" }
  };

  return styles[type];
}

function graphNodeRadius(node: GraphNode) {
  if (node.type === "memory") return 24;
  return Math.min(20, 8 + Math.sqrt(node.weight) * 3);
}

function shortLabel(value: string, limit: number) {
  if (value.length <= limit) return value;
  return `${value.slice(0, Math.max(1, limit - 3))}...`;
}

function bestTradeLabel(trades: TradeEntry[]) {
  if (!trades.length) return "-";
  const trade = [...trades].sort((a, b) => tradePnl(b) - tradePnl(a))[0];
  if (!trade) return "-";
  return `${trade.symbol} ${formatCurrency(tradePnl(trade))}`;
}

function worstTradeLabel(trades: TradeEntry[]) {
  if (!trades.length) return "-";
  const trade = [...trades].sort((a, b) => tradePnl(a) - tradePnl(b))[0];
  if (!trade) return "-";
  return `${trade.symbol} ${formatCurrency(tradePnl(trade))}`;
}

function topStrategyLabel(trades: TradeEntry[]) {
  const topStrategy = buildStrategyStats(trades)[0];
  if (!topStrategy) return "-";
  return `${topStrategy.name} ${formatCurrency(topStrategy.totalPnl)}`;
}
