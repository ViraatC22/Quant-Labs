import { Activity, BrainCircuit, DatabaseZap } from "lucide-react";

import { AnimatedGridPattern } from "@/components/magic/animated-grid-pattern";
import { Reveal } from "@/components/magic/reveal";
import { StatusPill } from "@/components/StatusPill";
import { Badge } from "@/components/ui/badge";
import { ThemeToggle } from "@/components/shell/ThemeToggle";

type DashboardHeaderProps = {
  status: "online" | "offline";
};

export function DashboardHeader({ status }: DashboardHeaderProps) {
  return (
    <header className="relative overflow-hidden border-b bg-card text-card-foreground">
      <AnimatedGridPattern />
      <div className="relative mx-auto flex max-w-7xl flex-col gap-5 px-4 py-6 md:flex-row md:items-center md:justify-between">
        <Reveal className="min-w-0" delay={0.02}>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">Quant Labs</Badge>
            <Badge variant="success">Local Memory</Badge>
          </div>
          <h1 className="mt-3 text-2xl font-semibold tracking-normal text-foreground md:text-3xl">
            Trading Intelligence OS
          </h1>
          <div className="mt-4 flex flex-wrap gap-2">
            <Badge className="gap-1.5" variant="secondary">
              <DatabaseZap aria-hidden="true" size={14} />
              Vault
            </Badge>
            <Badge className="gap-1.5" variant="secondary">
              <Activity aria-hidden="true" size={14} />
              Trades
            </Badge>
            <Badge className="gap-1.5" variant="secondary">
              <BrainCircuit aria-hidden="true" size={14} />
              Insights
            </Badge>
          </div>
        </Reveal>

        <Reveal className="flex shrink-0 items-center gap-3" delay={0.08}>
          <StatusPill status={status} />
          <ThemeToggle />
        </Reveal>
      </div>
    </header>
  );
}
