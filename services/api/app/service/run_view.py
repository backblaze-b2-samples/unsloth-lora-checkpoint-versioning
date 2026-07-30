"""Read-model shaping for the Run entity: summaries, detail, options, stats.

Pure transformation over data already fetched from B2 (via `repo.runs_store`) —
no orchestration, no background work. Kept separate so `service.runs` stays
focused on the run lifecycle and both files stay under the 300-line ceiling.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict

from app.repo import runs_store, trainer
from app.repo.run_progress import get_progress
from app.types.formatting import humanize_bytes
from app.types.runs import (
    BASE_MODELS,
    EPOCHS_MAX,
    EPOCHS_MIN,
    LEARNING_RATE_OPTIONS,
    LORA_RANK_OPTIONS,
    Artifact,
    CumulativePoint,
    DatasetOption,
    RunDetail,
    RunManifest,
    RunOptions,
    RunStats,
    RunStatus,
    RunSummary,
    TrainingMethod,
)


def artifact_kind(filename: str) -> str:
    if filename == "run.json":
        return "manifest"
    if filename == "config.json":
        return "config"
    if filename == "metrics.json":
        return "metrics"
    if filename.startswith("checkpoints/"):
        return "checkpoint"
    if filename.startswith("adapter/"):
        return "adapter"
    return "other"


def build_artifacts(objects: list[dict], *, presign: bool) -> list[Artifact]:
    out: list[Artifact] = []
    for obj in objects:
        size = int(obj["size_bytes"])
        out.append(
            Artifact(
                key=obj["key"],
                filename=obj["filename"],
                kind=artifact_kind(obj["filename"]),
                size_bytes=size,
                size_human=humanize_bytes(size),
                last_modified=obj["last_modified"],
                download_url=(
                    runs_store.presign(obj["key"], filename=obj["filename"].split("/")[-1])
                    if presign
                    else None
                ),
            )
        )
    return out


def build_summary(manifest: RunManifest, objects: list[dict]) -> RunSummary:
    size = sum(int(o["size_bytes"]) for o in objects)
    return RunSummary(
        id=manifest.id,
        name=manifest.name,
        status=manifest.status,
        base_model=manifest.config.base_model,
        dataset_id=manifest.config.dataset_id,
        method=manifest.config.method,
        epochs=manifest.config.epochs,
        final_loss=manifest.final_loss,
        artifact_count=len(objects),
        size_bytes=size,
        size_human=humanize_bytes(size),
        created_at=manifest.created_at,
        updated_at=manifest.updated_at,
    )


def build_detail(manifest: RunManifest, objects: list[dict]) -> RunDetail:
    artifacts = build_artifacts(objects, presign=True)
    size = sum(a.size_bytes for a in artifacts)
    progress = get_progress(manifest.id) if manifest.status == RunStatus.running else None
    return RunDetail(
        id=manifest.id,
        name=manifest.name,
        notes=manifest.notes,
        tags=manifest.tags,
        config=manifest.config,
        status=manifest.status,
        device=manifest.device,
        base_model_resolved=manifest.base_model_resolved,
        epoch_metrics=manifest.epoch_metrics,
        final_loss=manifest.final_loss,
        error=manifest.error,
        progress=progress,
        artifacts=artifacts,
        artifact_count=len(artifacts),
        size_bytes=size,
        size_human=humanize_bytes(size),
        created_at=manifest.created_at,
        updated_at=manifest.updated_at,
        started_at=manifest.started_at,
        completed_at=manifest.completed_at,
    )


def _count_rows(data: bytes, filename: str) -> int | None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if filename.lower().endswith(".csv"):
        rows = list(csv.reader(io.StringIO(text)))
        return max(len(rows) - 1, 0)  # minus header
    return sum(1 for line in text.splitlines() if line.strip())


def list_dataset_options() -> list[DatasetOption]:
    out: list[DatasetOption] = []
    for d in runs_store.list_datasets():
        data = runs_store.get_dataset_bytes(d["id"])
        rows = _count_rows(data, d["filename"]) if data else None
        out.append(
            DatasetOption(
                id=d["id"],
                filename=d["filename"],
                rows=rows,
                size_bytes=d["size_bytes"],
                size_human=humanize_bytes(d["size_bytes"]),
            )
        )
    return out


def parse_examples(data: bytes, filename: str) -> list[str]:
    """Turn a JSONL/CSV training file into a list of text examples.

    Each record's string fields are joined into a single `key: value` block —
    enough signal for a real (if tiny) causal-LM fine-tune without imposing a
    fixed schema on the ingested dataset.
    """
    text = data.decode("utf-8", errors="replace")
    examples: list[str] = []
    if filename.lower().endswith(".csv"):
        for row in csv.DictReader(io.StringIO(text)):
            block = "\n".join(f"{k}: {v}" for k, v in row.items() if v)
            if block:
                examples.append(block)
        return examples
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            examples.append(line)
            continue
        if isinstance(obj, dict):
            block = "\n".join(f"{k}: {v}" for k, v in obj.items())
            if block:
                examples.append(block)
        elif isinstance(obj, str):
            examples.append(obj)
    return examples


def get_options() -> RunOptions:
    datasets = list_dataset_options()
    return RunOptions(
        base_models=BASE_MODELS,
        methods=[m.value for m in TrainingMethod],
        learning_rates=LEARNING_RATE_OPTIONS,
        lora_ranks=LORA_RANK_OPTIONS,
        epochs_min=EPOCHS_MIN,
        epochs_max=EPOCHS_MAX,
        datasets=datasets,
        default_dataset_id=datasets[0].id if datasets else None,
        gpu_available=trainer.select_device() == "cuda",
    )


def build_stats(manifests: list[RunManifest], sizes: dict[str, list[dict]]) -> RunStats:
    counts: dict[str, int] = defaultdict(int)
    total_artifacts = 0
    total_size = 0
    for m in manifests:
        counts[m.status.value] += 1
        objects = sizes.get(m.id, [])
        total_artifacts += len(objects)
        total_size += sum(int(o["size_bytes"]) for o in objects)

    # One cumulative point PER RUN, ordered by when the run happened, so a
    # same-session sweep renders an ascending run-over-run curve instead of
    # collapsing every same-day run into a single dot. `date` carries the run's
    # full timestamp (not a date-only string); the client formats it in local
    # time, so the x-axis label matches the run's real date rather than drifting
    # a day in a behind-UTC locale.
    cumulative: list[CumulativePoint] = []
    running_artifacts = 0
    running_bytes = 0
    for m in sorted(manifests, key=lambda r: r.completed_at or r.created_at):
        objects = sizes.get(m.id, [])
        running_artifacts += len(objects)
        running_bytes += sum(int(o["size_bytes"]) for o in objects)
        ts = m.completed_at or m.created_at
        cumulative.append(
            CumulativePoint(
                date=ts.isoformat(),
                artifacts=running_artifacts,
                size_bytes=running_bytes,
            )
        )

    return RunStats(
        total_runs=len(manifests),
        queued=counts["queued"],
        running=counts["running"],
        completed=counts["completed"],
        failed=counts["failed"],
        total_artifacts=total_artifacts,
        total_size_bytes=total_size,
        total_size_human=humanize_bytes(total_size),
        cumulative=cumulative,
    )
