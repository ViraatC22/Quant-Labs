import { BookOpen, FlaskConical, GitBranch, LineChart, Settings, ShieldCheck } from "lucide-react";

const navItems = [
  { label: "Vault", icon: BookOpen, active: true },
  { label: "Journal", icon: LineChart, active: false },
  { label: "Graph", icon: GitBranch, active: false },
  { label: "Paper Lab", icon: FlaskConical, active: false },
  { label: "Safety", icon: ShieldCheck, active: false },
  { label: "Settings", icon: Settings, active: false }
];

export function WorkspaceNav() {
  return (
    <nav className="flex gap-2 overflow-x-auto border-b border-line bg-white/78 px-4 py-3 backdrop-blur">
      {navItems.map((item) => {
        const Icon = item.icon;

        return (
          <button
            key={item.label}
            className={[
              "inline-flex min-h-10 items-center gap-2 rounded-md border px-3 text-sm font-medium transition",
              item.active
                ? "border-signal/30 bg-signal/10 text-signal"
                : "border-transparent text-ink/62 hover:border-line hover:bg-paper"
            ].join(" ")}
            type="button"
            title={item.label}
          >
            <Icon aria-hidden="true" size={17} strokeWidth={2.2} />
            {item.label}
          </button>
        );
      })}
    </nav>
  );
}
