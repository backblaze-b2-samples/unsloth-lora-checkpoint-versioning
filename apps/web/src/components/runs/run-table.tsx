"use client";

import { useState } from "react";
import Link from "next/link";
import { FlaskConical, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { useRuns } from "@/lib/queries";
import { formatDate } from "@/lib/utils";
import { StatusBadge } from "./status-badge";
import { DeleteRunDialog } from "./delete-run-dialog";

/**
 * The Runs list — a sample-scoped experiment log. Lists every run under the
 * app's own `runs/` B2 prefix (not the whole bucket; that's the Files view).
 */
export function RunTable() {
  const { data: runs = [], isLoading, error, refetch } = useRuns();
  const [target, setTarget] = useState<{ id: string; name: string } | null>(null);

  return (
    <Card>
      <CardContent className="p-0">
        {isLoading ? (
          <div className="space-y-3 p-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : runs.length === 0 ? (
          <EmptyState
            icon={FlaskConical}
            title="No runs yet"
            description="Configure your first fine-tuning run — its checkpoints and adapter land on Backblaze B2 as it trains."
            action={
              <Button asChild size="sm">
                <Link href="/runs/new">New run</Link>
              </Button>
            }
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/40 hover:bg-muted/40">
                {["Name", "Status", "Base model", "Method", "Epochs", "Final loss", "Artifacts", "Size", "Created"].map(
                  (h) => (
                    <TableHead
                      key={h}
                      className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                    >
                      {h}
                    </TableHead>
                  )
                )}
                <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Actions
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map((r) => (
                <TableRow key={r.id} className="table-row-hover">
                  <TableCell className="font-medium">
                    <Link
                      href={`/runs/${r.id}`}
                      className="rounded-sm underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                    >
                      {r.name}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={r.status} />
                  </TableCell>
                  <TableCell className="whitespace-nowrap font-mono text-xs text-muted-foreground">
                    {r.base_model}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="font-mono text-[11px]">
                      {r.method}
                    </Badge>
                  </TableCell>
                  <TableCell className="tabular-nums">{r.epochs}</TableCell>
                  <TableCell className="font-mono text-xs tabular-nums text-muted-foreground">
                    {r.final_loss === null ? "—" : r.final_loss.toFixed(4)}
                  </TableCell>
                  <TableCell className="tabular-nums">{r.artifact_count}</TableCell>
                  <TableCell className="whitespace-nowrap font-mono text-xs tabular-nums text-muted-foreground">
                    {r.size_human}
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-muted-foreground">
                    {formatDate(r.created_at)}
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      aria-label="Delete"
                      onClick={() => setTarget({ id: r.id, name: r.name })}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
      <DeleteRunDialog
        runId={target?.id ?? null}
        runName={target?.name}
        open={target !== null}
        onOpenChange={(open) => !open && setTarget(null)}
      />
    </Card>
  );
}
