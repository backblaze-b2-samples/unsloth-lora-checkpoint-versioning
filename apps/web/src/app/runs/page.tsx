import Link from "next/link";
import { FlaskConical } from "lucide-react";

import { Button } from "@/components/ui/button";
import { RunTable } from "@/components/runs/run-table";

export default function RunsPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
        <div className="min-w-0">
          <h1 className="page-title">Runs</h1>
          <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
            Every LoRA/QLoRA fine-tuning experiment — its frozen config,
            per-epoch checkpoints, and final adapter versioned on Backblaze B2.
          </p>
        </div>
        <Button asChild size="sm" className="h-8 shrink-0">
          <Link href="/runs/new">
            <FlaskConical aria-hidden="true" className="h-3.5 w-3.5" />
            New run
          </Link>
        </Button>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <RunTable />
      </div>
    </div>
  );
}
