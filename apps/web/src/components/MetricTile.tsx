import type { ReactNode } from "react";

import { ShineCard } from "@/components/magic/shine-card";

type MetricTileProps = {
  label: string;
  value: string;
  detail: string;
  icon: ReactNode;
};

export function MetricTile({ label, value, detail, icon }: MetricTileProps) {
  return (
    <ShineCard className="bg-card/82 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
          <p className="mt-3 text-3xl font-semibold leading-none text-foreground">{value}</p>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-md border bg-secondary text-primary">
          {icon}
        </div>
      </div>
      <p className="mt-4 text-sm text-muted-foreground">{detail}</p>
    </ShineCard>
  );
}
