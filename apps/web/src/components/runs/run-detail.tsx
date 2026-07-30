"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { AlertTriangle, Cpu, Download, Play, RotateCcw, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useRun, useStartRun } from "@/lib/queries";
import type { RunDetail as RunDetailData } from "@unsloth-lora-checkpoint-versioning/shared";
import { StatusBadge } from "./status-badge";
import { LossChart } from "./loss-chart";
import { EditRunDialog } from "./edit-run-dialog";
import { DeleteRunDialog } from "./delete-run-dialog";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="mt-0.5 text-sm font-medium tabular-nums">{value}</div>
    </div>
  );
}

function StartButton({ run }: { run: RunDetailData }) {
  const start = useStartRun(run.id);
  const isRunning = run.status === "running";
  const isReRun = run.status === "completed" || run.status === "failed";

  const onClick = async () => {
    try {
      await start.mutateAsync();
      toast.success(isReRun ? "Re-running" : "Training started", {
        description: "Checkpoints are versioned to Backblaze B2 as each epoch completes.",
      });
    } catch (e) {
      toast.error("Could not start", {
        description: e instanceof Error ? e.message : "Please try again.",
      });
    }
  };

  return (
    <Button size="sm" onClick={onClick} disabled={isRunning || start.isPending}>
      {isReRun ? <RotateCcw className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
      {isRunning ? "Training…" : isReRun ? "Re-run" : "Start training"}
    </Button>
  );
}

export function RunDetail({ runId }: { runId: string }) {
  const router = useRouter();
  const { data, isLoading, error, refetch } = useRun(runId);
  const [deleteOpen, setDeleteOpen] = useState(false);

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (error)
    return (
      <ErrorState
        error={error}
        onRetry={() => refetch()}
        title={error.isNotFound ? "Run not found" : undefined}
      />
    );
  if (!data) return <EmptyState title="Run not found" />;

  const lrLabel = data.config.learning_rate.toExponential(0);
  const progressPct = data.progress
    ? Math.min(100, Math.round((data.progress.current_epoch / Math.max(1, data.progress.total_epochs)) * 100))
    : 0;
  // A GPU-only model was requested but the run trained the tiny CPU-demo model
  // (no CUDA on this host). `base_model_resolved`/`device` come straight from
  // the manifest; disclose it so the run isn't read as a real fine-tune of the
  // requested model. `base_model` === "tiny" is the only non-GPU option, so a
  // non-tiny request that ran on CPU is always the fallback.
  const ranCpuFallback =
    data.device === "cpu" &&
    data.config.base_model !== "tiny" &&
    !!data.base_model_resolved &&
    data.base_model_resolved !== data.config.base_model;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-5">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="page-title">{data.name}</h1>
            <StatusBadge status={data.status} />
          </div>
          {data.notes && (
            <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">{data.notes}</p>
          )}
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge variant="secondary" className="font-mono text-[11px]">
              {data.config.method}
            </Badge>
            {data.tags.map((t) => (
              <Badge key={t} variant="outline" className="text-[11px]">
                {t}
              </Badge>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StartButton run={data} />
          <EditRunDialog run={data} />
          <Button variant="outline" size="sm" onClick={() => setDeleteOpen(true)}>
            <Trash2 className="h-3.5 w-3.5" />
            Delete
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="grid grid-cols-2 gap-4 p-5 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Base model" value={data.config.base_model} />
          <Stat label="Dataset" value={data.config.dataset_id} />
          <Stat label="Epochs" value={data.config.epochs} />
          <Stat label="Learning rate" value={lrLabel} />
          <Stat label="LoRA rank" value={data.config.lora_rank} />
          <Stat label="Device" value={data.device || "—"} />
        </CardContent>
      </Card>

      {ranCpuFallback && (
        <Card className="border-border bg-muted/40">
          <CardContent className="flex items-start gap-3 p-4 text-sm">
            <Cpu className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
            <div>
              <div className="font-medium">Ran on CPU-demo fallback (tiny model)</div>
              <p className="mt-1 text-xs text-muted-foreground">
                No CUDA GPU was available, so{" "}
                <code className="font-mono">{data.config.base_model}</code> was not
                loaded. This run trained the portable CPU-demo model{" "}
                (<code className="break-all font-mono">{data.base_model_resolved}</code>)
                instead — its loss and adapter reflect that tiny model, not a real
                fine-tune of the requested model.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {data.status === "running" && data.progress && (
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Training progress</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 p-5">
            <Progress value={progressPct} />
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>{data.progress.message || `Epoch ${data.progress.current_epoch}/${data.progress.total_epochs}`}</span>
              <span className="font-mono tabular-nums">
                {data.progress.latest_loss !== null
                  ? `loss ${data.progress.latest_loss.toFixed(4)}`
                  : ""}
              </span>
            </div>
          </CardContent>
        </Card>
      )}

      {data.status === "failed" && data.error && (
        <Card className="border-destructive/40">
          <CardContent className="flex items-start gap-3 p-5 text-sm">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
            <div>
              <div className="font-medium text-destructive">Training failed</div>
              <p className="mt-1 font-mono text-xs text-muted-foreground">{data.error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between border-b border-border py-4 px-5">
          <CardTitle className="card-title">Loss curve</CardTitle>
          {data.final_loss !== null && (
            <span className="text-xs text-muted-foreground">
              final loss{" "}
              <span className="font-mono font-medium text-foreground tabular-nums">
                {data.final_loss.toFixed(4)}
              </span>
            </span>
          )}
        </CardHeader>
        <CardContent className="p-5">
          <LossChart metrics={data.epoch_metrics} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between border-b border-border py-4 px-5">
          <CardTitle className="card-title">Versioned artifacts on Backblaze B2</CardTitle>
          <span className="text-xs text-muted-foreground">
            {data.artifact_count} objects · {data.size_human}
          </span>
        </CardHeader>
        <CardContent className="p-0">
          {data.artifacts.length === 0 ? (
            <EmptyState title="No artifacts yet" description="Start training to version checkpoints here." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/40 hover:bg-muted/40">
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Artifact
                  </TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Kind
                  </TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Size
                  </TableHead>
                  <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Download
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.artifacts.map((a) => (
                  <TableRow key={a.key}>
                    <TableCell className="font-mono text-xs">{a.filename}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-[11px]">
                        {a.kind}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs tabular-nums text-muted-foreground">
                      {a.size_human}
                    </TableCell>
                    <TableCell className="text-right">
                      {a.download_url ? (
                        <Button asChild variant="ghost" size="icon" className="h-8 w-8" aria-label={`Download ${a.filename}`}>
                          <a href={a.download_url} target="_blank" rel="noopener noreferrer">
                            <Download className="h-3.5 w-3.5" />
                          </a>
                        </Button>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <DeleteRunDialog
        runId={data.id}
        runName={data.name}
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onDeleted={() => router.push("/runs")}
      />
    </div>
  );
}
