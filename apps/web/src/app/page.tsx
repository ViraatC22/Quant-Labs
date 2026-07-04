import {
  Activity,
  BookMarked,
  BrainCircuit,
  ClipboardCheck,
  DatabaseZap,
  GitBranch,
  Plus,
  ShieldAlert
} from "lucide-react";

import { MetricTile } from "@/components/MetricTile";
import { StatusPill } from "@/components/StatusPill";
import { WorkspaceNav } from "@/components/WorkspaceNav";

export const dynamic = "force-dynamic";

type HealthStatus = "online" | "offline";

async function getHealthStatus(): Promise<HealthStatus> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  try {
    const response = await fetch(`${apiUrl}/health`, { cache: "no-store" });
    return response.ok ? "online" : "offline";
  } catch {
    return "offline";
  }
}

const lanes = [
  { label: "Vault", value: "0", detail: "documents", icon: BookMarked },
  { label: "Trades", value: "0", detail: "records", icon: Activity },
  { label: "Graph", value: "0", detail: "nodes", icon: GitBranch },
  { label: "Memory", value: "0", detail: "chunks", icon: BrainCircuit }
];

const queue = [
  { label: "Source upload", status: "Ready", tone: "text-moss" },
  { label: "CSV import", status: "Queued for Phase 1", tone: "text-caution" },
  { label: "Embeddings", status: "Queued for Phase 2", tone: "text-caution" },
  { label: "Paper autonomy", status: "Locked", tone: "text-loss" }
];

export default async function Home() {
  const healthStatus = await getHealthStatus();

  return (
    <main className="min-h-screen">
      <header className="border-b border-line bg-ink text-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-5 px-4 py-5 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-white/58">
              Quant Labs
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-normal md:text-3xl">
              Trading Intelligence OS
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <StatusPill status={healthStatus} />
            <button
              className="inline-flex min-h-10 items-center gap-2 rounded-md bg-white px-3 text-sm font-semibold text-ink transition hover:bg-paper"
              type="button"
              title="New vault item"
            >
              <Plus aria-hidden="true" size={17} strokeWidth={2.3} />
              New
            </button>
          </div>
        </div>
      </header>

      <WorkspaceNav />

      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[1fr_340px]">
        <section className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {lanes.map((lane) => {
              const Icon = lane.icon;

              return (
                <MetricTile
                  key={lane.label}
                  label={lane.label}
                  value={lane.value}
                  detail={lane.detail}
                  icon={<Icon aria-hidden="true" size={20} strokeWidth={2.1} />}
                />
              );
            })}
          </div>

          <section className="rounded-lg border border-line bg-white/86 shadow-panel">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <div>
                <h2 className="text-base font-semibold text-ink">Learning Vault</h2>
                <p className="mt-1 text-sm text-ink/58">No documents yet</p>
              </div>
              <DatabaseZap aria-hidden="true" className="text-signal" size={21} strokeWidth={2.1} />
            </div>
            <div className="grid min-h-64 place-items-center px-4 py-12 text-center">
              <div className="max-w-sm">
                <BookMarked aria-hidden="true" className="mx-auto text-signal" size={32} />
                <p className="mt-4 text-sm font-medium text-ink/70">Vault is empty</p>
              </div>
            </div>
          </section>
        </section>

        <aside className="space-y-6">
          <section className="rounded-lg border border-line bg-white/86 p-4 shadow-panel">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-ink">Sprint Gate</h2>
              <ClipboardCheck aria-hidden="true" className="text-moss" size={20} strokeWidth={2.1} />
            </div>
            <dl className="mt-4 space-y-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <dt className="text-ink/62">Mode</dt>
                <dd className="font-medium text-ink">Local-first</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-ink/62">Execution</dt>
                <dd className="font-medium text-loss">Paper only</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-ink/62">Auth</dt>
                <dd className="font-medium text-caution">Skeleton</dd>
              </div>
            </dl>
          </section>

          <section className="rounded-lg border border-line bg-white/86 p-4 shadow-panel">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-ink">Pipeline</h2>
              <ShieldAlert aria-hidden="true" className="text-copper" size={20} strokeWidth={2.1} />
            </div>
            <div className="mt-4 divide-y divide-line">
              {queue.map((item) => (
                <div key={item.label} className="flex items-center justify-between gap-3 py-3">
                  <span className="text-sm font-medium text-ink">{item.label}</span>
                  <span className={`text-right text-xs font-semibold ${item.tone}`}>
                    {item.status}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </main>
  );
}
