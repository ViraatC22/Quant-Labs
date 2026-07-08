import { WorkspaceApp } from "@/components/WorkspaceApp";

export const dynamic = "force-dynamic";

// The header's API status is now driven live by the client (WorkspaceApp polls
// health and replays the offline queue), so it no longer needs a stale
// server-render-time snapshot here.
export default function Home() {
  return (
    <main className="min-h-screen">
      <WorkspaceApp />
    </main>
  );
}
