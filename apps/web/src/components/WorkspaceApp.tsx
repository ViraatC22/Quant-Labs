"use client";

import {
  Activity,
  BookMarked,
  BrainCircuit,
  CalendarCheck,
  Download,
  FileText,
  GitBranch,
  LineChart,
  Plus,
  Save,
  Search,
  ShieldCheck,
  Trash2,
  Upload
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";

import { MetricTile } from "@/components/MetricTile";

type TabKey = "vault" | "journal" | "trades" | "graph";

type VaultItem = {
  id: string;
  title: string;
  kind: string;
  source: string;
  body: string;
  tags: string[];
  createdAt: string;
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

const storageKey = "quant-labs.workspace.v1";

const tabs: Array<{ key: TabKey; label: string; icon: typeof BookMarked }> = [
  { key: "vault", label: "Vault", icon: BookMarked },
  { key: "journal", label: "Journal", icon: CalendarCheck },
  { key: "trades", label: "Trades", icon: LineChart },
  { key: "graph", label: "Graph", icon: GitBranch }
];

const emptyState: WorkspaceState = {
  vault: [],
  journal: [],
  trades: []
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
      [item.title, item.kind, item.source, item.body, item.tags.join(" ")]
        .join(" ")
        .toLowerCase()
        .includes(needle)
    );
  }, [query, state.vault]);

  const graph = useMemo(() => {
    const strategies = new Set(state.trades.map((trade) => trade.strategy).filter(Boolean));
    const symbols = new Set(state.trades.map((trade) => trade.symbol).filter(Boolean));
    const emotions = new Set([
      ...state.trades.map((trade) => trade.emotion).filter(Boolean),
      ...state.journal.map((entry) => entry.emotion).filter(Boolean)
    ]);
    const tags = new Set([
      ...state.vault.flatMap((item) => item.tags),
      ...state.journal.flatMap((entry) => entry.tags)
    ]);

    return {
      nodes: state.vault.length + state.journal.length + state.trades.length + strategies.size + symbols.size,
      edges: state.trades.length * 2 + state.vault.length + state.journal.length + tags.size,
      strategies,
      symbols,
      emotions,
      tags
    };
  }, [state]);

  function addVaultItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const title = String(form.get("title") ?? "").trim();
    const body = String(form.get("body") ?? "").trim();
    if (!title || !body) return;

    const item: VaultItem = {
      id: newId(),
      title,
      kind: String(form.get("kind") ?? "note"),
      source: String(form.get("source") ?? "").trim(),
      body,
      tags: splitTags(String(form.get("tags") ?? "")),
      createdAt: new Date().toISOString()
    };

    setState((current) => ({ ...current, vault: [item, ...current.vault] }));
    event.currentTarget.reset();
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
              <form
                className="rounded-lg border border-line bg-white/86 p-4 shadow-panel"
                onSubmit={addVaultItem}
              >
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold text-ink">Vault Capture</h2>
                  <Save aria-hidden="true" className="text-signal" size={20} strokeWidth={2.1} />
                </div>
                <div className="mt-4 grid gap-3">
                  <Field label="Title">
                    <input className={textInputClass()} name="title" required />
                  </Field>
                  <Field label="Type">
                    <select className={textInputClass()} name="kind">
                      <option value="note">Note</option>
                      <option value="article">Article</option>
                      <option value="strategy">Strategy</option>
                      <option value="screenshot">Screenshot</option>
                      <option value="broker_import">Broker Import</option>
                    </select>
                  </Field>
                  <Field label="Source">
                    <input className={textInputClass()} name="source" placeholder="URL or origin" />
                  </Field>
                  <Field label="Tags">
                    <input className={textInputClass()} name="tags" placeholder="orb, vwap, mistake" />
                  </Field>
                  <Field label="Body">
                    <textarea className={textareaClass()} name="body" required />
                  </Field>
                  <button
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-ink px-3 text-sm font-semibold text-white transition hover:bg-ink/88"
                    type="submit"
                  >
                    <Plus aria-hidden="true" size={17} strokeWidth={2.3} />
                    Add to vault
                  </button>
                </div>
              </form>

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
                  {filteredVault.map((item) => (
                    <article key={item.id} className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-sm font-semibold text-ink">{item.title}</h3>
                            <span className="rounded-md bg-signal/10 px-2 py-1 text-xs font-medium text-signal">
                              {item.kind}
                            </span>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-ink/68">{item.body}</p>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {item.source && tagChip(item.source)}
                            {item.tags.map(tagChip)}
                          </div>
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
                  ))}
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

          {activeTab === "graph" && (
            <section className="grid gap-4 xl:grid-cols-[1fr_360px]">
              <section className="rounded-lg border border-line bg-white/86 p-4 shadow-panel">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-ink">Strategy Graph</h2>
                    <p className="mt-1 text-sm text-ink/58">
                      {graph.nodes} nodes / {graph.edges} edges
                    </p>
                  </div>
                  <GitBranch aria-hidden="true" className="text-signal" size={21} strokeWidth={2.1} />
                </div>
                <div className="mt-5 grid gap-3 md:grid-cols-2">
                  <GraphGroup label="Strategies" values={Array.from(graph.strategies)} />
                  <GraphGroup label="Symbols" values={Array.from(graph.symbols)} />
                  <GraphGroup label="Emotions" values={Array.from(graph.emotions)} />
                  <GraphGroup label="Tags" values={Array.from(graph.tags)} />
                </div>
              </section>

              <section className="rounded-lg border border-line bg-white/86 p-4 shadow-panel">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold text-ink">Evidence</h2>
                  <ShieldCheck aria-hidden="true" className="text-moss" size={20} strokeWidth={2.1} />
                </div>
                <div className="mt-4 space-y-3 text-sm text-ink/68">
                  <p>{state.trades.length} trades connected to symbols, strategy labels, and states.</p>
                  <p>{state.vault.length} vault records connected to source tags.</p>
                  <p>{state.journal.length} journal entries connected to routines and states.</p>
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

function GraphGroup({ label, values }: { label: string; values: string[] }) {
  return (
    <section className="min-h-36 rounded-lg border border-line bg-paper/55 p-4">
      <h3 className="text-sm font-semibold text-ink">{label}</h3>
      <div className="mt-3 flex flex-wrap gap-2">
        {values.length ? values.map(tagChip) : <span className="text-sm text-ink/48">Empty</span>}
      </div>
    </section>
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

function bestTradeLabel(trades: TradeEntry[]) {
  if (!trades.length) return "-";
  const trade = [...trades].sort((a, b) => tradePnl(b) - tradePnl(a))[0];
  return `${trade.symbol} ${formatCurrency(tradePnl(trade))}`;
}

function worstTradeLabel(trades: TradeEntry[]) {
  if (!trades.length) return "-";
  const trade = [...trades].sort((a, b) => tradePnl(a) - tradePnl(b))[0];
  return `${trade.symbol} ${formatCurrency(tradePnl(trade))}`;
}

function topStrategyLabel(trades: TradeEntry[]) {
  const counts = trades.reduce<Record<string, number>>((acc, trade) => {
    const key = trade.strategy || "Untitled";
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});
  const [strategy] = Object.entries(counts).sort((a, b) => b[1] - a[1])[0] ?? [];
  return strategy ?? "-";
}
