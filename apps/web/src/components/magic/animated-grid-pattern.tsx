import { cn } from "@/lib/utils";

type AnimatedGridPatternProps = {
  className?: string;
};

export function AnimatedGridPattern({ className }: AnimatedGridPatternProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute inset-0 overflow-hidden opacity-60",
        className
      )}
    >
      <div className="absolute inset-0 bg-[linear-gradient(to_right,hsl(var(--line)/0.42)_1px,transparent_1px),linear-gradient(to_bottom,hsl(var(--line)/0.42)_1px,transparent_1px)] bg-[size:44px_44px] motion-safe:animate-grid-pan" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,hsl(var(--signal)/0.16),transparent_46%),linear-gradient(180deg,hsl(var(--card)/0.2),hsl(var(--background)))]" />
    </div>
  );
}
