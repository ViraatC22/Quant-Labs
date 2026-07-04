type StatusPillProps = {
  status: "online" | "offline";
};

export function StatusPill({ status }: StatusPillProps) {
  const online = status === "online";

  return (
    <span
      className={[
        "inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium",
        online
          ? "border-moss/25 bg-moss/10 text-moss"
          : "border-loss/25 bg-loss/10 text-loss"
      ].join(" ")}
    >
      <span
        className={[
          "h-2.5 w-2.5 rounded-full",
          online ? "bg-moss" : "bg-loss"
        ].join(" ")}
      />
      API {online ? "online" : "offline"}
    </span>
  );
}
