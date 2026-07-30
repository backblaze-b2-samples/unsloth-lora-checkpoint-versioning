"use client";

import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useDeleteRun } from "@/lib/queries";

interface Props {
  runId: string | null;
  runName?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDeleted?: () => void;
}

/**
 * Confirm + delete a run. The delete is scoped server-side to the run's own
 * prefix (`runs/<id>/`) — never a bucket-wide wipe.
 */
export function DeleteRunDialog({ runId, runName, open, onOpenChange, onDeleted }: Props) {
  const del = useDeleteRun();

  const onConfirm = async () => {
    if (!runId) return;
    try {
      await del.mutateAsync(runId);
      toast.success("Run deleted");
      onOpenChange(false);
      onDeleted?.();
    } catch (e) {
      toast.error("Delete failed", {
        description: e instanceof Error ? e.message : "Please try again.",
      });
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete this run?</AlertDialogTitle>
          <AlertDialogDescription>
            {runName ? <strong>{runName}</strong> : "This run"} and all of its
            artifacts on Backblaze B2 (config, per-epoch checkpoints, final
            adapter, metrics) will be permanently removed. This can&apos;t be
            undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={del.isPending}>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm} disabled={del.isPending}>
            {del.isPending ? "Deleting…" : "Delete"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
