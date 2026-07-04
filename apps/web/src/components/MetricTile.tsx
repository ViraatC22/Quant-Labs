import type { ReactNode } from "react";

type MetricTileProps = {
  label: string;
  value: string;
  detail: string;
  icon: ReactNode;
};

export function MetricTile({ label, value, detail, icon }: MetricTileProps) {
  return (
    <section className="rounded-lg border border-line bg-white/82 p-4 shadow-panel">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink/55">{label}</p>
          <p className="mt-3 text-3xl font-semibold leading-none text-ink">{value}</p>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-md border border-line bg-paper text-signal">
          {icon}
        </div>
      </div>
      <p className="mt-4 text-sm text-ink/62">{detail}</p>
    </section>
  );
}
