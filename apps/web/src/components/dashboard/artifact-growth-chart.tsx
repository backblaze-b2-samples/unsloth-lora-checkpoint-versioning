"use client";

import { useMemo } from "react";
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { TrendingUp } from "lucide-react";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useRunStats } from "@/lib/queries";

const chartConfig = {
  size_bytes: { label: "Cumulative bytes", color: "var(--chart-1)" },
} satisfies ChartConfig;

function humanizeBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = n / 1024;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[i]}`;
}

/**
 * The headline B2 metric: total artifact bytes accumulating run over run. Each
 * point is one run's bytes added to the running total (ordered by when the run
 * completed), so a same-session sweep renders an ascending curve instead of
 * collapsing to a single per-day dot. `p.date` is the run's full timestamp, so
 * `new Date(...).toLocaleDateString()` yields the run's real local date (no
 * off-by-one from a date-only UTC string). The curve only ever grows as
 * experiments pile up on Backblaze B2.
 */
export function ArtifactGrowthChart() {
  const { data: stats, isLoading, error, refetch } = useRunStats();
  const data = useMemo(
    () =>
      (stats?.cumulative ?? []).map((p) => ({
        date: new Date(p.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
        size_bytes: p.size_bytes,
      })),
    [stats]
  );

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Artifact Storage on B2</CardTitle>
        <CardDescription className="text-xs">Cumulative, run over run</CardDescription>
        <CardAction className="self-center text-right">
          {isLoading ? (
            <Skeleton className="ml-auto h-6 w-16" />
          ) : (
            <>
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Total
              </div>
              <div className="text-lg font-semibold leading-tight tracking-tight tabular-nums">
                {stats?.total_size_human ?? "-"}
              </div>
            </>
          )}
        </CardAction>
      </CardHeader>
      <CardContent className="p-5">
        {isLoading ? (
          <Skeleton className="h-[240px] w-full" />
        ) : error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : data.length === 0 ? (
          <EmptyState
            icon={TrendingUp}
            title="No artifacts yet"
            description="Run a fine-tune to start the accumulating-artifact curve."
          />
        ) : (
          <ChartContainer config={chartConfig} className="h-[240px] w-full">
            <AreaChart data={data} margin={{ top: 8, right: 8, left: -4, bottom: 0 }}>
              <defs>
                <linearGradient id="size-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--color-size_bytes)" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="var(--color-size_bytes)" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tickLine={false} axisLine={false} tickMargin={10} fontSize={11} />
              <YAxis
                tickLine={false}
                axisLine={false}
                tickMargin={6}
                fontSize={11}
                width={52}
                tickFormatter={(v: number) => humanizeBytes(v)}
              />
              <ChartTooltip
                cursor={{ stroke: "var(--border)" }}
                content={<ChartTooltipContent />}
              />
              <Area
                type="monotone"
                dataKey="size_bytes"
                stroke="var(--color-size_bytes)"
                strokeWidth={2}
                fill="url(#size-fill)"
                animationDuration={500}
              />
            </AreaChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
