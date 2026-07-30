import { RunDetail } from "@/components/runs/run-detail";

export default async function RunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="space-y-8">
      <RunDetail runId={id} />
    </div>
  );
}
