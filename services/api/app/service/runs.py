"""Run lifecycle orchestration: create -> start (train) -> version on B2.

Owns the full CRUD + `run` (start/re-run) surface for the `Run` entity. The
background training worker and dataset seeding live in `run_executor` (kept
separate so both files stay under the 300-line ceiling); B2 I/O is in
`repo.runs_store`, live progress in `repo.run_progress`, and read-model shaping
in `run_view`. No ML or boto3 SDK is imported here.

Training executes in a background daemon thread with an in-process progress
registry merged into `GET /runs/{id}` while running; the final state persists to
B2. This is single-replica (see docs/RELIABILITY.md), the same class of
in-process state as the rate limiter and the listing cache.
"""

from __future__ import annotations

import logging
import re
import secrets
import threading
from datetime import UTC, datetime

from app.repo import run_progress, runs_store
from app.service.run_executor import execute_run, seed_sample_dataset
from app.service.run_view import build_detail, build_stats, build_summary, get_options
from app.types.runs import (
    BASE_MODEL_VALUES,
    EPOCHS_MAX,
    EPOCHS_MIN,
    LEARNING_RATE_OPTIONS,
    LORA_RANK_OPTIONS,
    CreateRunRequest,
    RunConfig,
    RunDetail,
    RunManifest,
    RunOptions,
    RunStats,
    RunStatus,
    RunSummary,
    UpdateRunRequest,
)

logger = logging.getLogger(__name__)

__all__ = [
    "InvalidRunConfigError",
    "RunConflictError",
    "RunNotFoundError",
    "create_run",
    "delete_run",
    "get_artifact_download_url",
    "get_run",
    "get_run_options",
    "get_run_stats",
    "list_runs",
    "seed_sample_dataset",
    "start_run",
    "update_run",
]


class RunServiceError(Exception):
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class RunNotFoundError(RunServiceError):
    def __init__(self, detail: str = "Run not found"):
        super().__init__(detail)


class RunConflictError(RunServiceError):
    pass


class InvalidRunConfigError(RunServiceError):
    pass


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:40] or "run"


def _new_id(name: str) -> str:
    return f"{_slug(name)}-{secrets.token_hex(3)}"


def _require_manifest(run_id: str) -> RunManifest:
    manifest = runs_store.read_manifest(run_id)
    if manifest is None:
        raise RunNotFoundError()
    return manifest


def _validate_config(config: RunConfig) -> None:
    if config.base_model not in BASE_MODEL_VALUES:
        raise InvalidRunConfigError(f"base_model must be one of {BASE_MODEL_VALUES}")
    if not EPOCHS_MIN <= config.epochs <= EPOCHS_MAX:
        raise InvalidRunConfigError(f"epochs must be between {EPOCHS_MIN} and {EPOCHS_MAX}")
    if round(config.learning_rate, 6) not in {round(v, 6) for v in LEARNING_RATE_OPTIONS}:
        raise InvalidRunConfigError(f"learning_rate must be one of {LEARNING_RATE_OPTIONS}")
    if config.lora_rank not in LORA_RANK_OPTIONS:
        raise InvalidRunConfigError(f"lora_rank must be one of {LORA_RANK_OPTIONS}")
    if runs_store.get_dataset_bytes(config.dataset_id) is None:
        raise InvalidRunConfigError(
            f"dataset '{config.dataset_id}' was not found under the datasets/ prefix"
        )


def create_run(req: CreateRunRequest) -> RunDetail:
    _validate_config(req.config)
    now = datetime.now(UTC)
    manifest = RunManifest(
        id=_new_id(req.name),
        name=req.name,
        notes=req.notes,
        tags=req.tags,
        config=req.config,
        status=RunStatus.queued,
        created_at=now,
        updated_at=now,
    )
    # Freeze the config alongside the manifest so it is a versioned artifact.
    runs_store.put_object(
        runs_store.object_key(manifest.id, "config.json"),
        req.config.model_dump_json(indent=2).encode("utf-8"),
        "application/json",
    )
    runs_store.write_manifest(manifest)
    logger.info("Run created: id=%s status=queued", manifest.id)
    return build_detail(manifest, runs_store.list_run_objects(manifest.id))


def list_runs() -> list[RunSummary]:
    summaries: list[RunSummary] = []
    for run_id in runs_store.list_run_ids():
        manifest = runs_store.read_manifest(run_id)
        if manifest is None:
            continue
        summaries.append(build_summary(manifest, runs_store.list_run_objects(run_id)))
    summaries.sort(key=lambda s: s.updated_at, reverse=True)
    return summaries


def get_run(run_id: str) -> RunDetail:
    manifest = _require_manifest(run_id)
    return build_detail(manifest, runs_store.list_run_objects(run_id))


def update_run(run_id: str, req: UpdateRunRequest) -> RunDetail:
    manifest = _require_manifest(run_id)
    if req.name is not None:
        manifest.name = req.name
    if req.notes is not None:
        manifest.notes = req.notes
    if req.tags is not None:
        manifest.tags = req.tags
    manifest.updated_at = datetime.now(UTC)
    runs_store.write_manifest(manifest)
    return build_detail(manifest, runs_store.list_run_objects(run_id))


def delete_run(run_id: str) -> None:
    _require_manifest(run_id)
    run_progress.clear_progress(run_id)
    runs_store.delete_run(run_id)
    logger.info("Run deleted: id=%s (artifacts swept under runs/%s/)", run_id, run_id)


def start_run(run_id: str) -> RunDetail:
    """The `run` verb: launch (or re-run) training in the background."""
    manifest = _require_manifest(run_id)
    if manifest.status == RunStatus.running:
        raise RunConflictError("Run is already training")
    now = datetime.now(UTC)
    manifest.status = RunStatus.running
    manifest.started_at = now
    manifest.updated_at = now
    manifest.completed_at = None
    manifest.error = None
    manifest.epoch_metrics = []
    manifest.final_loss = None
    runs_store.write_manifest(manifest)
    run_progress.set_progress(run_id, 0, manifest.config.epochs, message="Queued")

    thread = threading.Thread(target=execute_run, args=(run_id,), daemon=True)
    thread.start()
    logger.info("Run started: id=%s", run_id)
    return build_detail(manifest, runs_store.list_run_objects(run_id))


def get_run_options() -> RunOptions:
    return get_options()


def get_run_stats() -> RunStats:
    manifests: list[RunManifest] = []
    sizes: dict[str, list[dict]] = {}
    for run_id in runs_store.list_run_ids():
        manifest = runs_store.read_manifest(run_id)
        if manifest is None:
            continue
        manifests.append(manifest)
        sizes[run_id] = runs_store.list_run_objects(run_id)
    return build_stats(manifests, sizes)


def get_artifact_download_url(run_id: str, key: str) -> str:
    _require_manifest(run_id)
    prefix = runs_store.run_dir(run_id)
    if not key.startswith(prefix) or ".." in key:
        raise InvalidRunConfigError("artifact key must be within this run's prefix")
    return runs_store.presign(key, filename=key.split("/")[-1])
