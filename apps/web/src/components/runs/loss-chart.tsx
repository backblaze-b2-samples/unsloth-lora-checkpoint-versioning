"use client";

import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import { LineChart as LineChartIcon } from "lucide-react";

import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { EmptyState } from "@/components/ui/empty-state";
import type { EpochMetric } from "@unsloth-lora-checkpoint-versioning/shared";

const chartConfig = {
  loss: { label: "Training loss", color: "var(--chart-1)" },
} satisfies ChartConfig;

export function LossChart({ metrics }: { metrics: EpochMetric[] }) {
  if (metrics.length === 0) {
    return (
      <EmptyState
        icon={LineChartIcon}
        title="No metrics yet"
        description="The loss curve fills in as each epoch completes."
      />
    );
  }

  const data = metrics.map((m) => ({ epoch: `Epoch ${m.epoch}`, loss: m.loss }));

  return (
    <ChartContainer config={chartConfig} className="h-[240px] w-full">
      <LineChart data={data} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
        <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="epoch" tickLine={false} axisLine={false} tickMargin={10} fontSize={11} />
        <YAxis
          tickLine={false}
          axisLine={false}
          tickMargin={6}
          fontSize={11}
          width={44}
          domain={["auto", "auto"]}
          tickFormatter={(v: number) => v.toFixed(2)}
        />
        <ChartTooltip cursor={{ stroke: "var(--border)" }} content={<ChartTooltipContent />} />
        <Line
          type="monotone"
          dataKey="loss"
          stroke="var(--color-loss)"
          strokeWidth={2}
          dot={{ r: 3 }}
          animationDuration={400}
        />
      </LineChart>
    </ChartContainer>
  );
}
