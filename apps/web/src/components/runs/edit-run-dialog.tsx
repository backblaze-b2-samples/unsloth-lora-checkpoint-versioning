"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Pencil } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useUpdateRun } from "@/lib/queries";
import type { RunDetail } from "@unsloth-lora-checkpoint-versioning/shared";

const parseList = (s: string): string[] =>
  s.split(",").map((v) => v.trim()).filter(Boolean);

/**
 * Metadata-only edit (name / notes / tags). The training config is immutable
 * once a run has executed — to change hyperparameters, create a new run.
 */
export function EditRunDialog({ run }: { run: RunDetail }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(run.name);
  const [notes, setNotes] = useState(run.notes);
  const [tags, setTags] = useState(run.tags.join(", "));
  const update = useUpdateRun(run.id);

  const onSave = async () => {
    try {
      await update.mutateAsync({ name, notes, tags: parseList(tags) });
      toast.success("Run updated");
      setOpen(false);
    } catch (e) {
      toast.error("Update failed", {
        description: e instanceof Error ? e.message : "Please try again.",
      });
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) {
          // Re-seed from the latest run metadata each time the dialog opens.
          setName(run.name);
          setNotes(run.notes);
          setTags(run.tags.join(", "));
        }
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Pencil className="h-3.5 w-3.5" />
          Edit
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit run metadata</DialogTitle>
          <DialogDescription>
            Update the name, notes, and tags. The training configuration is a
            fixed experiment record and can&apos;t be edited — re-run from a new
            config to change hyperparameters.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="run-name">Name</Label>
            <Input id="run-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="run-notes">Notes</Label>
            <Textarea
              id="run-notes"
              className="resize-none"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="run-tags">Tags</Label>
            <Input
              id="run-tags"
              placeholder="support, tone"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={update.isPending}>
            Cancel
          </Button>
          <Button onClick={onSave} disabled={update.isPending || name.trim().length === 0}>
            {update.isPending ? "Saving…" : "Save changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
