import { Badge } from "@/components/ui/badge";

type StatusPillProps = {
  status: "online" | "offline";
};

export function StatusPill({ status }: StatusPillProps) {
  const online = status === "online";

  return (
    <Badge className="min-h-10 gap-2 px-3" variant={online ? "success" : "destructive"}>
      <span
        className={[
          "h-2.5 w-2.5 rounded-full",
          online ? "bg-moss" : "bg-loss"
        ].join(" ")}
      />
      API {online ? "online" : "offline"}
    </Badge>
  );
}
