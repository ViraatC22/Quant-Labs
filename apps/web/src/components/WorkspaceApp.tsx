"use client";

import {
  Activity,
  BookMarked,
  BrainCircuit,
  CalendarCheck,
  Crosshair,
  Download,
  FileText,
  GitBranch,
  Link2,
  LineChart,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
  Wand2,
  ZoomIn,
  ZoomOut
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { MetricTile } from "@/components/MetricTile";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import * as api from "@/lib/api";
import type {
  AiRouterStatus,
  GeneratedStrategyInfo,
  JournalEntry,
  MarketQuote,
  SourceDetails,
  StrategyEvaluation,
  TradeEntry,
  TradeRecommendation,
  VaultItem,
  WorkspaceState
} from "@/lib/types";

type TabKey = "vault" | "journal" | "trades" | "routine" | "insights" | "graph";

type ImportedVaultItem = {
  title: string;
  kind: string;
  source: string;
  body: string;
  tags: string[];
  ai_tags?: string[];
  technical_tags?: string[];
  technical_profile?: Record<string, string[]>;
  source_details?: SourceDetails | null;
  strategy_info?: GeneratedStrategyInfo | null;
  metadata?: Record<string, unknown>;
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
  bestTrade?: TradeEntry;
  worstTrade?: TradeEntry;
  sourceCount: number;
  sourceTitles: string[];
  researchConfidence: number;
  researchSummary?: string;
  researchRules: string[];
  validationState: "live" | "research" | "mixed";
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

type RoutineBlock = {
  title: string;
  items: string[];
};

type RecommendedRoutine = {
  strategyName: string;
  sourceCount: number;
  confidence: number;
  validationState: StrategyStat["validationState"] | "draft";
  setupFocus: string;
  technicalTags: string[];
  blocks: RoutineBlock[];
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

type GraphClusterGuide = {
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

type SourceStrategySignal = {
  sourceId: string;
  sourceTitle: string;
  strategyName: string;
  setup?: string | null;
  summary?: string | null;
  confidence: number;
  tags: string[];
  rules: string[];
  attributes: string[];
};

type GraphViewport = {
  centerX: number;
  centerY: number;
  zoom: number;
};

type GraphDragState = {
  startX: number;
  startY: number;
  startView: GraphViewport;
};

type QuickTradeDraft = {
  symbol: string;
  side: TradeEntry["side"];
  entryDate: string;
  entryPrice: number;
  exitPrice: number | null;
  quantity: number;
  fees: number;
  strategy: string;
  setup: string;
  emotion: string;
  notes: string;
};

type TradeDraft = NonNullable<TradeRecommendation["draft"]>;

const storageKey = "quant-labs.workspace.v1";

const tabs: Array<{ key: TabKey; label: string; icon: typeof BookMarked }> = [
  { key: "vault", label: "Vault", icon: BookMarked },
  { key: "journal", label: "Journal", icon: CalendarCheck },
  { key: "trades", label: "Trades", icon: LineChart },
  { key: "routine", label: "Routine", icon: CalendarCheck },
  { key: "insights", label: "Insights", icon: BrainCircuit },
  { key: "graph", label: "Atlas", icon: GitBranch }
];

const emptyState: WorkspaceState = {
  vault: [],
  journal: [],
  trades: []
};

const graphClusterGuides: GraphClusterGuide[] = [
  { label: "Source Evidence", x: 24, y: 48, width: 220, height: 270 },
  { label: "Strategy Layer", x: 290, y: 48, width: 210, height: 270 },
  { label: "Execution Setups", x: 560, y: 48, width: 210, height: 270 },
  { label: "Trade Outcomes", x: 830, y: 48, width: 200, height: 270 },
  { label: "Journal Routine", x: 24, y: 390, width: 220, height: 180 },
  { label: "Tags", x: 290, y: 390, width: 210, height: 180 },
  { label: "States", x: 560, y: 390, width: 210, height: 180 },
  { label: "Markets", x: 830, y: 390, width: 200, height: 180 }
];
const graphCanvasWidth = 1060;
const graphCanvasHeight = 660;

const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const textLikeExtensions = [".txt", ".md", ".markdown", ".csv", ".json", ".log", ".pine", ".py"];
const semanticTagRules = [
  ["opening range", "orb"],
  ["opening range breakout", "orb"],
  ["mean reversion", "mean-reversion"],
  ["trend following", "trend-following"],
  ["risk parity", "risk-parity"],
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
  ["risk parity", "Risk parity"],
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
const technicalRules: Record<string, Array<readonly [RegExp, string, string]>> = {
  indicators: [
    [/\bvwap\b/i, "VWAP", "vwap"],
    [/\banchored\s+vwap\b|\bavwap\b/i, "Anchored VWAP", "anchored-vwap"],
    [/\bema\b|\bexponential moving average\b/i, "EMA", "ema"],
    [/\bsma\b|\bsimple moving average\b/i, "SMA", "sma"],
    [/\brsi\b|\brelative strength index\b/i, "RSI", "rsi"],
    [/\bmacd\b/i, "MACD", "macd"],
    [/\batr\b|\baverage true range\b/i, "ATR", "atr"],
    [/\badx\b/i, "ADX", "adx"],
    [/\bstochastic oscillator\b|\bstochastic indicator\b|\bstoch\b/i, "Stochastic", "stochastic"],
    [/\bbollinger\b|\bbb\b/i, "Bollinger Bands", "bollinger-bands"],
    [/\bvolume profile\b/i, "Volume profile", "volume-profile"],
    [/\brelative volume\b|\brvol\b/i, "Relative volume", "relative-volume"]
  ],
  price_action: [
    [/\bsupport\b/i, "Support", "support"],
    [/\bresistance\b/i, "Resistance", "resistance"],
    [/\btrendline\b|\btrend line\b/i, "Trendline", "trendline"],
    [/\bbreakout\b/i, "Breakout", "breakout"],
    [/\bbreakdown\b/i, "Breakdown", "breakdown"],
    [/\bpullback\b/i, "Pullback", "pullback"],
    [/\breversal\b/i, "Reversal", "reversal"],
    [/\bgap fill\b/i, "Gap fill", "gap-fill"]
  ],
  market_structure: [
    [/\bmarket structure\b/i, "Market structure", "market-structure"],
    [/\bbreak of structure\b|\bbos\b/i, "Break of structure", "break-of-structure"],
    [/\bchange of character\b|\bchoch\b/i, "Change of character", "change-of-character"],
    [/\bliquidity sweep\b|\bsweep\b/i, "Liquidity sweep", "liquidity-sweep"],
    [/\border block\b|\bob\b/i, "Order block", "order-block"],
    [/\bfair value gap\b|\bfvg\b/i, "Fair value gap", "fair-value-gap"],
    [/\bimbalance\b/i, "Imbalance", "imbalance"],
    [/\bsupply\b|\bdemand\b/i, "Supply demand", "supply-demand"]
  ],
  setups: [
    [/\bopening range breakout\b|\borb\b/i, "Opening range breakout", "opening-range-breakout"],
    [/\bvwap pullback\b/i, "VWAP pullback", "vwap-pullback"],
    [/\bmean reversion\b/i, "Mean reversion", "mean-reversion"],
    [/\btrend following\b/i, "Trend following", "trend-following"],
    [/\brisk parity\b/i, "Risk parity", "risk-parity"],
    [/\bmomentum\b/i, "Momentum", "momentum"]
  ],
  risk: [
    [/\bstop loss\b|\bstop\b/i, "Stop loss", "stop-loss"],
    [/\binvalidation\b/i, "Invalidation", "invalidation"],
    [/\btake profit\b|\bprofit target\b|\btarget\b/i, "Profit target", "profit-target"],
    [/\brisk reward\b|\br:r\b|\brr\b/i, "Risk reward", "risk-reward"],
    [/\bposition siz(e|ing)\b|\bsize\b/i, "Position sizing", "position-sizing"]
  ],
  sessions: [
    [/\bpremarket\b|\bpre-market\b/i, "Premarket", "premarket"],
    [/\bopen\b|\bopening bell\b/i, "Open", "open"],
    [/\blondon\b/i, "London", "london-session"],
    [/\bnew york\b|\bny session\b/i, "New York", "new-york-session"]
  ]
};

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

function slug(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function technicalProfileForText(text: string) {
  const profile: Record<string, string[]> = {};
  Object.entries(technicalRules).forEach(([category, rules]) => {
    const labels = rules
      .filter(([pattern]) => pattern.test(text))
      .map(([, label]) => label);
    if (labels.length) profile[category] = Array.from(new Set(labels)).sort();
  });
  const timeframes =
    text.match(/\b(?:1|2|3|5|10|15|30|45|60)[ -]?(?:s|sec|m|min|minute|h|hr|hour)s?\b|\b(?:daily|weekly|monthly|intraday)\b/gi) ??
    [];
  if (timeframes.length) {
    profile.timeframes = Array.from(new Set(timeframes.map((value) => value.toUpperCase()))).sort();
  }
  return profile;
}

function technicalTagsForProfile(profile: Record<string, string[]>) {
  return uniqueTags(
    Object.entries(profile).flatMap(([category, values]) =>
      values.flatMap((value) => [slug(value), `${category.replace(/s$/, "")}:${slug(value)}`])
    )
  ).sort();
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2
  }).format(value);
}

function quotePrice(quote: MarketQuote | undefined) {
  if (!quote) return null;
  const price = Number(quote.last_price);
  return Number.isFinite(price) ? price : null;
}

function isTradeClosed(trade: TradeEntry) {
  return trade.exitPrice !== null && trade.exitPrice !== undefined;
}

function tradeMarkPrice(trade: TradeEntry) {
  return trade.exitPrice ?? trade.currentPrice ?? null;
}

function tradePnl(trade: TradeEntry) {
  const markPrice = tradeMarkPrice(trade);
  if (markPrice === null) return 0;
  const direction = trade.side === "long" ? 1 : -1;
  return (markPrice - trade.entryPrice) * trade.quantity * direction - trade.fees;
}

function targetPercentForTags(tags: string[]) {
  const text = tags.join(" ");
  if (text.includes("risk-parity")) return 0.006;
  if (text.includes("opening-range-breakout") || text.includes("breakout")) return 0.012;
  if (text.includes("mean-reversion") || text.includes("vwap-pullback")) return 0.008;
  return 0.01;
}

function targetExitPrice(entry: number, side: TradeEntry["side"], tags: string[]) {
  const pct = targetPercentForTags(tags);
  const raw = side === "short" ? entry * (1 - pct) : entry * (1 + pct);
  return Number(raw.toFixed(entry >= 100 ? 2 : 4));
}

function numberString(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return undefined;
  return String(value);
}

function draftNumber(value: string | undefined) {
  if (!value) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
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
  return "min-h-10 rounded-md border border-input bg-card px-3 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/20";
}

function textareaClass() {
  return "min-h-28 rounded-md border border-input bg-card px-3 py-2 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/20";
}

function tagChip(tag: string) {
  return (
    <Badge key={tag} variant="secondary">
      {tag}
    </Badge>
  );
}

function compactText(value: string, limit = 180) {
  if (value.length <= limit) return value;
  const clipped = value.slice(0, limit).replace(/\s+\S*$/, "");
  return `${clipped}...`;
}

function essentialTechnicalTags(tags: string[], limit = 8) {
  const directTags = uniqueTags(tags.filter((tag) => tag && !tag.includes(":")));
  const values = directTags.length ? directTags : uniqueTags(tags);
  return values.slice(0, limit);
}

function vaultItemFromImport(item: ImportedVaultItem): VaultItem {
  const aiTags = uniqueTags(item.ai_tags ?? []);
  const metadataTechnicalProfile =
    (item.metadata?.technical_profile as Record<string, string[]> | undefined) ?? {};
  const metadataTechnicalTags = (item.metadata?.technical_tags as string[] | undefined) ?? [];
  const sourceDetails =
    item.source_details ??
    (item.metadata?.source_details as SourceDetails | undefined) ??
    (item.metadata?.sourceDetails as SourceDetails | undefined) ??
    null;
  const technicalProfile = item.technical_profile ?? metadataTechnicalProfile;
  const technicalTags = uniqueTags([
    ...(item.technical_tags ?? []),
    ...metadataTechnicalTags,
    ...technicalTagsForProfile(technicalProfile)
  ]);
  const strategyInfo = item.strategy_info ?? null;
  const learningSummary = item.metadata?.learned_memory as VaultItem["learningSummary"] | undefined;

  return {
    id: newId(),
    title: item.title || "Untitled source",
    kind: item.kind || "note",
    source: item.source || "local upload",
    body: item.body || "Imported source",
    tags: uniqueTags([...(item.tags ?? []), ...aiTags, ...technicalTags]),
    aiTags,
    technicalTags,
    technicalProfile,
    sourceDetails,
    strategyInfo,
    learningSummary: learningSummary ?? null,
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
  const technicalProfile = technicalProfileForText(text);
  const technicalTags = technicalTagsForProfile(technicalProfile);
  const tags = [
    ...technicalTags,
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
  const technicalProfile = technicalProfileForText(text);
  const technicalTags = technicalTagsForProfile(technicalProfile);
  const sentences = sourceSentences(text);
  const setup = firstMatchingRule(text, setupRules);
  const indicators = [
    ...indicatorRules
      .filter(([needle]) => textContainsWord(lowered, needle))
      .map(([, label]) => label),
    ...(technicalProfile.indicators ?? [])
  ].sort();
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
    indicators: Array.from(new Set(indicators)),
    market,
    technical_tags: technicalTags,
    technical_profile: technicalProfile,
    confidence: Math.min(0.95, Number((0.25 + signalCount * 0.08).toFixed(2)))
  };
}

function enrichImportedItem(item: ImportedVaultItem): ImportedVaultItem {
  const aiTags = generatedTagsForImport(item);
  const strategyInfo = strategyInfoForImport(item, aiTags);
  const technicalProfile = technicalProfileForText(`${item.title} ${item.source} ${item.body.slice(0, 9000)}`);
  const technicalTags = technicalTagsForProfile(technicalProfile);

  return {
    ...item,
    tags: uniqueTags([...(item.tags ?? []), ...aiTags, ...technicalTags]).sort(),
    ai_tags: aiTags,
    technical_tags: technicalTags,
    technical_profile: technicalProfile,
    strategy_info: strategyInfo,
    metadata: {
      ...item.metadata,
      generated_tags: aiTags,
      technical_tags: technicalTags,
      technical_profile: technicalProfile,
      strategy_info: strategyInfo,
      enrichment_method: "client_semantic_rules"
    }
  };
}

function normalizeImportedItem(item: ImportedVaultItem): ImportedVaultItem {
  const localEnrichment = enrichImportedItem(item);
  const aiTags = uniqueTags([...(item.ai_tags ?? []), ...(localEnrichment.ai_tags ?? [])]).sort();
  const technicalProfile = {
    ...(localEnrichment.technical_profile ?? {}),
    ...(item.technical_profile ?? {})
  };
  const technicalTags = uniqueTags([
    ...(item.technical_tags ?? []),
    ...(localEnrichment.technical_tags ?? []),
    ...technicalTagsForProfile(technicalProfile)
  ]).sort();
  const strategyInfo = item.strategy_info ?? localEnrichment.strategy_info ?? null;

  return {
    ...item,
    tags: uniqueTags([...(item.tags ?? []), ...aiTags, ...technicalTags]).sort(),
    ai_tags: aiTags,
    technical_tags: technicalTags,
    technical_profile: technicalProfile,
    strategy_info: strategyInfo,
    metadata: {
      ...localEnrichment.metadata,
      ...item.metadata,
      generated_tags: aiTags,
      technical_tags: technicalTags,
      technical_profile: technicalProfile,
      strategy_info: strategyInfo
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
  // Seed with the empty state so the server render and the first client render
  // match. The persisted workspace is loaded from localStorage after mount (see
  // the effect below) to avoid an SSR/client hydration mismatch once data exists.
  const [state, setState] = useState<WorkspaceState>(emptyState);
  const [hydrated, setHydrated] = useState(false);
  const [apiOnline, setApiOnline] = useState(false);
  const [aiRouterStatus, setAiRouterStatus] = useState<AiRouterStatus | null>(null);
  const [tradeRecommendations, setTradeRecommendations] = useState<TradeRecommendation[]>([]);
  const [optimalStrategy, setOptimalStrategy] = useState<StrategyEvaluation | null>(null);
  const [quoteBySymbol, setQuoteBySymbol] = useState<Record<string, MarketQuote>>({});
  const [strategyIdea, setStrategyIdea] = useState("");
  const [strategyIdeaSymbol, setStrategyIdeaSymbol] = useState("");
  const [strategyEvaluation, setStrategyEvaluation] = useState<StrategyEvaluation | null>(null);
  const [strategyEvaluationMessage, setStrategyEvaluationMessage] = useState(
    "Describe a strategy in plain English to score it against your current memory."
  );
  const [pendingTradeDraft, setPendingTradeDraft] = useState<{
    draft: TradeDraft;
    title: string;
  } | null>(null);
  const [query, setQuery] = useState("");
  const [vaultUrl, setVaultUrl] = useState("");
  const [quickTradeText, setQuickTradeText] = useState("");
  const [quickTradeMessage, setQuickTradeMessage] = useState("Paste one line like: AAPL long 100 x10 strategy VWAP setup ORB.");
  const [importStatus, setImportStatus] = useState<{
    tone: "idle" | "loading" | "success" | "error";
    message: string;
  }>({ tone: "idle", message: "Waiting for a link or file." });
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState("memory");
  const tradeFormRef = useRef<HTMLFormElement>(null);
  const [graphView, setGraphView] = useState<GraphViewport>({
    centerX: graphCanvasWidth / 2,
    centerY: graphCanvasHeight / 2,
    zoom: 1
  });
  const [graphDrag, setGraphDrag] = useState<GraphDragState | null>(null);

  // On mount, prefer the API as the source of truth. When it is unreachable,
  // fall back to the browser-local workspace so the app stays fully usable
  // offline. Runs after mount, keeping the first render SSR-safe.
  useEffect(() => {
    let cancelled = false;

    function loadLocal() {
      try {
        const saved = window.localStorage.getItem(storageKey);
        if (saved && !cancelled) {
          const parsed = JSON.parse(saved) as WorkspaceState;
          setState({
            vault: parsed.vault ?? [],
            journal: parsed.journal ?? [],
            trades: parsed.trades ?? []
          });
        }
      } catch {
        // Ignore corrupt storage and start from the empty workspace.
      }
    }

    async function load() {
      const online = await api.checkHealth();
      if (cancelled) return;

      if (online) {
        try {
          const [trades, journal, vault, aiStatus, recommendations, optimal] = await Promise.all([
            api.listTrades(),
            api.listJournal(),
            api.listDocuments(),
            api.getAiRouterStatus().catch(() => null),
            api.listTradeRecommendations().catch(() => []),
            api.getOptimalStrategy().catch(() => null)
          ]);
          if (cancelled) return;
          setState({ vault, journal, trades });
          setAiRouterStatus(aiStatus);
          setTradeRecommendations(recommendations);
          setOptimalStrategy(optimal);
          setApiOnline(true);
          setHydrated(true);
          return;
        } catch {
          // API became unreachable mid-load; use the local cache instead.
        }
      }

      loadLocal();
      setAiRouterStatus(null);
      setTradeRecommendations([]);
      setOptimalStrategy(null);
      if (!cancelled) setHydrated(true);
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  // Persist only after the initial load so the empty seed never overwrites
  // previously saved data on first render.
  useEffect(() => {
    if (!hydrated) return;
    window.localStorage.setItem(storageKey, JSON.stringify(state));
  }, [state, hydrated]);

  useEffect(() => {
    if (!hydrated || !apiOnline) return;
    const symbols = uniqueTags(
      state.trades
        .filter((trade) => !isTradeClosed(trade))
        .map((trade) => trade.symbol)
    );
    if (!symbols.length) return;

    let cancelled = false;
    async function refreshQuotes() {
      const quotes = await Promise.all(
        symbols.map((symbol) => api.getQuote(symbol).catch(() => null))
      );
      if (cancelled) return;
      setQuoteBySymbol((current) => {
        const next = { ...current };
        quotes.forEach((quote) => {
          if (quote) next[quote.symbol] = quote;
        });
        return next;
      });
    }

    void refreshQuotes();
    const intervalId = window.setInterval(refreshQuotes, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [apiOnline, hydrated, state.trades]);

  const markedTrades = useMemo(
    () =>
      state.trades.map((trade) => {
        if (isTradeClosed(trade)) return trade;
        const quote = quoteBySymbol[trade.symbol];
        const currentPrice = quotePrice(quote);
        return {
          ...trade,
          currentPrice,
          quoteProvider: quote?.provider ?? trade.quoteProvider,
          quoteTime: quote?.market_time ?? trade.quoteTime,
          status: "open" as const
        };
      }),
    [quoteBySymbol, state.trades]
  );

  const viewState = useMemo(
    () => ({ ...state, trades: markedTrades }),
    [markedTrades, state]
  );

  const openPaperTrades = useMemo(
    () => viewState.trades.filter((trade) => !isTradeClosed(trade)),
    [viewState.trades]
  );

  const openPaperPnl = useMemo(
    () => openPaperTrades.reduce((sum, trade) => sum + tradePnl(trade), 0),
    [openPaperTrades]
  );

  const openPaperNotional = useMemo(
    () => openPaperTrades.reduce((sum, trade) => sum + trade.entryPrice * trade.quantity, 0),
    [openPaperTrades]
  );

  const metrics = useMemo(() => {
    const closedTrades = viewState.trades.filter(isTradeClosed);
    const netPnl = viewState.trades.reduce((sum, trade) => sum + tradePnl(trade), 0);
    const wins = closedTrades.filter((trade) => tradePnl(trade) > 0).length;
    const winRate = closedTrades.length ? Math.round((wins / closedTrades.length) * 100) : 0;
    const memoryCount = viewState.vault.length + viewState.journal.length + viewState.trades.length;

    return [
      {
        label: "Vault",
        value: String(viewState.vault.length),
        detail: "documents",
        icon: <BookMarked aria-hidden="true" size={20} strokeWidth={2.1} />
      },
      {
        label: "Trades",
        value: String(viewState.trades.length),
        detail: `${openPaperTrades.length} open / ${winRate}% win`,
        icon: <Activity aria-hidden="true" size={20} strokeWidth={2.1} />
      },
      {
        label: "P&L",
        value: formatCurrency(netPnl),
        detail: openPaperTrades.length ? "realized + open marks" : "closed trades",
        icon: <LineChart aria-hidden="true" size={20} strokeWidth={2.1} />
      },
      {
        label: "Memory",
        value: String(memoryCount),
        detail: "local records",
        icon: <BrainCircuit aria-hidden="true" size={20} strokeWidth={2.1} />
      }
    ];
  }, [openPaperTrades, viewState]);

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
        item.technicalTags?.join(" ") ?? "",
        JSON.stringify(item.technicalProfile ?? {}),
        JSON.stringify(item.sourceDetails ?? {}),
        JSON.stringify(item.strategyInfo ?? {}),
        JSON.stringify(item.learningSummary ?? {})
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle)
    );
  }, [query, state.vault]);

  const sourceStrategySignals = useMemo(
    () => buildSourceStrategySignals(viewState.vault, viewState.trades),
    [viewState.trades, viewState.vault]
  );
  const strategyStats = useMemo(
    () => buildStrategyStats(viewState, sourceStrategySignals),
    [sourceStrategySignals, viewState]
  );
  const strategySuggestions = useMemo(
    () => strategyStats.map((stat) => stat.name).filter(Boolean),
    [strategyStats]
  );
  const setupSuggestions = useMemo(
    () =>
      Array.from(
        new Set(
          [
            ...strategyStats.flatMap((stat) => stat.setups),
            ...sourceStrategySignals.map((signal) => signal.setup ?? "")
          ].filter(Boolean)
        )
      ),
    [sourceStrategySignals, strategyStats]
  );
  const quickTradePreview = useMemo(
    () => parseQuickTrade(quickTradeText),
    [quickTradeText]
  );
  const tradingInsights = useMemo(
    () =>
      buildTradingInsights(
        viewState,
        strategyStats,
        sourceStrategySignals,
        aiRouterStatus,
        tradeRecommendations
      ),
    [aiRouterStatus, sourceStrategySignals, strategyStats, tradeRecommendations, viewState]
  );
  const recommendedRoutine = useMemo(
    () =>
      buildRecommendedRoutine(
        viewState,
        strategyStats,
        sourceStrategySignals,
        optimalStrategy,
        tradeRecommendations
      ),
    [optimalStrategy, sourceStrategySignals, strategyStats, tradeRecommendations, viewState]
  );
  const routineSignals = useMemo(() => {
    const related = sourceStrategySignals.filter(
      (signal) =>
        labelsOverlap(signal.strategyName, recommendedRoutine.strategyName) ||
        labelsOverlap(signal.setup ?? "", recommendedRoutine.setupFocus)
    );
    return (related.length ? related : sourceStrategySignals).slice(0, 5);
  }, [recommendedRoutine, sourceStrategySignals]);
  const routineStrategyStat = useMemo(
    () =>
      strategyStats.find((stat) => labelsOverlap(stat.name, recommendedRoutine.strategyName)) ??
      strategyStats[0],
    [recommendedRoutine.strategyName, strategyStats]
  );
  const graph = useMemo(
    () => buildGraphModel(viewState, sourceStrategySignals, strategyStats),
    [sourceStrategySignals, strategyStats, viewState]
  );
  const graphNodeLookup = useMemo(
    () => new Map(graph.nodes.map((node) => [node.id, node])),
    [graph.nodes]
  );
  const selectedGraphNode = graphNodeLookup.get(selectedGraphNodeId) ?? graph.nodes[0];
  const selectedGraphEdges = useMemo(
    () =>
      selectedGraphNode
        ? graph.edges.filter((edge) => edge.from === selectedGraphNode.id || edge.to === selectedGraphNode.id)
        : [],
    [graph.edges, selectedGraphNode]
  );
  const focusedGraphNodeIds = useMemo(() => {
    const ids = new Set<string>();
    if (selectedGraphNode) ids.add(selectedGraphNode.id);
    selectedGraphEdges.forEach((edge) => {
      ids.add(edge.from);
      ids.add(edge.to);
    });
    return ids;
  }, [selectedGraphEdges, selectedGraphNode]);
  const graphFocusMode = Boolean(selectedGraphNode && selectedGraphNode.type !== "memory");
  const graphViewBox = useMemo(() => {
    const width = graphCanvasWidth / graphView.zoom;
    const height = graphCanvasHeight / graphView.zoom;
    return `${graphView.centerX - width / 2} ${graphView.centerY - height / 2} ${width} ${height}`;
  }, [graphView]);

  function selectGraphNode(nodeId: string, focus = false) {
    const node = graphNodeLookup.get(nodeId);
    setSelectedGraphNodeId(nodeId);
    if (focus && node) focusGraphNode(node);
  }

  function focusGraphNode(node: PositionedGraphNode) {
    setGraphView({ centerX: node.x, centerY: node.y, zoom: Math.max(1.35, graphView.zoom) });
  }

  function zoomGraph(delta: number) {
    setGraphView((current) => ({
      ...current,
      zoom: Math.min(2.4, Math.max(0.7, Number((current.zoom + delta).toFixed(2))))
    }));
  }

  function resetGraphView() {
    setGraphView({ centerX: graphCanvasWidth / 2, centerY: graphCanvasHeight / 2, zoom: 1 });
  }

  function panGraph(event: React.PointerEvent<SVGSVGElement>) {
    if (!graphDrag) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const unitX = graphCanvasWidth / rect.width / graphDrag.startView.zoom;
    const unitY = graphCanvasHeight / rect.height / graphDrag.startView.zoom;
    setGraphView({
      ...graphDrag.startView,
      centerX: graphDrag.startView.centerX - (event.clientX - graphDrag.startX) * unitX,
      centerY: graphDrag.startView.centerY - (event.clientY - graphDrag.startY) * unitY
    });
  }

  async function refreshTradeRecommendations() {
    if (!apiOnline) return;
    try {
      setTradeRecommendations(await api.listTradeRecommendations());
      setOptimalStrategy(await api.getOptimalStrategy().catch(() => null));
    } catch {
      setApiOnline(false);
    }
  }

  async function enrichDraftWithQuote(draft: TradeDraft, tags: string[]) {
    const symbol = draft.symbol?.trim().toUpperCase();
    if (!symbol) return draft;
    const side = draft.side ?? "long";
    const fallbackEntry = draftNumber(draft.entry_price);
    const fallbackExit = draftNumber(draft.exit_price);
    try {
      const quote = await api.getQuote(symbol);
      setQuoteBySymbol((current) => ({ ...current, [quote.symbol]: quote }));
      const entry = quotePrice(quote) ?? fallbackEntry;
      return {
        ...draft,
        symbol: quote.symbol,
        entry_price: numberString(entry),
        exit_price: numberString(
          fallbackExit ?? (entry ? targetExitPrice(entry, side, tags) : undefined)
        ),
        price_source: quote.provider,
        price_time: quote.market_time ?? undefined
      };
    } catch {
      return {
        ...draft,
        entry_price: numberString(fallbackEntry),
        exit_price: numberString(fallbackExit)
      };
    }
  }

  function fillTradeForm(draft: TradeDraft, title: string) {
    const form = tradeFormRef.current;
    if (!draft || !form) return;

    const setField = (name: string, value: string | undefined) => {
      if (value === undefined) return;
      const field = form.elements.namedItem(name);
      if (field instanceof HTMLInputElement || field instanceof HTMLSelectElement || field instanceof HTMLTextAreaElement) {
        field.value = value;
      }
    };

    setQuickTradeText("");
    setField("symbol", draft.symbol);
    setField("side", draft.side);
    setField("entryDate", new Date().toISOString().slice(0, 10));
    setField("entryPrice", draft.entry_price);
    setField("exitPrice", draft.exit_price);
    setField("strategy", draft.strategy);
    setField("setup", draft.setup);
    setField("emotion", draft.emotion);
    setField("quantity", draft.quantity);
    setField("fees", draft.fees);
    setField("notes", draft.notes);
    const priceMessage =
      draft.entry_price && draft.exit_price
        ? `Entry ${draft.entry_price}, target exit ${draft.exit_price}.`
        : "Quote unavailable; add entry and exit prices before logging.";
    setQuickTradeMessage(`Filled trade draft from ${title}. ${priceMessage}`);
  }

  async function applyTradeDraft(recommendation: TradeRecommendation) {
    if (!recommendation.draft) return;
    const draft = await enrichDraftWithQuote(recommendation.draft, recommendation.technical_tags);
    if (activeTab !== "trades") {
      setPendingTradeDraft({ draft, title: recommendation.title });
      setActiveTab("trades");
      return;
    }
    fillTradeForm(draft, recommendation.title);
  }

  async function applyEvaluationDraft(evaluation: StrategyEvaluation) {
    const draft = await enrichDraftWithQuote(evaluation.draft, evaluation.technical_tags);
    if (activeTab !== "trades") {
      setPendingTradeDraft({ draft, title: evaluation.title });
      setActiveTab("trades");
      return;
    }
    fillTradeForm(draft, evaluation.title);
  }

  useEffect(() => {
    if (activeTab !== "trades" || !pendingTradeDraft || !tradeFormRef.current) return;
    fillTradeForm(pendingTradeDraft.draft, pendingTradeDraft.title);
    setPendingTradeDraft(null);
  }, [activeTab, pendingTradeDraft]);

  async function saveImportedVaultItem(item: ImportedVaultItem) {
    const vaultItem = vaultItemFromImport(normalizeImportedItem(item));
    let stored = vaultItem;
    if (apiOnline) {
      try {
        stored = await api.createDocument(vaultItem);
      } catch {
        setApiOnline(false);
      }
    }
    setState((current) => ({ ...current, vault: [stored, ...current.vault] }));
    void refreshTradeRecommendations();
    setImportStatus({
      tone: "success",
      message: `Imported "${stored.title}" with ${stored.tags.length} tags${
        stored.strategyInfo ? " and strategy fields" : ""
      }${
        stored.learningSummary
          ? `; learned ${stored.learningSummary.chunk_count} chunks / ${stored.learningSummary.node_count} map nodes`
          : ""
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
      await saveImportedVaultItem((await response.json()) as ImportedVaultItem);
    } catch {
      await saveImportedVaultItem(fallbackLinkImport(url));
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
      await saveImportedVaultItem((await response.json()) as ImportedVaultItem);
    } catch {
      await saveImportedVaultItem(await fallbackFileImport(file));
      setImportStatus({
        tone: "success",
        message: "Imported the file locally. Rich parsing will improve when parser workers are added."
      });
    }
    event.target.value = "";
  }

  async function evaluatePlainEnglishStrategy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const idea = strategyIdea.trim();
    if (!idea) return;
    setStrategyEvaluationMessage("Evaluating idea against learned sources, trades, and journal memory...");
    try {
      const evaluation = await api.evaluateStrategyIdea(idea, strategyIdeaSymbol.trim());
      setStrategyEvaluation(evaluation);
      setStrategyEvaluationMessage(
        `Decision: ${evaluation.decision}. Journaled evaluation ${evaluation.journal_entry_id ? "saved" : "not saved"}.`
      );
      if (apiOnline) {
        const journal = await api.listJournal().catch(() => null);
        if (journal) setState((current) => ({ ...current, journal }));
      }
    } catch {
      const localEvaluation = buildLocalStrategyEvaluation(
        idea,
        strategyIdeaSymbol.trim(),
        viewState,
        sourceStrategySignals
      );
      setStrategyEvaluation(localEvaluation);
      setStrategyEvaluationMessage("API unavailable; evaluated locally without journal sync.");
    }
  }

  async function fillTradePricesFromQuote() {
    const form = tradeFormRef.current;
    if (!form) return;
    const symbol = String(new FormData(form).get("symbol") ?? "").trim().toUpperCase();
    if (!symbol) {
      setQuickTradeMessage("Enter a symbol before asking for a live quote.");
      return;
    }
    try {
      const quote = await api.getQuote(symbol);
      setQuoteBySymbol((current) => ({ ...current, [quote.symbol]: quote }));
      const side = String(new FormData(form).get("side") ?? "long") as TradeEntry["side"];
      const tags = uniqueTags([
        String(new FormData(form).get("setup") ?? ""),
        String(new FormData(form).get("strategy") ?? "")
      ]);
      const entry = quotePrice(quote);
      const exit = entry ? targetExitPrice(entry, side, tags) : null;
      if (entry) {
        const entryField = form.elements.namedItem("entryPrice");
        const exitField = form.elements.namedItem("exitPrice");
        if (entryField instanceof HTMLInputElement) entryField.value = String(entry);
        if (exitField instanceof HTMLInputElement && exit) exitField.value = String(exit);
      }
      setQuickTradeMessage(`Fetched ${quote.symbol} at ${formatCurrency(Number(quote.last_price))}.`);
    } catch {
      setQuickTradeMessage("Live quote is unavailable for that symbol right now.");
    }
  }

  // Persist a newly created record: to the API when online (using the returned
  // server row, which carries the real id), otherwise to local state only.
  async function persistCreate<T extends { id: string }>(
    collection: keyof WorkspaceState,
    local: T,
    create: (item: T) => Promise<T>
  ) {
    let stored = local;
    if (apiOnline) {
      try {
        stored = await create(local);
      } catch {
        setApiOnline(false);
      }
    }
    setState(
      (current) =>
        ({
          ...current,
          [collection]: [stored, ...(current[collection] as unknown as T[])]
        }) as WorkspaceState
    );
    void refreshTradeRecommendations();
  }

  async function addJournalEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formEl = event.currentTarget;
    const form = new FormData(formEl);
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

    formEl.reset();
    await persistCreate("journal", entry, api.createJournal);
  }

  async function placeLivePaperTrade() {
    const formEl = tradeFormRef.current;
    if (!formEl) return;

    const form = new FormData(formEl);
    const symbol = String(form.get("symbol") ?? "").trim().toUpperCase();
    const quantity = Number(form.get("quantity"));
    if (!symbol || !quantity) {
      setQuickTradeMessage("Enter a symbol and quantity before placing a live paper trade.");
      return;
    }

    setQuickTradeMessage(`Fetching a live paper fill for ${symbol}...`);
    try {
      const quote = await api.getQuote(symbol);
      const entryPrice = quotePrice(quote);
      if (entryPrice === null) throw new Error("missing quote");

      const side = String(form.get("side") ?? "long") as TradeEntry["side"];
      const quoteTime = quote.market_time ?? new Date().toISOString();
      const rawNotes = String(form.get("notes") ?? "").trim();
      const executionNote = `Paper market order opened at ${formatCurrency(entryPrice)} from ${quote.provider}${
        quote.market_time ? ` (${quote.market_time})` : ""
      }.`;
      const trade: TradeEntry = {
        id: newId(),
        symbol: quote.symbol,
        side,
        entryDate: String(form.get("entryDate") || quoteTime.slice(0, 10)),
        entryPrice,
        exitPrice: null,
        currentPrice: entryPrice,
        quoteProvider: quote.provider,
        quoteTime: quote.market_time,
        status: "open",
        orderType: "paper_market",
        paperOrder: true,
        quantity,
        fees: Number(form.get("fees")) || 0,
        strategy: String(form.get("strategy") ?? "").trim(),
        setup: String(form.get("setup") ?? "").trim(),
        emotion: String(form.get("emotion") ?? "focused"),
        notes: [rawNotes, executionNote].filter(Boolean).join("\n"),
        createdAt: new Date().toISOString()
      };

      setQuoteBySymbol((current) => ({ ...current, [quote.symbol]: quote }));
      formEl.reset();
      setQuickTradeText("");
      setQuickTradeMessage(
        `Placed paper ${trade.side} ${trade.symbol} x${trade.quantity} at ${formatCurrency(entryPrice)}.`
      );
      await persistCreate("trades", trade, api.createTrade);
    } catch {
      setQuickTradeMessage(`Could not place ${symbol}; live quote is unavailable right now.`);
    }
  }

  async function addTrade(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formEl = event.currentTarget;
    const form = new FormData(formEl);
    const quickTrade = String(form.get("quickTrade") ?? "").trim();
    if (quickTrade) {
      const draft = parseQuickTrade(quickTrade);
      if (!draft) {
        setQuickTradeMessage("Could not read that trade. Include symbol, side, entry, and quantity.");
        return;
      }

      const trade: TradeEntry = {
        id: newId(),
        ...draft,
        createdAt: new Date().toISOString()
      };

      formEl.reset();
      setQuickTradeText("");
      setQuickTradeMessage(
        isTradeClosed(trade)
          ? `Logged ${trade.symbol} ${trade.side} for ${formatCurrency(tradePnl(trade))}.`
          : `Opened ${trade.symbol} ${trade.side}; live marks will update while it is in progress.`
      );
      await persistCreate("trades", trade, api.createTrade);
      return;
    }

    const symbol = String(form.get("symbol") ?? "").trim().toUpperCase();
    const entryPrice = Number(form.get("entryPrice"));
    const exitRaw = String(form.get("exitPrice") ?? "").trim();
    const exitPrice = exitRaw ? Number(exitRaw) : null;
    const quantity = Number(form.get("quantity"));
    if (!symbol || !entryPrice || !quantity) {
      setQuickTradeMessage("Use the quick line or fill symbol, entry, and quantity.");
      return;
    }

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

    formEl.reset();
    setQuickTradeText("");
    setQuickTradeMessage(
      isTradeClosed(trade)
        ? `Logged ${trade.symbol} ${trade.side} for ${formatCurrency(tradePnl(trade))}.`
        : `Opened ${trade.symbol} ${trade.side}; live marks will update while it is in progress.`
    );
    await persistCreate("trades", trade, api.createTrade);
  }

  async function closeTradeAtLive(trade: TradeEntry) {
    try {
      const quote = await api.getQuote(trade.symbol);
      const exitPrice = quotePrice(quote);
      if (!exitPrice) throw new Error("missing quote");
      const updated = await api.updateTrade(trade.id, {
        ...trade,
        exitPrice,
        currentPrice: exitPrice,
        quoteProvider: quote.provider,
        quoteTime: quote.market_time
      });
      setQuoteBySymbol((current) => ({ ...current, [quote.symbol]: quote }));
      setState((current) => ({
        ...current,
        trades: current.trades.map((item) => (item.id === trade.id ? updated : item))
      }));
      setQuickTradeMessage(`Closed ${trade.symbol} at ${formatCurrency(exitPrice)}.`);
      void refreshTradeRecommendations();
    } catch {
      setQuickTradeMessage(`Could not fetch a live exit for ${trade.symbol}.`);
    }
  }

  async function removeItem(collection: keyof WorkspaceState, id: string) {
    if (apiOnline) {
      try {
        if (collection === "trades") await api.deleteTrade(id);
        else if (collection === "journal") await api.deleteJournal(id);
        else await api.deleteDocument(id);
      } catch {
        setApiOnline(false);
      }
    }
    setState((current) => ({
      ...current,
      [collection]: current[collection].filter((item) => item.id !== id)
    }));
    if (collection === "trades" || collection === "vault") {
      void refreshTradeRecommendations();
    }
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
      <Tabs className="border-b bg-card/78 px-4 py-3 backdrop-blur">
        <TabsList className="max-w-full overflow-x-auto">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.key;

            return (
              <TabsTrigger
                active={active}
                aria-controls={`${tab.key}-panel`}
                id={`${tab.key}-tab`}
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                title={tab.label}
              >
                <Icon aria-hidden="true" size={17} strokeWidth={2.2} />
                {tab.label}
              </TabsTrigger>
            );
          })}
        </TabsList>
      </Tabs>

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
            <section
              aria-labelledby="vault-tab"
              className="grid gap-4 xl:grid-cols-[360px_1fr]"
              id="vault-panel"
              role="tabpanel"
            >
              <section className="rounded-lg border border-line bg-card/86 p-4 shadow-panel">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold text-ink">Auto Capture</h2>
                  <Upload aria-hidden="true" className="text-signal" size={20} strokeWidth={2.1} />
                </div>
                <form className="mt-4 grid gap-3" onSubmit={importVaultUrl}>
                  <label className="grid gap-1.5 text-sm font-medium text-ink/72">
                    Link
                    <div className="flex gap-2">
                      <Input
                        className={`${textInputClass()} min-w-0 flex-1`}
                        onChange={(event) => setVaultUrl(event.target.value)}
                        placeholder="https://..."
                        type="url"
                        value={vaultUrl}
                      />
                      <Button
                        disabled={importStatus.tone === "loading"}
                        type="submit"
                      >
                        <Link2 aria-hidden="true" size={17} strokeWidth={2.3} />
                        Import
                      </Button>
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

                <div className="mt-4 rounded-md border border-line bg-card p-3">
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

              <section className="rounded-lg border border-line bg-card/86 shadow-panel">
                <div className="flex flex-col gap-3 border-b border-line px-4 py-3 md:flex-row md:items-center md:justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-ink">Learning Vault</h2>
                    <p className="mt-1 text-sm text-ink/58">{filteredVault.length} records</p>
                  </div>
                  <label className="flex min-h-10 items-center gap-2 rounded-md border border-line bg-card px-3 text-sm text-ink/62">
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
                    const technicalTags = item.technicalTags ?? [];
                    const technicalProfile = item.technicalProfile ?? item.strategyInfo?.technical_profile ?? {};
                    const strategyInfo = item.strategyInfo;
                    const sourceDetails = item.sourceDetails;
                    const learningSummary = item.learningSummary;

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
                            {sourceDetails && <SourceDetailsSummary details={sourceDetails} />}
                            {aiTags.length > 0 && (
                              <div className="mt-4 border-l-2 border-caution/35 pl-3">
                                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink/48">
                                  Generated Tags
                                </p>
                                <div className="mt-2 flex flex-wrap gap-2">{aiTags.map(tagChip)}</div>
                              </div>
                            )}
                            {technicalTags.length > 0 && (
                              <div className="mt-4 border-l-2 border-signal/35 pl-3">
                                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink/48">
                                  Technicals
                                </p>
                                <div className="mt-2 flex flex-wrap gap-2">
                                  {essentialTechnicalTags(technicalTags).map(tagChip)}
                                </div>
                                <div className="mt-3 grid gap-2 text-sm md:grid-cols-2">
                                  {Object.entries(technicalProfile).slice(0, 4).map(([category, values]) => (
                                    <SnapshotRow
                                      key={category}
                                      label={category.replaceAll("_", " ")}
                                      value={values.slice(0, 2).join(", ")}
                                    />
                                  ))}
                                </div>
                              </div>
                            )}
                            {strategyInfo && (
                              <StrategyInfoSummary strategyInfo={strategyInfo} />
                            )}
                            {learningSummary && (
                              <div className="mt-4 border-l-2 border-moss/35 pl-3">
                                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink/48">
                                  Personal AI Memory
                                </p>
                                <div className="mt-2 grid gap-2 text-sm md:grid-cols-3">
                                  <SnapshotRow label="Chunks" value={String(learningSummary.chunk_count)} />
                                  <SnapshotRow label="Nodes" value={String(learningSummary.node_count)} />
                                  <SnapshotRow label="Edges" value={String(learningSummary.edge_count)} />
                                </div>
                                {learningSummary.technical_count !== undefined && (
                                  <p className="mt-2 text-sm leading-6 text-ink/64">
                                    {learningSummary.technical_count} technical relationships learned.
                                  </p>
                                )}
                                {learningSummary.strategy && (
                                  <p className="mt-2 text-sm leading-6 text-ink/64">
                                    Learned into {learningSummary.strategy}.
                                  </p>
                                )}
                                <div className="mt-2 flex flex-wrap gap-2">
                                  {learningSummary.map_labels.slice(0, 8).map(tagChip)}
                                </div>
                              </div>
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
            <section
              aria-labelledby="journal-tab"
              className="grid gap-4 xl:grid-cols-[360px_1fr]"
              id="journal-panel"
              role="tabpanel"
            >
              <form
                className="rounded-lg border border-line bg-card/86 p-4 shadow-panel"
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
                  <Button type="submit">
                    <Plus aria-hidden="true" size={17} strokeWidth={2.3} />
                    Save entry
                  </Button>
                </div>
              </form>

              <section className="rounded-lg border border-line bg-card/86 shadow-panel">
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
            <section
              aria-labelledby="trades-tab"
              className="grid gap-4 xl:grid-cols-[360px_1fr]"
              id="trades-panel"
              role="tabpanel"
            >
              <form
                className="rounded-lg border border-line bg-card/86 p-4 shadow-panel"
                onSubmit={addTrade}
                ref={tradeFormRef}
              >
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold text-ink">Paper Trade Ticket</h2>
                  <Activity aria-hidden="true" className="text-signal" size={20} strokeWidth={2.1} />
                </div>
                <div className="mt-4 grid gap-3">
                  <div className="rounded-lg border border-signal/20 bg-signal/5 p-3">
                    <Field label="Quick trade">
                      <textarea
                        className={`${textareaClass()} min-h-24`}
                        name="quickTrade"
                        onChange={(event) => setQuickTradeText(event.target.value)}
                        placeholder="AAPL long 100 x10 strategy VWAP setup ORB notes clean reclaim"
                        value={quickTradeText}
                      />
                    </Field>
                    <div className="mt-3 rounded-md border border-line bg-card/75 px-3 py-2 text-sm text-ink/64">
                      {quickTradePreview ? (
                        <span>
                          {quickTradePreview.symbol} / {quickTradePreview.side} /{" "}
                          {formatCurrency(tradePnl({ id: "preview", createdAt: "", ...quickTradePreview }))} /{" "}
                          {quickTradePreview.strategy || "no strategy"}
                        </span>
                      ) : (
                        <span>{quickTradeMessage}</span>
                      )}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Symbol">
                      <input className={textInputClass()} name="symbol" />
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
                      <input className={textInputClass()} name="entryPrice" step="0.01" type="number" />
                    </Field>
                    <Field label="Exit">
                      <input className={textInputClass()} name="exitPrice" step="0.01" type="number" />
                    </Field>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <Button onClick={fillTradePricesFromQuote} type="button" variant="outline">
                      <LineChart aria-hidden="true" size={17} strokeWidth={2.2} />
                      Use live quote
                    </Button>
                    <Button onClick={placeLivePaperTrade} type="button">
                      <Activity aria-hidden="true" size={17} strokeWidth={2.3} />
                      Place live paper trade
                    </Button>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Qty">
                      <input className={textInputClass()} name="quantity" step="0.01" type="number" />
                    </Field>
                    <Field label="Fees">
                      <input className={textInputClass()} name="fees" step="0.01" type="number" />
                    </Field>
                  </div>
                  <Field label="Strategy">
                    <input className={textInputClass()} list="strategy-suggestions" name="strategy" placeholder="VWAP Pullback" />
                    <datalist id="strategy-suggestions">
                      {strategySuggestions.map((strategy) => (
                        <option key={strategy} value={strategy} />
                      ))}
                    </datalist>
                  </Field>
                  <Field label="Setup">
                    <input className={textInputClass()} list="setup-suggestions" name="setup" placeholder="Reclaim, ORB, fade" />
                    <datalist id="setup-suggestions">
                      {setupSuggestions.map((setup) => (
                        <option key={setup} value={setup} />
                      ))}
                    </datalist>
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
                  <Button type="submit">
                    <Plus aria-hidden="true" size={17} strokeWidth={2.3} />
                    Log manual trade
                  </Button>
                </div>
              </form>

              <div className="grid gap-4">
                <section className="rounded-lg border border-line bg-card/86 p-4 shadow-panel">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <h2 className="text-base font-semibold text-ink">Open Paper Positions</h2>
                      <p className="mt-1 text-sm text-ink/58">
                        Live marks refresh every 30 seconds while the API is online
                      </p>
                    </div>
                    <Activity aria-hidden="true" className="text-signal" size={20} strokeWidth={2.1} />
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    <div className="border-l-2 border-signal pl-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-ink/45">Open</p>
                      <p className="mt-1 text-lg font-semibold text-ink">{openPaperTrades.length}</p>
                    </div>
                    <div className="border-l-2 border-line pl-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-ink/45">Notional</p>
                      <p className="mt-1 text-lg font-semibold text-ink">{formatCurrency(openPaperNotional)}</p>
                    </div>
                    <div className="border-l-2 border-line pl-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-ink/45">Unrealized</p>
                      <p className={["mt-1 text-lg font-semibold", openPaperPnl >= 0 ? "text-moss" : "text-loss"].join(" ")}>
                        {formatCurrency(openPaperPnl)}
                      </p>
                    </div>
                  </div>
                  {openPaperTrades.length ? (
                    <div className="mt-4 divide-y divide-line border-y border-line">
                      {openPaperTrades.slice(0, 6).map((trade) => {
                        const mark = tradeMarkPrice(trade);
                        const pnl = tradePnl(trade);
                        return (
                          <div
                            className="grid gap-3 py-3 text-sm sm:grid-cols-[1fr_auto_auto]"
                            key={`open-${trade.id}`}
                          >
                            <div>
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="font-semibold text-ink">{trade.symbol}</span>
                                <Badge variant="warning">{trade.side}</Badge>
                                {trade.paperOrder && <Badge variant="outline">paper</Badge>}
                              </div>
                              <p className="mt-1 text-ink/58">
                                {trade.strategy || "Untitled strategy"} / {trade.setup || "no setup"}
                              </p>
                            </div>
                            <div className="text-ink/68 sm:text-right">
                              <p>
                                Entry {formatCurrency(trade.entryPrice)} / Mark{" "}
                                {mark ? formatCurrency(mark) : "waiting quote"}
                              </p>
                              <p className={pnl >= 0 ? "font-semibold text-moss" : "font-semibold text-loss"}>
                                {formatCurrency(pnl)}
                              </p>
                            </div>
                            <div className="flex items-center sm:justify-end">
                              <Button
                                onClick={() => void closeTradeAtLive(trade)}
                                size="sm"
                                type="button"
                                variant="outline"
                              >
                                Close live
                              </Button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="mt-4 border-y border-line py-4 text-sm font-medium text-ink/52">
                      No open paper positions.
                    </div>
                  )}
                </section>

                <section className="rounded-lg border border-line bg-card/86 p-4 shadow-panel">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <h2 className="text-base font-semibold text-ink">Strategy Idea Evaluator</h2>
                      <p className="mt-1 text-sm text-ink/58">
                        Score a plain-English idea against learned sources, trades, and journal memory
                      </p>
                    </div>
                    <BrainCircuit aria-hidden="true" className="text-signal" size={20} strokeWidth={2.1} />
                  </div>
                  <form className="mt-4 grid gap-3" onSubmit={evaluatePlainEnglishStrategy}>
                    <Field label="Strategy idea">
                      <textarea
                        className={textareaClass()}
                        onChange={(event) => setStrategyIdea(event.target.value)}
                        placeholder="Example: trade ES long when futures risk-parity momentum aligns and price reclaims VWAP, with a tight invalidation."
                        value={strategyIdea}
                      />
                    </Field>
                    <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                      <Field label="Symbol">
                        <input
                          className={textInputClass()}
                          onChange={(event) => setStrategyIdeaSymbol(event.target.value)}
                          placeholder="optional, e.g. ES"
                          value={strategyIdeaSymbol}
                        />
                      </Field>
                      <div className="flex items-end">
                        <Button type="submit">
                          <Wand2 aria-hidden="true" size={17} strokeWidth={2.2} />
                          Evaluate
                        </Button>
                      </div>
                    </div>
                  </form>
                  <p className="mt-3 text-sm text-ink/58">{strategyEvaluationMessage}</p>
                  {strategyEvaluation && (
                    <StrategyEvaluationCard
                      evaluation={strategyEvaluation}
                      onApply={applyEvaluationDraft}
                      title="Idea evaluation"
                    />
                  )}
                </section>

                <section className="rounded-lg border border-line bg-card/86 p-4 shadow-panel">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <h2 className="text-base font-semibold text-ink">AI Trade Recommendations</h2>
                      <p className="mt-1 text-sm text-ink/58">
                        Based on uploaded strategies, technical tags, learned memory, and trade history
                      </p>
                    </div>
                    <Wand2 aria-hidden="true" className="text-caution" size={20} strokeWidth={2.1} />
                  </div>
                  <div className="mt-4 grid gap-3">
                    {tradeRecommendations.map((recommendation) => (
                      <TradeRecommendationCard
                        key={recommendation.id}
                        onApply={applyTradeDraft}
                        recommendation={recommendation}
                      />
                    ))}
                    {!tradeRecommendations.length && (
                      <div className="rounded-md border border-line bg-paper/60 px-3 py-3 text-sm font-medium text-ink/52">
                        Add a strategy source to generate recommendations.
                      </div>
                    )}
                  </div>
                </section>

                <section className="overflow-hidden rounded-lg border border-line bg-card/86 shadow-panel">
                <div className="border-b border-line px-4 py-3">
                  <h2 className="text-base font-semibold text-ink">Trades</h2>
                  <p className="mt-1 text-sm text-ink/58">
                    {viewState.trades.filter((trade) => !isTradeClosed(trade)).length} open /{" "}
                    {viewState.trades.filter(isTradeClosed).length} closed
                  </p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[900px] border-collapse text-left text-sm">
                    <thead className="bg-paper text-xs uppercase text-ink/54">
                      <tr>
                        <th className="px-4 py-3">Date</th>
                        <th className="px-4 py-3">Symbol</th>
                        <th className="px-4 py-3">Side</th>
                        <th className="px-4 py-3">Strategy</th>
                        <th className="px-4 py-3">Entry</th>
                        <th className="px-4 py-3">Mark</th>
                        <th className="px-4 py-3">Qty</th>
                        <th className="px-4 py-3">P&L</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {viewState.trades.map((trade) => {
                        const pnl = tradePnl(trade);
                        const closed = isTradeClosed(trade);
                        const mark = tradeMarkPrice(trade);

                        return (
                          <tr key={trade.id}>
                            <td className="px-4 py-3 text-ink/62">{trade.entryDate}</td>
                            <td className="px-4 py-3 font-semibold text-ink">{trade.symbol}</td>
                            <td className="px-4 py-3 capitalize text-ink/68">{trade.side}</td>
                            <td className="px-4 py-3 text-ink/68">{trade.strategy || "Untitled"}</td>
                            <td className="px-4 py-3 text-ink/68">{formatCurrency(trade.entryPrice)}</td>
                            <td className="px-4 py-3 text-ink/68">
                              {mark ? formatCurrency(mark) : "waiting quote"}
                            </td>
                            <td className="px-4 py-3 text-ink/68">{trade.quantity}</td>
                            <td
                              className={[
                                "px-4 py-3 font-semibold",
                                pnl >= 0 ? "text-moss" : "text-loss"
                              ].join(" ")}
                            >
                              {formatCurrency(pnl)}
                            </td>
                            <td className="px-4 py-3 text-ink/68">
                              <Badge variant={closed ? "secondary" : "warning"}>
                                {closed ? "closed" : trade.paperOrder ? "paper open" : "open"}
                              </Badge>
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex justify-end gap-1">
                              {!closed && (
                                <button
                                  className="rounded-md px-2 py-1 text-xs font-semibold text-signal transition hover:bg-paper"
                                  onClick={() => void closeTradeAtLive(trade)}
                                  type="button"
                                >
                                  Close live
                                </button>
                              )}
                              <button
                                className="rounded-md p-2 text-ink/45 transition hover:bg-paper hover:text-loss"
                                onClick={() => removeItem("trades", trade.id)}
                                title="Delete"
                                type="button"
                              >
                                <Trash2 aria-hidden="true" size={17} />
                              </button>
                              </div>
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
              </div>
            </section>
          )}

          {activeTab === "routine" && (
            <section
              aria-labelledby="routine-tab"
              className="grid gap-4 xl:grid-cols-[1fr_360px]"
              id="routine-panel"
              role="tabpanel"
            >
              <RoutinePlaybookCard routine={recommendedRoutine} variant="full" />

              <div className="grid gap-4">
                <section className="rounded-lg border border-line bg-card/86 p-4 shadow-panel">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <h2 className="text-base font-semibold text-ink">Source Evidence</h2>
                      <p className="mt-1 text-sm text-ink/58">
                        Extracted rules supporting the current routine
                      </p>
                    </div>
                    <BookMarked aria-hidden="true" className="text-signal" size={20} strokeWidth={2.1} />
                  </div>
                  <div className="mt-4 divide-y divide-line border-y border-line">
                    {routineSignals.map((signal) => (
                      <article className="py-3" key={`${signal.sourceId}-${signal.strategyName}`}>
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <h3 className="text-sm font-semibold text-ink">{signal.sourceTitle}</h3>
                            <p className="mt-1 text-xs font-medium text-ink/52">
                              {signal.strategyName} / {signal.setup ?? "setup pending"}
                            </p>
                          </div>
                          <span className="text-xs font-semibold text-ink/48">
                            {Math.round(signal.confidence * 100)}%
                          </span>
                        </div>
                        {signal.summary && (
                          <p className="mt-2 text-sm leading-6 text-ink/64">
                            {compactText(signal.summary, 170)}
                          </p>
                        )}
                        {signal.rules.length > 0 && (
                          <div className="mt-2 grid gap-1 text-sm text-ink/62">
                            {signal.rules.slice(0, 2).map((rule) => (
                              <p key={rule}>{compactText(rule, 140)}</p>
                            ))}
                          </div>
                        )}
                      </article>
                    ))}
                    {!routineSignals.length && (
                      <div className="py-4 text-sm font-medium text-ink/52">
                        Add a strategy source to generate a source-backed routine.
                      </div>
                    )}
                  </div>
                </section>

                <section className="rounded-lg border border-line bg-card/86 p-4 shadow-panel">
                  <div className="flex items-center justify-between">
                    <h2 className="text-base font-semibold text-ink">Readiness</h2>
                    <ShieldCheck aria-hidden="true" className="text-moss" size={20} strokeWidth={2.1} />
                  </div>
                  <div className="mt-4 space-y-3 text-sm">
                    <SnapshotRow label="Validation" value={recommendedRoutine.validationState} />
                    <SnapshotRow label="Confidence" value={`${Math.round(recommendedRoutine.confidence * 100)}%`} />
                    <SnapshotRow label="Sources" value={String(recommendedRoutine.sourceCount)} />
                    <SnapshotRow
                      label="Closed trades"
                      value={String(routineStrategyStat?.count ?? 0)}
                    />
                    <SnapshotRow
                      label="Routine days"
                      value={String(viewState.journal.filter((entry) => entry.routineDone).length)}
                    />
                  </div>
                  <div className="mt-4 grid gap-2">
                    <Button onClick={() => setActiveTab("trades")} type="button">
                      <Activity aria-hidden="true" size={17} strokeWidth={2.2} />
                      Open paper ticket
                    </Button>
                    <Button onClick={() => setActiveTab("journal")} type="button" variant="outline">
                      <CalendarCheck aria-hidden="true" size={17} strokeWidth={2.2} />
                      Journal prep
                    </Button>
                  </div>
                </section>
              </div>
            </section>
          )}

          {activeTab === "insights" && (
            <section
              aria-labelledby="insights-tab"
              className="grid gap-4 xl:grid-cols-[1fr_380px]"
              id="insights-panel"
              role="tabpanel"
            >
              <section className="rounded-lg border border-line bg-card/86 p-4 shadow-panel">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <h2 className="text-base font-semibold text-ink">Trading Insights</h2>
                    <p className="mt-1 text-sm text-ink/58">
                      {state.trades.length} trades, {sourceStrategySignals.length} source signals
                    </p>
                  </div>
                  <BrainCircuit aria-hidden="true" className="text-signal" size={21} strokeWidth={2.1} />
                </div>

                <div className="mt-5 grid gap-3 md:grid-cols-2">
                  {tradingInsights.map((insight) => (
                    <InsightCard insight={insight} key={insight.title} />
                  ))}
                </div>
                <RoutinePlaybookCard routine={recommendedRoutine} />
                {optimalStrategy && (
                  <div className="mt-4">
                    <StrategyEvaluationCard
                      evaluation={optimalStrategy}
                      onApply={applyEvaluationDraft}
                      title="Optimal knowledge-base strategy"
                    />
                  </div>
                )}
              </section>

              <section className="overflow-hidden rounded-lg border border-line bg-card/86 shadow-panel">
                <div className="flex items-center justify-between border-b border-line px-4 py-3">
                  <div>
                    <h2 className="text-base font-semibold text-ink">Strategy Scoreboard</h2>
                    <p className="mt-1 text-sm text-ink/58">trade validation plus source evidence</p>
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
                            {stat.count} trades / {stat.sourceCount} sources / {stat.winRate}% win rate
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
                        <SnapshotRow label="Best" value={stat.bestTrade ? formatCurrency(tradePnl(stat.bestTrade)) : "research"} />
                        <SnapshotRow label="Worst" value={stat.worstTrade ? formatCurrency(tradePnl(stat.worstTrade)) : "research"} />
                      </div>
                      {stat.researchSummary && (
                        <p className="mt-4 text-sm leading-6 text-ink/64">{stat.researchSummary}</p>
                      )}
                      {stat.researchRules.length > 0 && (
                        <div className="mt-3 grid gap-1 text-sm text-ink/62">
                          {stat.researchRules.slice(0, 3).map((rule) => (
                            <p key={rule}>{rule}</p>
                          ))}
                        </div>
                      )}
                      <div className="mt-4 flex flex-wrap gap-2">
                        <Badge variant="secondary">{stat.validationState}</Badge>
                        {stat.symbols.slice(0, 4).map(tagChip)}
                        {stat.setups.slice(0, 3).map(tagChip)}
                        {stat.sourceTitles.slice(0, 2).map(tagChip)}
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
            <section
              aria-labelledby="graph-tab"
              className="grid gap-4 xl:grid-cols-[1fr_360px]"
              id="graph-panel"
              role="tabpanel"
            >
              <section className="rounded-lg border border-line bg-card/86 p-4 shadow-panel">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <h2 className="text-base font-semibold text-ink">Strategy Atlas</h2>
                    <p className="mt-1 text-sm text-ink/58">
                      {graph.nodes.length} nodes / {graph.edges.length} edges
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      className="grid h-9 w-9 place-items-center rounded-md border border-line bg-card text-ink/70 transition hover:bg-paper"
                      onClick={() => zoomGraph(0.18)}
                      title="Zoom in"
                      type="button"
                    >
                      <ZoomIn aria-hidden="true" size={17} />
                    </button>
                    <button
                      className="grid h-9 w-9 place-items-center rounded-md border border-line bg-card text-ink/70 transition hover:bg-paper"
                      onClick={() => zoomGraph(-0.18)}
                      title="Zoom out"
                      type="button"
                    >
                      <ZoomOut aria-hidden="true" size={17} />
                    </button>
                    <button
                      className="grid h-9 w-9 place-items-center rounded-md border border-line bg-card text-ink/70 transition hover:bg-paper"
                      onClick={() => selectedGraphNode && focusGraphNode(selectedGraphNode)}
                      title="Focus selected node"
                      type="button"
                    >
                      <Crosshair aria-hidden="true" size={17} />
                    </button>
                    <button
                      className="grid h-9 w-9 place-items-center rounded-md border border-line bg-card text-ink/70 transition hover:bg-paper"
                      onClick={resetGraphView}
                      title="Recenter"
                      type="button"
                    >
                      <GitBranch aria-hidden="true" size={17} />
                    </button>
                  </div>
                </div>

                <div className="mt-5 overflow-hidden rounded-lg border border-ink/10 bg-[#171a1d]">
                  <svg
                    aria-label="Trading relationship atlas"
                    className="h-[560px] w-full cursor-grab touch-none active:cursor-grabbing"
                    onPointerDown={(event) => {
                      if ((event.target as Element).closest("[data-graph-node='true']")) return;
                      setGraphDrag({
                        startX: event.clientX,
                        startY: event.clientY,
                        startView: graphView
                      });
                    }}
                    onPointerLeave={() => setGraphDrag(null)}
                    onPointerMove={panGraph}
                    onPointerUp={() => setGraphDrag(null)}
                    onWheel={(event) => {
                      event.preventDefault();
                      zoomGraph(event.deltaY > 0 ? -0.12 : 0.12);
                    }}
                    role="img"
                    viewBox={graphViewBox}
                  >
                    <rect fill="#171a1d" height="3000" width="3000" x="-1040" y="-1220" />
                    {graphClusterGuides.map((guide) => (
                      <g key={guide.label}>
                        <rect
                          fill="#f7f3ea"
                          height={guide.height}
                          opacity="0.035"
                          rx="14"
                          stroke="#d8d1c3"
                          strokeDasharray="6 8"
                          strokeOpacity="0.18"
                          width={guide.width}
                          x={guide.x}
                          y={guide.y}
                        />
                        <text
                          fill="#d8d1c3"
                          fontSize="11"
                          fontWeight={700}
                          opacity="0.48"
                          x={guide.x + 14}
                          y={guide.y + 22}
                        >
                          {guide.label}
                        </text>
                      </g>
                    ))}
                    {graph.edges.map((edge) => {
                      const from = graphNodeLookup.get(edge.from);
                      const to = graphNodeLookup.get(edge.to);
                      if (!from || !to) return null;
                      const active =
                        graphFocusMode && (edge.from === selectedGraphNode?.id || edge.to === selectedGraphNode?.id);
                      const memoryEdge = from.type === "memory" || to.type === "memory";
                      const opacity = active ? 0.76 : memoryEdge ? 0.055 : graphFocusMode ? 0.07 : 0.16;

                      return (
                        <path
                          d={graphEdgePath(from, to)}
                          fill="none"
                          key={edge.id}
                          opacity={opacity}
                          stroke="#d8d1c3"
                          strokeLinecap="round"
                          strokeWidth={active ? 1.8 : 0.9}
                        />
                      );
                    })}
                    {graph.nodes.map((node) => {
                      const style = graphNodeStyle(node.type);
                      const selected = selectedGraphNode?.id === node.id;
                      const focused = focusedGraphNodeIds.has(node.id);
                      const labelVisible = graphLabelVisible(node, selected, focused, graphFocusMode);
                      const muted = graphFocusMode && !focused;

                      return (
                        <g
                          className="cursor-pointer outline-none"
                          data-graph-node="true"
                          key={node.id}
                          onClick={() => selectGraphNode(node.id, true)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              selectGraphNode(node.id, true);
                            }
                          }}
                          role="button"
                          tabIndex={0}
                        >
                          <title>{node.label}</title>
                          <circle
                            cx={node.x}
                            cy={node.y}
                            fill={style.fill}
                            opacity={muted ? 0.38 : 1}
                            r={graphNodeRadius(node)}
                            stroke={selected ? "#ffffff" : style.stroke}
                            strokeWidth={selected ? 3 : focused ? 2 : 1.25}
                          />
                          {labelVisible && (
                            <text
                              fill="#f7f3ea"
                              fontSize={selected ? "12" : "10.5"}
                              fontWeight={selected ? 700 : 600}
                              opacity={selected ? 1 : focused ? 0.88 : 0.62}
                              textAnchor="middle"
                              x={node.x}
                              y={node.y + graphNodeRadius(node) + 15}
                            >
                              {shortLabel(node.label, node.type === "trade" ? 11 : 17)}
                            </text>
                          )}
                        </g>
                      );
                    })}
                  </svg>
                </div>
              </section>

              <section className="rounded-lg border border-line bg-card/86 p-4 shadow-panel">
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
                          className="flex min-h-10 items-center justify-between gap-3 rounded-md border border-line bg-card px-3 text-left text-sm transition hover:bg-paper"
                          key={edge.id}
                          onClick={() => other && selectGraphNode(other.id, true)}
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
          <section className="rounded-lg border border-line bg-card/86 p-4 shadow-panel">
            <h2 className="text-base font-semibold text-ink">Workspace</h2>
            <div className="mt-4 grid gap-2">
              <Button
                onClick={exportWorkspace}
                type="button"
                variant="outline"
              >
                <Download aria-hidden="true" size={17} strokeWidth={2.2} />
                Export JSON
              </Button>
              <label className="inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-md border border-line bg-card px-3 text-sm font-semibold text-ink transition hover:bg-paper">
                <Upload aria-hidden="true" size={17} strokeWidth={2.2} />
                Import JSON
                <input accept="application/json" className="hidden" onChange={importWorkspace} type="file" />
              </label>
            </div>
          </section>

          <section className="rounded-lg border border-line bg-card/86 p-4 shadow-panel">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-ink">AI Router</h2>
              <Sparkles aria-hidden="true" className="text-caution" size={20} strokeWidth={2.1} />
            </div>
            <div className="mt-4 space-y-3 text-sm">
              <SnapshotRow label="Mode" value={aiRouterStatus?.mode ?? (apiOnline ? "unknown" : "offline")} />
              <SnapshotRow
                label="Active"
                value={aiRouterStatus?.active_provider_id ?? (aiRouterStatus?.mode === "auto" ? "none" : "local rules")}
              />
              <div className="flex flex-wrap gap-2">
                {aiRouterStatus?.providers.map((provider) => (
                  <Badge key={provider.id} variant={provider.configured ? "default" : "secondary"}>
                    {provider.label}
                  </Badge>
                ))}
                {!aiRouterStatus?.providers.length && <Badge variant="secondary">local semantic rules</Badge>}
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-line bg-card/86 p-4 shadow-panel">
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
      {strategyInfo.technical_tags?.length ? (
        <div className="mt-3">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink/45">Technicals</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {essentialTechnicalTags(strategyInfo.technical_tags).map(tagChip)}
          </div>
        </div>
      ) : null}
      <StrategyRuleList label="Entry" values={strategyInfo.entry_rules ?? []} />
      <StrategyRuleList label="Exit" values={strategyInfo.exit_rules ?? []} />
      <StrategyRuleList label="Risk" values={strategyInfo.risk_rules ?? []} />
    </div>
  );
}

function SourceDetailsSummary({ details }: { details: SourceDetails }) {
  const authors = details.authors?.filter(Boolean) ?? [];
  const subjects = details.subjects?.filter(Boolean) ?? [];
  const notes = details.implementation_notes?.filter(Boolean) ?? [];
  const abstract = details.abstract ?? "";
  const authorLabel =
    authors.length > 3 ? `${authors.slice(0, 3).join(", ")} +${authors.length - 3}` : authors.join(", ");

  return (
    <div className="mt-4 border-l-2 border-ink/20 pl-3">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink/48">
        Source Details
      </p>
      <div className="mt-2 grid gap-2 text-sm md:grid-cols-2">
        {authors.length > 0 && <SnapshotRow label="Authors" value={authorLabel} />}
        {details.submitted && <SnapshotRow label="Submitted" value={details.submitted} />}
        {details.primary_category && (
          <SnapshotRow label="Category" value={details.primary_category} />
        )}
        {details.comments && <SnapshotRow label="Comments" value={compactText(details.comments, 80)} />}
        {details.doi && <SnapshotRow label="DOI" value={details.doi} />}
      </div>
      {subjects.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">{subjects.slice(0, 3).map(tagChip)}</div>
      )}
      {abstract && (
        <p className="mt-3 text-sm leading-6 text-ink/66">
          {compactText(abstract, 260)}
        </p>
      )}
      {notes.length > 0 && (
        <div className="mt-3 grid gap-2">
          {notes.slice(0, 2).map((note) => (
            <p key={note} className="rounded-md bg-paper/65 px-3 py-2 text-sm leading-6 text-ink/68">
              {compactText(note, 170)}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function StrategyRuleList({ label, values }: { label: string; values: string[] }) {
  if (!values.length) return null;
  const conciseValues = Array.from(new Set(values.map((value) => compactText(value, 150)))).slice(0, 2);

  return (
    <div className="mt-3">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink/45">{label}</p>
      <ul className="mt-1 grid gap-1 text-sm leading-6 text-ink/66">
        {conciseValues.map((value) => (
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

function RoutinePlaybookCard({
  routine,
  variant = "compact"
}: {
  routine: RecommendedRoutine;
  variant?: "compact" | "full";
}) {
  const full = variant === "full";

  return (
    <article
      className={[
        "rounded-lg border border-signal/25 bg-signal/5",
        full ? "p-5 shadow-panel" : "mt-4 p-4"
      ].join(" ")}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink/48">
            {full ? "Routine Playbook" : "Recommended Routine"}
          </p>
          <h3 className={["mt-2 font-semibold text-ink", full ? "text-xl" : "text-base"].join(" ")}>
            {routine.strategyName}
          </h3>
          <p className="mt-1 text-sm leading-6 text-ink/58">
            {routine.setupFocus} / {routine.sourceCount} source{routine.sourceCount === 1 ? "" : "s"} /{" "}
            {Math.round(routine.confidence * 100)}% confidence
          </p>
        </div>
        <Badge variant={routine.validationState === "live" ? "secondary" : "default"}>
          {routine.validationState}
        </Badge>
      </div>
      {routine.technicalTags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {essentialTechnicalTags(routine.technicalTags, 7).map(tagChip)}
        </div>
      )}
      <div className={["grid", full ? "mt-5 gap-5 lg:grid-cols-2" : "mt-4 gap-3 lg:grid-cols-2"].join(" ")}>
        {routine.blocks.map((block) => (
          <section
            className={[
              "border-l-2 pl-3",
              block.title === "When To Execute" ? "border-caution/60" : "border-signal/30",
              block.title === "Risk And Review" && full ? "lg:col-span-2" : ""
            ].join(" ")}
            key={block.title}
          >
            <h4 className="text-sm font-semibold text-ink">{block.title}</h4>
            <ul className="mt-2 grid gap-2 text-sm leading-6 text-ink/66">
              {block.items.slice(0, full ? 4 : 3).map((item) => (
                <li key={item}>{compactText(item, 150)}</li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </article>
  );
}

function StrategyEvaluationCard({
  evaluation,
  onApply,
  title
}: {
  evaluation: StrategyEvaluation;
  onApply: (evaluation: StrategyEvaluation) => void;
  title: string;
}) {
  const toneClass =
    evaluation.decision === "beneficial"
      ? "border-moss/25 bg-moss/10"
      : evaluation.decision === "weakens-edge"
        ? "border-loss/25 bg-loss/10"
        : "border-caution/30 bg-caution/10";

  return (
    <article className={`mt-4 rounded-lg border p-4 ${toneClass}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink/48">{title}</p>
          <h3 className="mt-2 text-sm font-semibold text-ink">{evaluation.title}</h3>
          <p className="mt-1 text-xs font-medium text-ink/52">
            {evaluation.decision} / {Math.round(evaluation.score * 100)}% score
          </p>
        </div>
        <Badge variant={evaluation.decision === "beneficial" ? "default" : "warning"}>
          AI
        </Badge>
      </div>
      <p className="mt-3 text-sm leading-6 text-ink/66">{evaluation.rationale}</p>
      {evaluation.technical_tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {essentialTechnicalTags(evaluation.technical_tags).map(tagChip)}
        </div>
      )}
      <details className="mt-3 rounded-md border border-line bg-card/70 px-3 py-2 text-sm">
        <summary className="cursor-pointer font-semibold text-ink">Why included / excluded</summary>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-moss">Included</p>
            <ul className="mt-2 grid gap-1 text-ink/66">
              {evaluation.included.slice(0, 5).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-loss">Excluded</p>
            <ul className="mt-2 grid gap-1 text-ink/66">
              {evaluation.excluded.slice(0, 5).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      </details>
      <button
        className="mt-3 inline-flex min-h-9 items-center gap-2 rounded-md border border-caution/30 bg-card px-3 text-sm font-semibold text-ink transition hover:bg-caution/15"
        onClick={() => onApply(evaluation)}
        type="button"
      >
        <Wand2 aria-hidden="true" size={16} strokeWidth={2.2} />
        Fill trade draft
      </button>
    </article>
  );
}

function TradeRecommendationCard({
  recommendation,
  onApply
}: {
  recommendation: TradeRecommendation;
  onApply: (recommendation: TradeRecommendation) => void;
}) {
  return (
    <article className="rounded-lg border border-caution/25 bg-caution/10 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink">{recommendation.title}</h3>
          <p className="mt-1 text-xs font-medium text-ink/52">
            {Math.round(recommendation.confidence * 100)}% confidence
          </p>
        </div>
        <Badge variant="warning">AI</Badge>
      </div>
      <p className="mt-3 text-sm font-medium leading-6 text-ink">{recommendation.action}</p>
      <p className="mt-2 text-sm leading-6 text-ink/64">{recommendation.rationale}</p>
      {recommendation.technical_tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {essentialTechnicalTags(recommendation.technical_tags).map(tagChip)}
        </div>
      )}
      {recommendation.risk_notes.length > 0 && (
        <div className="mt-3 border-l-2 border-loss/30 pl-3 text-sm leading-6 text-ink/64">
          {recommendation.risk_notes.slice(0, 2).map((note) => (
            <p key={note}>{note}</p>
          ))}
        </div>
      )}
      {recommendation.evidence.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {recommendation.evidence.slice(0, 3).map(tagChip)}
        </div>
      )}
      {recommendation.draft && (
        <button
          className="mt-3 inline-flex min-h-9 items-center gap-2 rounded-md border border-caution/30 bg-card px-3 text-sm font-semibold text-ink transition hover:bg-caution/15"
          onClick={() => onApply(recommendation)}
          type="button"
        >
          <Wand2 aria-hidden="true" size={16} strokeWidth={2.2} />
          Fill trade draft
        </button>
      )}
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

function comparableLabel(value: string) {
  const aliases: Record<string, string> = {
    orb: "opening range breakout",
    "opening range": "opening range breakout",
    vwap: "vwap"
  };
  const normalized = value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  return aliases[normalized] ?? normalized;
}

function labelsOverlap(left: string, right: string) {
  const a = comparableLabel(left);
  const b = comparableLabel(right);
  if (!a || !b) return false;
  return a === b || a.includes(b) || b.includes(a);
}

function buildSourceStrategySignals(vault: VaultItem[], trades: TradeEntry[]): SourceStrategySignal[] {
  const tradeStrategies = Array.from(
    new Set(trades.map((trade) => trade.strategy.trim()).filter(Boolean))
  );
  const tradeSetups = Array.from(new Set(trades.map((trade) => trade.setup.trim()).filter(Boolean)));

  return vault
    .filter((item) => {
      const tags = [...item.tags, ...(item.aiTags ?? [])].join(" ").toLowerCase();
      return Boolean(item.strategyInfo) || item.kind === "strategy" || tags.includes("strategy");
    })
    .map((item) => {
      const info = item.strategyInfo;
      const matchedStrategy =
        tradeStrategies.find((strategy) => labelsOverlap(strategy, info?.name ?? item.title)) ??
        tradeStrategies.find((strategy) => labelsOverlap(strategy, info?.setup ?? "")) ??
        tradeStrategies.find((strategy) =>
          item.tags.some((tag) => labelsOverlap(strategy, tag))
        );
      const matchedSetup =
        tradeSetups.find((setup) => labelsOverlap(setup, info?.setup ?? "")) ??
        tradeSetups.find((setup) => item.tags.some((tag) => labelsOverlap(setup, tag)));
      const strategyName = matchedStrategy ?? info?.name ?? matchedSetup ?? item.title;
      const rules = [
        ...(info?.entry_rules ?? []),
        ...(info?.exit_rules ?? []),
        ...(info?.risk_rules ?? [])
      ];
      const attributes = uniqueTags([
        info?.market,
        info?.timeframe,
        ...(info?.indicators ?? []),
        ...(info?.technical_tags ?? []),
        ...(item.technicalTags ?? []),
        ...(matchedSetup ? [matchedSetup] : [])
      ]);

      return {
        sourceId: item.id,
        sourceTitle: item.title,
        strategyName,
        setup: info?.setup ?? matchedSetup,
        summary: info?.summary,
        confidence: info?.confidence ?? 0.4,
        tags: uniqueTags([...item.tags, ...(item.aiTags ?? []), ...(item.technicalTags ?? [])]),
        rules,
        attributes
      };
    });
}

function buildStrategyStats(state: WorkspaceState, sourceSignals: SourceStrategySignal[]): StrategyStat[] {
  const groups = state.trades.reduce<Record<string, TradeEntry[]>>((acc, trade) => {
    const key = trade.strategy.trim() || "Untitled strategy";
    acc[key] = [...(acc[key] ?? []), trade];
    return acc;
  }, {});
  const names = new Set([
    ...Object.keys(groups),
    ...sourceSignals.map((signal) => signal.strategyName.trim()).filter(Boolean)
  ]);

  return Array.from(names)
    .map((name) => {
      const group = groups[name] ?? [];
      const relatedSignals = sourceSignals.filter((signal) => labelsOverlap(signal.strategyName, name));
      const sorted = [...group].sort((a, b) => tradePnl(b) - tradePnl(a));
      const bestTrade = sorted[0];
      const worstTrade = sorted[sorted.length - 1];
      const pnls = group.map(tradePnl);
      const totalPnl = pnls.reduce((sum, pnl) => sum + pnl, 0);
      const wins = pnls.filter((pnl) => pnl > 0).length;
      const losses = pnls.filter((pnl) => pnl < 0).length;
      const symbols = Array.from(new Set(group.map((trade) => trade.symbol).filter(Boolean)));
      const setups = uniqueTags([
        ...group.map((trade) => trade.setup),
        ...relatedSignals.map((signal) => signal.setup ?? "")
      ]);
      const researchRules = uniqueTags(relatedSignals.flatMap((signal) => signal.rules)).slice(0, 6);
      const researchConfidence = relatedSignals.length
        ? relatedSignals.reduce((sum, signal) => sum + signal.confidence, 0) / relatedSignals.length
        : 0;
      const validationState: StrategyStat["validationState"] =
        group.length && relatedSignals.length ? "mixed" : group.length ? "live" : "research";

      return {
        name,
        count: group.length,
        wins,
        losses,
        winRate: group.length ? Math.round((wins / group.length) * 100) : 0,
        totalPnl,
        avgPnl: group.length ? totalPnl / group.length : 0,
        symbols,
        setups,
        bestTrade,
        worstTrade,
        sourceCount: relatedSignals.length,
        sourceTitles: relatedSignals.map((signal) => signal.sourceTitle),
        researchConfidence,
        researchSummary: relatedSignals.find((signal) => signal.summary)?.summary ?? undefined,
        researchRules,
        validationState
      };
    })
    .sort((a, b) => {
      if (a.count && !b.count) return -1;
      if (!a.count && b.count) return 1;
      return b.totalPnl - a.totalPnl || b.researchConfidence - a.researchConfidence;
    });
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

function buildLocalStrategyEvaluation(
  idea: string,
  symbol: string,
  state: WorkspaceState,
  sourceSignals: SourceStrategySignal[]
): StrategyEvaluation {
  const profile = technicalProfileForText(idea);
  const tags = uniqueTags([
    ...technicalTagsForProfile(profile),
    ...singleWordTags.filter((tag) => new RegExp(`\\b${tag}\\b`, "i").test(idea)),
    ...semanticTagRules.filter(([phrase]) => idea.toLowerCase().includes(phrase)).map(([, tag]) => tag)
  ]).sort();
  const relatedSources = sourceSignals.filter((signal) =>
    signal.tags.some((tag) => tags.some((candidate) => labelsOverlap(candidate, tag)))
  );
  const relatedTrades = state.trades.filter((trade) =>
    [trade.strategy, trade.setup, trade.notes].some((value) =>
      tags.some((tag) => labelsOverlap(value, tag))
    )
  );
  const closedRelated = relatedTrades.filter(isTradeClosed);
  const avgPnl = averagePnl(closedRelated);
  const score = Math.max(
    0.05,
    Math.min(
      0.95,
      0.36 +
        Math.min(0.24, relatedSources.length * 0.06) +
        Math.min(0.16, tags.length * 0.015) +
        (avgPnl > 0 ? 0.12 : avgPnl < 0 ? -0.12 : 0)
    )
  );
  const decision =
    !tags.length ? "needs-structure" : score >= 0.68 ? "beneficial" : score >= 0.48 ? "observe" : "weakens-edge";
  const setup = profile.setups?.[0] ?? setupRules.find(([phrase]) => idea.toLowerCase().includes(phrase))?.[1];
  const tradeSymbol = symbol || (tags.includes("futures") ? "ES" : tags.includes("crypto") ? "BTC" : "SPY");
  const side: TradeEntry["side"] = /\b(short|fade|breakdown|sell)\b/i.test(idea) ? "short" : "long";
  const title = idea.split(".")[0].slice(0, 90) || setup || "Plain-English strategy idea";
  const included = [
    setup ? `Setup extracted: ${setup}.` : "",
    tags.length ? `Technicals extracted: ${tags.slice(0, 8).join(", ")}.` : "",
    relatedSources.length ? `${relatedSources.length} source signal(s) overlap.` : "",
    closedRelated.length ? `${closedRelated.length} related closed trade(s), average ${formatCurrency(avgPnl)}.` : ""
  ].filter(Boolean);
  const excluded = [
    tags.length ? "" : "No concrete technical tags were found.",
    relatedSources.length ? "" : "No learned source strongly supports this idea yet.",
    closedRelated.length ? "" : "No matching closed-trade sample exists for validation.",
    /\b(risk|stop|invalidation|size)\b/i.test(idea) ? "" : "Risk or invalidation was not explicit."
  ].filter(Boolean);

  return {
    title,
    decision,
    score,
    confidence: score,
    rationale: `${decision} at ${Math.round(score * 100)}% score. ${included[0] ?? excluded[0] ?? ""}`,
    technical_tags: tags,
    technical_profile: profile,
    included: included.length ? included : ["Idea captured locally."],
    excluded,
    draft: {
      symbol: tradeSymbol,
      side,
      strategy: title,
      setup: setup ?? "Source-backed setup",
      emotion: "patient",
      quantity: "1",
      fees: "0",
      notes: `${decision} local evaluation. Tags: ${tags.slice(0, 6).join(", ")}.`
    }
  };
}

function buildRecommendedRoutine(
  state: WorkspaceState,
  strategyStats: StrategyStat[],
  sourceSignals: SourceStrategySignal[],
  optimalStrategy: StrategyEvaluation | null,
  tradeRecommendations: TradeRecommendation[]
): RecommendedRoutine {
  const primaryStat =
    strategyStats.find((stat) => stat.validationState === "mixed") ??
    strategyStats.find((stat) => stat.sourceCount > 0) ??
    strategyStats[0];
  const leadingRecommendation = tradeRecommendations[0];
  const strategyName =
    primaryStat?.name ??
    optimalStrategy?.title ??
    leadingRecommendation?.strategy ??
    leadingRecommendation?.title ??
    "Knowledge-base routine";
  const relatedSignals = primaryStat
    ? sourceSignals.filter((signal) => labelsOverlap(signal.strategyName, primaryStat.name))
    : sourceSignals;
  const signalPool = relatedSignals.length ? relatedSignals : sourceSignals;
  const sourceCount = primaryStat?.sourceCount ?? signalPool.length;
  const setupFocus =
    primaryStat?.setups[0] ??
    optimalStrategy?.draft.setup ??
    leadingRecommendation?.setup ??
    signalPool.find((signal) => signal.setup)?.setup ??
    "Source-backed setup";
  const technicalTags = uniqueTags([
    ...(primaryStat?.setups ?? []),
    ...(signalPool.flatMap((signal) => [...signal.tags, ...signal.attributes]) ?? []),
    ...(optimalStrategy?.technical_tags ?? []),
    ...(leadingRecommendation?.technical_tags ?? [])
  ]);
  const rules = uniqueTags(signalPool.flatMap((signal) => signal.rules));
  const entryRules = preferredRoutineRules(
    rules,
    ["entry", "enter", "trigger", "break", "reclaim", "confirmation", "align", "long", "short"],
    [
      `Wait for ${setupFocus} conditions to align before opening a paper trade.`,
      "Use the live quote ticket only after direction, size, and invalidation are clear."
    ]
  );
  const exitRules = preferredRoutineRules(
    rules,
    ["exit", "target", "take profit", "profit", "sell", "cover", "trail"],
    ["Predefine the target or management rule before entry."]
  );
  const riskRules = preferredRoutineRules(
    rules,
    ["risk", "stop", "invalidation", "max loss", "position size", "size", "atr"],
    ["Size down when the setup is not directly supported by learned source evidence."]
  );
  const journalCount = state.journal.length;
  const routineDays = state.journal.filter((entry) => entry.routineDone).length;
  const validationState = primaryStat?.validationState ?? (sourceCount ? "research" : "draft");
  const confidence =
    primaryStat?.researchConfidence ||
    optimalStrategy?.confidence ||
    leadingRecommendation?.confidence ||
    (sourceCount ? 0.48 : 0.28);

  return {
    strategyName,
    sourceCount,
    confidence: Math.min(0.95, Math.max(0.05, confidence)),
    validationState,
    setupFocus,
    technicalTags,
    blocks: [
      {
        title: "Routine",
        items: [
          `Start with ${strategyName}; review the source-backed setup before scanning.`,
          technicalTags.length
            ? `Mark the key technicals: ${essentialTechnicalTags(technicalTags, 5).join(", ")}.`
            : "Mark trend, support/resistance, volatility, and session context.",
          journalCount
            ? `${routineDays}/${journalCount} journal entries are marked routine complete; keep logging pre-trade state.`
            : "Create a journal entry before trading and mark whether the routine was completed."
        ]
      },
      {
        title: "How To Trade",
        items: [
          primaryStat?.count
            ? `Favor the validated side of ${strategyName}: ${primaryStat.count} logged trade(s), ${primaryStat.winRate}% win rate.`
            : `Treat ${strategyName} as research until more closed trades validate it.`,
          leadingRecommendation?.action ?? `Trade only when ${setupFocus} matches the learned source rules.`,
          "Use paper orders first; promote sizing only after journal and closed-trade evidence improve."
        ]
      },
      {
        title: "Setup To Look For",
        items: [
          setupFocus,
          primaryStat?.symbols.length
            ? `Most relevant symbols: ${primaryStat.symbols.slice(0, 4).join(", ")}.`
            : "Pick the symbol whose market and timeframe match the extracted strategy.",
          signalPool[0]?.summary ?? optimalStrategy?.rationale ?? "Prefer clear alignment over isolated indicators."
        ]
      },
      {
        title: "When To Execute",
        items: entryRules
      },
      {
        title: "Risk And Review",
        items: [...riskRules.slice(0, 2), ...exitRules.slice(0, 1), "After closing, journal whether the setup, state, and execution matched the plan."]
      }
    ]
  };
}

function preferredRoutineRules(rules: string[], needles: string[], fallback: string[], limit = 3) {
  const matched = rules.filter((rule) => {
    const lowered = rule.toLowerCase();
    return needles.some((needle) => lowered.includes(needle));
  });
  return uniqueTags([...matched, ...fallback]).slice(0, limit);
}

function buildTradingInsights(
  state: WorkspaceState,
  strategyStats: StrategyStat[],
  sourceSignals: SourceStrategySignal[],
  aiRouterStatus: AiRouterStatus | null,
  tradeRecommendations: TradeRecommendation[]
): TradingInsight[] {
  const learnedSources = state.vault.filter((item) => item.learningSummary);
  const learnedChunks = learnedSources.reduce(
    (sum, item) => sum + (item.learningSummary?.chunk_count ?? 0),
    0
  );

  if (!state.trades.length) {
    const strategySources = sourceSignals.length;

    return [
      {
        title: "Strategy Edge",
        value: "Waiting",
        detail: "Log closed trades with strategy, setup, and state labels to calculate edge.",
        tone: "neutral"
      },
      {
        title: "Strategy Research",
        value: `${strategySources} sources`,
        detail: strategySources
          ? "Generated strategy fields are ready in the vault and map."
          : "Upload strategy notes or links to generate setup, entry, exit, and risk fields.",
        tone: strategySources ? "good" : "neutral"
      },
      {
        title: "AI Router",
        value: aiRouterStatus?.mode ?? "offline",
        detail:
          aiRouterStatus?.active_provider_id
            ? `Cloud extraction is routed through ${aiRouterStatus.active_provider_id}.`
            : "Local semantic extraction is active until an opt-in provider key is configured.",
        tone: aiRouterStatus?.active_provider_id ? "good" : "neutral"
      },
      {
        title: "Memory Bot",
        value: `${learnedChunks} chunks`,
        detail: learnedSources.length
          ? `${learnedSources.length} sources have been learned into the map.`
          : "Sources become memory chunks and graph facts once saved through the API.",
        tone: learnedSources.length ? "good" : "neutral"
      },
      {
        title: "Trade Guidance",
        value: `${tradeRecommendations.length} ideas`,
        detail: tradeRecommendations[0]?.action ?? "Recommendations appear after strategy sources are learned.",
        tone: tradeRecommendations.length ? "good" : "neutral"
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
  const sourceBackedStrategies = strategyStats.filter((stat) => stat.sourceCount > 0);
  const unvalidatedResearch = strategyStats.filter(
    (stat) => stat.validationState === "research" && stat.sourceCount > 0
  );
  const insights: TradingInsight[] = [
    {
      title: "Net Edge",
      value: formatCurrency(totalPnl),
      detail: `${state.trades.length} closed trades at ${winRate}% win rate.`,
      tone: totalPnl > 0 ? "good" : totalPnl < 0 ? "bad" : "neutral"
    }
  ];

  if (sourceBackedStrategies.length) {
    const validatedCount = sourceBackedStrategies.filter((stat) => stat.count > 0).length;
    insights.push({
      title: "Strategy Research",
      value: `${sourceBackedStrategies.length} linked`,
      detail: `${validatedCount} source-backed strategies have trade validation; ${unvalidatedResearch.length} still need a sample.`,
      tone: unvalidatedResearch.length ? "warn" : "good"
    });
  }

  if (tradeRecommendations.length) {
    insights.push({
      title: "Trade Guidance",
      value: tradeRecommendations[0].title,
      detail: tradeRecommendations[0].action,
      tone: tradeRecommendations[0].confidence >= 0.7 ? "good" : "warn"
    });
  }

  if (learnedSources.length) {
    insights.push({
      title: "Memory Bot",
      value: `${learnedChunks} chunks`,
      detail: `${learnedSources.length} sources are available as graph memory and strategy evidence.`,
      tone: "good"
    });
  }

  if (bestStrategy) {
    insights.push({
      title: "Best Strategy",
      value: bestStrategy.name,
      detail: `${formatCurrency(bestStrategy.totalPnl)} across ${bestStrategy.count} trades; ${bestStrategy.sourceCount} sources attached.`,
      tone: bestStrategy.totalPnl >= 0 ? "good" : "warn"
    });
  }

  if (unvalidatedResearch[0]) {
    const candidate = unvalidatedResearch[0];
    insights.push({
      title: "Next Validation",
      value: candidate.name,
      detail:
        candidate.researchRules[0] ??
        `${candidate.sourceCount} source(s) define this strategy, but no closed trades are logged yet.`,
      tone: "warn"
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

  insights.push({
    title: "AI Router",
    value: aiRouterStatus?.mode ?? "offline",
    detail:
      aiRouterStatus?.active_provider_id
        ? `Provider order is active; current route starts with ${aiRouterStatus.active_provider_id}.`
        : "Cloud AI is opt-in. The app is using deterministic local extraction right now.",
    tone: aiRouterStatus?.active_provider_id ? "good" : "neutral"
  });

  return insights.slice(0, 6);
}

function averagePnl(trades: TradeEntry[]) {
  if (!trades.length) return 0;
  return trades.reduce((sum, trade) => sum + tradePnl(trade), 0) / trades.length;
}

function parseQuickTrade(raw: string): QuickTradeDraft | null {
  const text = raw.trim();
  if (!text) return null;
  const date = text.match(/\b\d{4}-\d{2}-\d{2}\b/)?.[0] ?? new Date().toISOString().slice(0, 10);
  const textWithoutDate = text.replace(date, " ");
  const symbol = textWithoutDate.match(/\b[A-Z][A-Z0-9./-]{0,9}\b/i)?.[0]?.toUpperCase();
  const side: TradeEntry["side"] = /\b(short|sell|sold|s)\b/i.test(text) ? "short" : "long";
  const feesMatch = text.match(/\b(?:fee|fees|commission)[:=\s]+(\d+(?:\.\d+)?)/i);
  const entryMatch = text.match(/\b(?:entry|in|buy|short|long)[:=@\s]+(\d+(?:\.\d+)?)/i);
  const exitMatch = text.match(/\b(?:exit|out|sell|cover|target)[:=@\s]+(\d+(?:\.\d+)?)/i);
  const qtyMatch = text.match(/\b(?:qty|quantity|shares|contracts|size|x)[:=\s]*(\d+(?:\.\d+)?)/i);
  const numericText = textWithoutDate
    .replace(/\b(?:fee|fees|commission)[:=\s]+\d+(?:\.\d+)?/gi, " ")
    .replace(/[,$]/g, " ")
    .replace(/->|@|x/gi, " ");
  const numbers = (numericText.match(/\b\d+(?:\.\d+)?\b/g) ?? []).map(Number);
  const entryPrice = Number(entryMatch?.[1] ?? numbers[0]);
  const hasInlineExit = Boolean(exitMatch?.[1]) || /->/.test(text);
  const exitPrice = hasInlineExit && numbers[1] ? Number(exitMatch?.[1] ?? numbers[1]) : null;
  const quantity = Number(qtyMatch?.[1] ?? (exitPrice === null ? numbers[1] : numbers[2]));
  const fees = Number(feesMatch?.[1] ?? 0);
  const strategy = labeledValue(text, ["strategy", "strat", "system"]);
  const setup = labeledValue(text, ["setup", "playbook", "pattern"]);
  const emotion = labeledValue(text, ["state", "emotion", "mood"]) || "focused";
  const notes = labeledValue(text, ["notes", "note", "why"]) || text;

  if (!symbol || !entryPrice || !quantity) return null;

  return {
    symbol,
    side,
    entryDate: date,
    entryPrice,
    exitPrice,
    quantity,
    fees,
    strategy,
    setup,
    emotion: emotion.toLowerCase(),
    notes
  };
}

function labeledValue(text: string, labels: string[]) {
  const labelPattern = labels.join("|");
  const stopWords = "strategy|strat|system|setup|playbook|pattern|state|emotion|mood|notes|note|why|fee|fees|commission";
  const match = text.match(
    new RegExp(`\\b(?:${labelPattern})[:=\\s]+(.+?)(?=\\s+(?:${stopWords})[:=\\s]+|$)`, "i")
  );
  return match?.[1]?.trim().replace(/[.;|]+$/, "") ?? "";
}

function buildGraphModel(
  state: WorkspaceState,
  sourceSignals: SourceStrategySignal[],
  strategyStats: StrategyStat[]
): GraphModel {
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

  strategyStats.forEach((stat) => {
    addGraphNode(nodes, {
      id: graphId("strategy", stat.name),
      label: stat.name,
      type: "strategy",
      detail:
        `${formatCurrency(stat.totalPnl)} across ${stat.count} trades; ` +
        `${stat.sourceCount} source(s), ${stat.winRate}% win rate.`,
      weight: Math.max(1, stat.count + stat.sourceCount),
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
    const sourceSignal = sourceSignals.find((signal) => signal.sourceId === item.id);
    addGraphNode(nodes, {
      id: sourceId,
      label: item.title,
      type: "source",
      detail:
        `${item.kind} from ${item.source || "local upload"}. ${item.body.slice(0, 220)}` +
        (item.learningSummary
          ? ` Learned ${item.learningSummary.chunk_count} chunks into ${item.learningSummary.node_count} nodes.`
          : ""),
      weight: Math.max(1, item.learningSummary?.node_count ?? 1)
    });
    addGraphEdge(edges, edgeIds, memoryId, sourceId, "source");

    if (
      strategyInfo ||
      item.kind === "strategy" ||
      item.tags.some((tag) => tag.toLowerCase().includes("strategy"))
    ) {
      const strategyName = sourceSignal?.strategyName || strategyInfo?.name || item.title;
      const strategyId = graphId("strategy", strategyName);
      addGraphNode(nodes, {
        id: strategyId,
        label: strategyName,
        type: "strategy",
        detail: strategyInfo?.summary || "Strategy research captured in the vault.",
        weight: Math.max(1, sourceSignal?.confidence ? sourceSignal.confidence * 2 : 1)
      });
      addGraphEdge(edges, edgeIds, sourceId, strategyId, strategyInfo ? "strategy info" : "strategy note");

      if (sourceSignal?.setup || strategyInfo?.setup) {
        const setup = sourceSignal?.setup || strategyInfo?.setup || "";
        const setupId = graphId("setup", setup);
        addGraphNode(nodes, {
          id: setupId,
          label: setup,
          type: "setup",
          detail: "Generated setup from imported strategy information.",
          weight: 1
        });
        addGraphEdge(edges, edgeIds, strategyId, setupId, "setup");
      }

      [
        ...(sourceSignal?.attributes ?? []),
        strategyInfo?.market,
        strategyInfo?.timeframe,
        ...(strategyInfo?.indicators ?? [])
      ]
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
  const layout: Record<
    GraphNodeType,
    { x: number; y: number; columns: number; colGap: number; rowGap: number }
  > = {
    memory: { x: graphCanvasWidth / 2, y: graphCanvasHeight / 2, columns: 1, colGap: 0, rowGap: 0 },
    source: { x: 134, y: 190, columns: 2, colGap: 104, rowGap: 54 },
    strategy: { x: 395, y: 190, columns: 2, colGap: 98, rowGap: 54 },
    setup: { x: 665, y: 190, columns: 2, colGap: 98, rowGap: 54 },
    trade: { x: 930, y: 190, columns: 3, colGap: 60, rowGap: 52 },
    journal: { x: 134, y: 480, columns: 2, colGap: 104, rowGap: 46 },
    tag: { x: 395, y: 480, columns: 3, colGap: 62, rowGap: 42 },
    emotion: { x: 665, y: 480, columns: 2, colGap: 98, rowGap: 46 },
    symbol: { x: 930, y: 480, columns: 2, colGap: 82, rowGap: 46 }
  };
  const types: GraphNodeType[] = [
    "memory",
    "source",
    "strategy",
    "setup",
    "trade",
    "journal",
    "tag",
    "emotion",
    "symbol"
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
      return { ...node, x: layout.memory.x, y: layout.memory.y };
    }

    const nodeOrder = order.get(node.id) ?? { index: 0, total: 1 };
    const nodeLayout = layout[node.type];
    const columns = Math.max(1, Math.min(nodeLayout.columns, nodeOrder.total));
    const rows = Math.ceil(nodeOrder.total / columns);
    const row = Math.floor(nodeOrder.index / columns);
    const column = nodeOrder.index % columns;
    const rowGap = Math.max(34, nodeLayout.rowGap - Math.max(0, rows - 3) * 3);
    const columnOffset = (column - (columns - 1) / 2) * nodeLayout.colGap;
    const rowOffset = (row - (rows - 1) / 2) * rowGap;
    const stagger = rows > 2 && column % 2 === 1 ? rowGap * 0.24 : 0;

    return {
      ...node,
      x: nodeLayout.x + columnOffset,
      y: nodeLayout.y + rowOffset + stagger
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

function graphEdgePath(from: PositionedGraphNode, to: PositionedGraphNode) {
  const dx = to.x - from.x;
  const curve = Math.max(42, Math.min(180, Math.abs(dx) * 0.42));
  const direction = dx >= 0 ? 1 : -1;
  const c1x = from.x + curve * direction;
  const c2x = to.x - curve * direction;
  return `M ${from.x} ${from.y} C ${c1x} ${from.y}, ${c2x} ${to.y}, ${to.x} ${to.y}`;
}

function graphLabelVisible(
  node: GraphNode,
  selected: boolean,
  focused: boolean,
  focusMode: boolean
) {
  if (selected) return true;
  if (focusMode) return focused && node.type !== "tag";
  if (node.type === "memory" || node.type === "strategy") return true;
  if (node.type === "source" || node.type === "setup") return node.weight > 1;
  return false;
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
  const topStrategy = buildStrategyStats({ vault: [], journal: [], trades }, [])[0];
  if (!topStrategy) return "-";
  return `${topStrategy.name} ${formatCurrency(topStrategy.totalPnl)}`;
}
