import { DashboardHeader } from "@/components/shell/DashboardHeader";
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
      <DashboardHeader status={healthStatus} />
      <WorkspaceApp />
    </main>
  );
}
