"""Pydantic models for the Run primary entity.

A `Run` is one LoRA/QLoRA fine-tuning experiment. Every artifact it produces —
the frozen config, per-epoch checkpoints, the final adapter, the metrics, and
the run.json manifest — is versioned on Backblaze B2 under `runs/<run_id>/`.
The manifest (run.json) is the source of truth; these models are the boundary
contract for the `/runs` API and are mirrored by the frontend in
`packages/shared/src/types.ts`.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class TrainingMethod(StrEnum):
    lora = "LoRA"
    qlora = "QLoRA"


class BaseModelOption(BaseModel):
    value: str
    label: str
    # Gated models (Llama 3.x, Gemma) need an HF_TOKEN to accept their license.
    gated: bool = False
    # The Unsloth 4-bit models only run on a CUDA GPU; the CPU-demo model does
    # not. Surfaced so the create form can warn before a run is queued.
    requires_gpu: bool = False


# Finite selector option sets. The create form uses selectors (never free text)
# for these, and they are exposed via GET /runs/options so the UI never drifts.
BASE_MODELS: list[BaseModelOption] = [
    BaseModelOption(
        value="tiny", label="Tiny (CPU demo)", gated=False, requires_gpu=False
    ),
    BaseModelOption(
        value="unsloth/Llama-3.2-1B-Instruct-bnb-4bit",
        label="Llama 3.2 1B (Unsloth 4-bit)",
        gated=True,
        requires_gpu=True,
    ),
    BaseModelOption(
        value="unsloth/Qwen2.5-0.5B-bnb-4bit",
        label="Qwen2.5 0.5B (Unsloth 4-bit)",
        gated=False,
        requires_gpu=True,
    ),
    BaseModelOption(
        value="unsloth/gemma-2-2b-bnb-4bit",
        label="Gemma 2 2B (Unsloth 4-bit)",
        gated=True,
        requires_gpu=True,
    ),
]
BASE_MODEL_VALUES: list[str] = [m.value for m in BASE_MODELS]

LEARNING_RATE_OPTIONS: list[float] = [1e-4, 2e-4, 5e-4]
LORA_RANK_OPTIONS: list[int] = [8, 16, 32, 64]
EPOCHS_MIN: int = 1
EPOCHS_MAX: int = 5


class RunConfig(BaseModel):
    """Immutable training configuration, frozen into config.json on B2."""

    base_model: str = "tiny"
    dataset_id: str = Field(..., min_length=1)
    method: TrainingMethod = TrainingMethod.lora
    epochs: int = 1
    learning_rate: float = 2e-4
    lora_rank: int = 16


class CreateRunRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    config: RunConfig


class UpdateRunRequest(BaseModel):
    """Metadata-only edit. The training config is intentionally immutable once a
    run has executed — 'change hyperparameters and try again' is served by
    re-running from a new config, not by editing the record."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    notes: str | None = None
    tags: list[str] | None = None


class EpochMetric(BaseModel):
    epoch: int
    loss: float
    checkpoint_key: str | None = None


class RunProgress(BaseModel):
    """Live progress for a running training job (in-process, merged into the
    detail while the run's status is `running`)."""

    current_epoch: int
    total_epochs: int
    latest_loss: float | None = None
    message: str = ""


class Artifact(BaseModel):
    key: str
    filename: str
    kind: str  # manifest | config | metrics | checkpoint | adapter | other
    size_bytes: int
    size_human: str
    last_modified: datetime
    download_url: str | None = None


class RunManifest(BaseModel):
    """Persisted run record (runs/<id>/run.json) — the source of truth."""

    id: str
    name: str
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    config: RunConfig
    status: RunStatus = RunStatus.queued
    device: str = ""  # resolved device the run trained on (cuda | cpu)
    base_model_resolved: str = ""  # the actual model id/path used
    epoch_metrics: list[EpochMetric] = Field(default_factory=list)
    final_loss: float | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RunSummary(BaseModel):
    id: str
    name: str
    status: RunStatus
    base_model: str
    dataset_id: str
    method: TrainingMethod
    epochs: int
    final_loss: float | None = None
    artifact_count: int
    size_bytes: int
    size_human: str
    created_at: datetime
    updated_at: datetime


class RunDetail(BaseModel):
    id: str
    name: str
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    config: RunConfig
    status: RunStatus
    device: str = ""
    base_model_resolved: str = ""
    epoch_metrics: list[EpochMetric] = Field(default_factory=list)
    final_loss: float | None = None
    error: str | None = None
    progress: RunProgress | None = None
    artifacts: list[Artifact] = Field(default_factory=list)
    artifact_count: int = 0
    size_bytes: int = 0
    size_human: str = "0 B"
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class DatasetOption(BaseModel):
    id: str  # key relative to the datasets/ prefix (== filename)
    filename: str
    rows: int | None = None
    size_bytes: int
    size_human: str


class RunOptions(BaseModel):
    base_models: list[BaseModelOption]
    methods: list[str]
    learning_rates: list[float]
    lora_ranks: list[int]
    epochs_min: int
    epochs_max: int
    datasets: list[DatasetOption]
    default_dataset_id: str | None = None
    # Whether a CUDA GPU is present on the API host, so the form can steer the
    # user toward the CPU-demo model when it is not.
    gpu_available: bool = False


class CumulativePoint(BaseModel):
    date: str
    artifacts: int
    size_bytes: int


class RunStats(BaseModel):
    total_runs: int
    queued: int
    running: int
    completed: int
    failed: int
    total_artifacts: int
    total_size_bytes: int
    total_size_human: str
    cumulative: list[CumulativePoint]


class DeleteResponse(BaseModel):
    deleted: bool
    id: str
