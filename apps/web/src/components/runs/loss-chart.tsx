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

  // The tiny CPU-demo model nudges the loss by a razor-thin amount (~1e-4 on a
  // ~10 base) while a real GPU run spans whole units. Derive the tick decimals
  // and a small padded domain from the actual band so every tick is distinct
  // and the integer part stays visible — a fixed toFixed(2) at width=44 collapsed
  // every tick to one clipped value.
  const losses = data.map((d) => d.loss);
  const min = Math.min(...losses);
  const max = Math.max(...losses);
  const span = max - min;
  const decimals =
    span > 0 ? Math.min(6, Math.max(2, Math.ceil(-Math.log10(span)) + 1)) : 4;
  const pad = span > 0 ? span * 0.15 : Math.max(Math.abs(max) * 1e-3, 0.01);

  return (
    <ChartContainer config={chartConfig} className="h-[240px] w-full">
      <LineChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
        <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="epoch" tickLine={false} axisLine={false} tickMargin={10} fontSize={11} />
        <YAxis
          tickLine={false}
          axisLine={false}
          tickMargin={6}
          fontSize={11}
          width={68}
          domain={[min - pad, max + pad]}
          tickFormatter={(v: number) => v.toFixed(decimals)}
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
