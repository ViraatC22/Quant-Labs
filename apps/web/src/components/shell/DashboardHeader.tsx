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
      <div className="relative mx-auto flex max-w-7xl flex-col gap-4 px-4 py-6 md:flex-row md:items-center md:justify-between">
        <Reveal className="min-w-0" delay={0.02}>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">Quant Labs</Badge>
            <Badge variant="success">Local-first</Badge>
          </div>
          <h1 className="mt-3 text-2xl font-semibold tracking-normal text-foreground md:text-3xl">
            Trading Intelligence OS
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Your trading memory: research, journal, trades, and paper experiments in one place.
          </p>
        </Reveal>

        <Reveal className="flex shrink-0 items-center gap-3" delay={0.08}>
          <StatusPill status={status} />
          <ThemeToggle />
        </Reveal>
      </div>
    </header>
  );
}
