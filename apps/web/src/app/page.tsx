import { StatusPill } from "@/components/StatusPill";
import { WorkspaceApp } from "@/components/WorkspaceApp";

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
          </div>
        </div>
      </header>

      <WorkspaceApp />
    </main>
  );
}
