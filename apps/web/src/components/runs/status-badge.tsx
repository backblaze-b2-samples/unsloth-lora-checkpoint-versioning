import { Badge } from "@/components/ui/badge";
import type { RunStatus } from "@unsloth-lora-checkpoint-versioning/shared";

const VARIANT: Record<RunStatus, "default" | "secondary" | "outline" | "destructive"> = {
  queued: "outline",
  running: "secondary",
  completed: "default",
  failed: "destructive",
};

export function StatusBadge({ status }: { status: RunStatus }) {
  return (
    <Badge variant={VARIANT[status]} className="text-[11px] capitalize">
      {status === "running" && (
        <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
      )}
      {status}
    </Badge>
  );
}
