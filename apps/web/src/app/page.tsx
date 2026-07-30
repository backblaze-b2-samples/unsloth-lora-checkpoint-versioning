import Link from "next/link";
import { FlaskConical } from "lucide-react";

import { Button } from "@/components/ui/button";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { RecentRunsTable } from "@/components/dashboard/recent-runs-table";
import { ArtifactGrowthChart } from "@/components/dashboard/artifact-growth-chart";

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1.5">
            Fine-tuning runs and the artifacts they version on Backblaze B2 —
            growing with every experiment.
          </p>
        </div>
        <Button asChild size="sm" className="h-8">
          <Link href="/runs/new">
            <FlaskConical className="h-3.5 w-3.5" />
            New run
          </Link>
        </Button>
      </div>
      <StatsCards />
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="animate-fade-in-up stagger-3">
          <ArtifactGrowthChart />
        </div>
        <div className="animate-fade-in-up stagger-4">
          <RecentRunsTable />
        </div>
      </div>
    </div>
  );
}
