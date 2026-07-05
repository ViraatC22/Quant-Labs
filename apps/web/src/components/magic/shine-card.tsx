import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type ShineCardProps = {
  children: ReactNode;
  className?: string;
};

export function ShineCard({ children, className }: ShineCardProps) {
  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-lg border bg-card/86 text-card-foreground shadow-panel",
        "before:absolute before:inset-x-0 before:top-0 before:h-px before:bg-[linear-gradient(90deg,transparent,hsl(var(--signal)/0.68),transparent)] before:bg-[length:200%_100%] before:motion-safe:animate-shine",
        className
      )}
    >
      {children}
    </section>
  );
}
