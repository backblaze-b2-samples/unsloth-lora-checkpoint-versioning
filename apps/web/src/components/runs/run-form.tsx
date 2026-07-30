"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { FlaskConical } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useCreateRun, useRunOptions } from "@/lib/queries";
import type { TrainingMethod } from "@unsloth-lora-checkpoint-versioning/shared";

const METHODS: { value: TrainingMethod; label: string; hint: string }[] = [
  { value: "LoRA", label: "LoRA", hint: "Low-rank adapters on the base weights." },
  { value: "QLoRA", label: "QLoRA", hint: "LoRA on a 4-bit quantized base (CUDA only)." },
];

const parseList = (s: string): string[] =>
  s.split(",").map((v) => v.trim()).filter(Boolean);

const lrLabel = (lr: number) => lr.toExponential(0).replace("e-", "e-");

const schema = z.object({
  name: z.string().min(1, "Name is required").max(100),
  notes: z.string().max(1000).optional(),
  tags: z.string().optional(),
  base_model: z.string().min(1),
  dataset_id: z.string().min(1, "Pick a dataset (or upload one first)"),
  method: z.enum(["LoRA", "QLoRA"]),
  epochs: z.coerce.number().int().min(1).max(5),
  learning_rate: z.string().min(1),
  lora_rank: z.string().min(1),
});

type Values = z.infer<typeof schema>;

export function RunCreateForm() {
  const router = useRouter();
  const { data: options, isLoading, error, refetch } = useRunOptions();
  const create = useCreateRun();

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      notes: "",
      tags: "",
      base_model: "tiny",
      dataset_id: "",
      method: "LoRA",
      epochs: 1,
      learning_rate: "0.0002",
      lora_rank: "16",
    },
  });

  // Seed the dataset selector with the safe default once options arrive.
  useEffect(() => {
    if (options?.default_dataset_id && !form.getValues("dataset_id")) {
      form.setValue("dataset_id", options.default_dataset_id);
    }
  }, [options, form]);

  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;

  // The base-model and dataset option lists are server-sourced, so they are
  // empty until `options` resolves. Radix <SelectValue> can only mirror a value
  // whose <SelectItem> is already mounted, so we must not render these two
  // Selects with an empty list — the already-set default would paint blank and
  // never backfill. (learning_rate/lora_rank have non-empty local fallbacks, so
  // their default item exists on first paint and they render fine.)
  const optionsReady = !!options;
  const baseModels = options?.base_models ?? [];
  const datasets = options?.datasets ?? [];
  const learningRates = options?.learning_rates ?? [0.0001, 0.0002, 0.0005];
  const loraRanks = options?.lora_ranks ?? [8, 16, 32, 64];
  const noDatasets = !isLoading && datasets.length === 0;

  const onSubmit = async (values: Values) => {
    try {
      const detail = await create.mutateAsync({
        name: values.name,
        notes: values.notes ?? "",
        tags: parseList(values.tags ?? ""),
        config: {
          base_model: values.base_model,
          dataset_id: values.dataset_id,
          method: values.method,
          epochs: values.epochs,
          learning_rate: Number(values.learning_rate),
          lora_rank: Number(values.lora_rank),
        },
      });
      toast.success("Run created", {
        description: "Open it and press Start training to launch the fine-tune.",
      });
      router.push(`/runs/${detail.id}`);
    } catch (e) {
      toast.error("Could not create run", {
        description: e instanceof Error ? e.message : "Please try again.",
      });
    }
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Experiment</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 p-5">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. llama32-support-tone-v1" {...field} />
                  </FormControl>
                  <FormDescription>A short label for this run.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="notes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Notes</FormLabel>
                  <FormControl>
                    <Textarea placeholder="What are you testing?" className="resize-none" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="tags"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Tags</FormLabel>
                  <FormControl>
                    <Input placeholder="support, tone" {...field} />
                  </FormControl>
                  <FormDescription>Comma-separated. Optional.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Training configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6 p-5">
            <FormField
              control={form.control}
              name="base_model"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Base model</FormLabel>
                  {optionsReady ? (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {baseModels.map((m) => (
                          <SelectItem key={m.value} value={m.value}>
                            {m.label}
                            {m.requires_gpu ? " · needs GPU" : ""}
                            {m.gated ? " · gated" : ""}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Skeleton className="h-9 w-full rounded-md" />
                  )}
                  <FormDescription>
                    <strong>Tiny (CPU demo)</strong> is the safe default — it
                    needs no GPU and no token. Models marked{" "}
                    <em>· needs GPU</em> are Unsloth 4-bit builds that require a
                    CUDA GPU; the <em>· gated</em> ones (Llama 3.x, Gemma) also
                    need an <code>HF_TOKEN</code> to accept their license.{" "}
                    {options && !options.gpu_available
                      ? "No GPU was detected on this host, so any GPU-only model falls back to the CPU-demo model."
                      : "Unsloth runs them in 4-bit on the GPU."}
                  </FormDescription>
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="dataset_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Dataset</FormLabel>
                  {optionsReady && (noDatasets || field.value) ? (
                    <Select value={field.value} onValueChange={field.onChange} disabled={noDatasets}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select an ingested dataset" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {datasets.map((d) => (
                          <SelectItem key={d.id} value={d.id}>
                            {d.filename}
                            {d.rows !== null ? ` · ${d.rows} rows` : ""}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Skeleton className="h-9 w-full rounded-md" />
                  )}
                  <FormDescription>
                    {noDatasets ? (
                      <>
                        No datasets yet — <Link href="/upload" className="underline">upload a JSONL/CSV</Link>{" "}
                        training file first.
                      </>
                    ) : (
                      "Ingested training files (JSONL/CSV) under the datasets/ prefix. A sample dataset is seeded for you."
                    )}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="method"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Method</FormLabel>
                  <FormControl>
                    <RadioGroup
                      onValueChange={field.onChange}
                      value={field.value}
                      className="grid gap-2 sm:grid-cols-2"
                    >
                      {METHODS.map((m) => (
                        <label
                          key={m.value}
                          className="flex cursor-pointer items-start gap-2 rounded-md border border-border p-3 text-sm"
                        >
                          <RadioGroupItem value={m.value} className="mt-0.5" />
                          <span>
                            <span className="font-medium">{m.label}</span>
                            <span className="block text-xs text-muted-foreground">{m.hint}</span>
                          </span>
                        </label>
                      ))}
                    </RadioGroup>
                  </FormControl>
                  <FormDescription>LoRA is the safe default.</FormDescription>
                </FormItem>
              )}
            />

            <div className="grid gap-4 sm:grid-cols-3">
              <FormField
                control={form.control}
                name="epochs"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Epochs</FormLabel>
                    <FormControl>
                      <Input type="number" min={1} max={5} {...field} />
                    </FormControl>
                    <FormDescription>1–5. Default 1.</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="learning_rate"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Learning rate</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {learningRates.map((lr) => (
                          <SelectItem key={lr} value={String(lr)}>
                            {lrLabel(lr)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormDescription>Default 2e-4.</FormDescription>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="lora_rank"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>LoRA rank</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {loraRanks.map((r) => (
                          <SelectItem key={r} value={String(r)}>
                            {r}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormDescription>Default 16.</FormDescription>
                  </FormItem>
                )}
              />
            </div>
          </CardContent>
        </Card>

        <div className="flex items-center justify-end gap-2">
          <Button type="submit" disabled={create.isPending || isLoading || noDatasets}>
            <FlaskConical className="h-3.5 w-3.5" />
            {create.isPending ? "Creating…" : "Create run"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
