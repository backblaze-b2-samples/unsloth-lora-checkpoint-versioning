"""Background training worker + dataset seeding for the Run entity.

Split out of `service.runs` to keep both files under the 300-line ceiling. This
is the code that runs inside the per-run daemon thread: it resolves the dataset
from B2, drives `repo.trainer` (device auto-detected CUDA -> CPU), versions each
epoch's checkpoint to B2, and persists the manifest. No ML or boto3 SDK is
imported here — training goes through `repo.trainer`, storage through
`repo.runs_store`.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from app.config import settings
from app.repo import run_progress, runs_store, trainer
from app.service.run_view import parse_examples
from app.types.runs import EpochMetric, RunStatus

logger = logging.getLogger(__name__)

_SAMPLE_DATASET_ID = "sample-support-qa.jsonl"
_SAMPLE_DATASET = [
    {"question": "How do I reset my password?", "answer": "Open Settings, choose Security, then Reset password and follow the emailed link."},
    {"question": "Where are my invoices?", "answer": "Invoices live under Billing > History and can be downloaded as PDF."},
    {"question": "How do I invite a teammate?", "answer": "Go to Team, click Invite, and enter their work email to send an invitation."},
    {"question": "Can I export my data?", "answer": "Yes — Settings > Data > Export produces a downloadable archive of your account data."},
    {"question": "How do I cancel my plan?", "answer": "Visit Billing > Plan and choose Cancel; access continues until the period ends."},
    {"question": "Is there an API?", "answer": "Yes, a REST API is available; create a key under Settings > Developer to get started."},
]


def _content_type(name: str) -> str:
    if name.endswith(".json"):
        return "application/json"
    if name.endswith(".md"):
        return "text/markdown"
    return "application/octet-stream"


def execute_run(run_id: str) -> None:
    """Background worker: train, versioning each epoch's checkpoint to B2."""
    try:
        manifest = runs_store.read_manifest(run_id)
        if manifest is None:
            return
        config = manifest.config
        data = runs_store.get_dataset_bytes(config.dataset_id)
        if data is None:
            raise RuntimeError(f"dataset '{config.dataset_id}' is missing")
        examples = parse_examples(data, config.dataset_id)[: settings.max_train_rows]
        if not examples:
            raise RuntimeError("dataset produced no training examples")

        device = trainer.select_device(settings.training_device)
        manifest.device = device
        runs_store.write_manifest(manifest)

        def save_checkpoint(epoch: int, files: dict[str, bytes]) -> str:
            prefix = f"checkpoints/epoch-{epoch}/"
            for rel, blob in files.items():
                runs_store.put_object(
                    runs_store.object_key(run_id, prefix + rel), blob, _content_type(rel)
                )
            return runs_store.object_key(run_id, prefix)

        def report_epoch(epoch: int, loss: float, checkpoint_key: str | None) -> None:
            manifest.epoch_metrics.append(
                EpochMetric(epoch=epoch, loss=loss, checkpoint_key=checkpoint_key)
            )
            manifest.final_loss = loss
            manifest.updated_at = datetime.now(UTC)
            runs_store.write_manifest(manifest)

        def report_progress(epoch: int, loss: float | None, message: str) -> None:
            run_progress.set_progress(run_id, epoch, config.epochs, loss, message)

        result = trainer.train(
            base_model=config.base_model,
            method=config.method.value,
            epochs=config.epochs,
            learning_rate=config.learning_rate,
            lora_rank=config.lora_rank,
            examples=examples,
            device=device,
            hf_token=settings.hf_token,
            max_steps_per_epoch=settings.max_steps_per_epoch,
            save_checkpoint=save_checkpoint,
            report_epoch=report_epoch,
            report_progress=report_progress,
        )

        for rel, blob in result.final_adapter_files.items():
            runs_store.put_object(
                runs_store.object_key(run_id, f"adapter/{rel}"), blob, _content_type(rel)
            )
        metrics = {
            "run_id": run_id,
            "device": result.device,
            "base_model_requested": config.base_model,
            "base_model_resolved": result.resolved_model,
            "method": config.method.value,
            "note": result.method_note,
            "epoch_losses": result.epoch_losses,
            "loss_curve": [{"epoch": m.epoch, "loss": m.loss} for m in manifest.epoch_metrics],
        }
        runs_store.put_object(
            runs_store.object_key(run_id, "metrics.json"),
            json.dumps(metrics, indent=2).encode("utf-8"),
            "application/json",
        )

        manifest.status = RunStatus.completed
        manifest.base_model_resolved = result.resolved_model
        manifest.completed_at = datetime.now(UTC)
        manifest.updated_at = manifest.completed_at
        runs_store.write_manifest(manifest)
        logger.info("Run completed: id=%s device=%s", run_id, result.device)
    except Exception as e:
        logger.exception("Run failed: id=%s", run_id)
        manifest = runs_store.read_manifest(run_id)
        if manifest is not None:
            manifest.status = RunStatus.failed
            manifest.error = str(e)
            manifest.updated_at = datetime.now(UTC)
            runs_store.write_manifest(manifest)
    finally:
        run_progress.clear_progress(run_id)


def seed_sample_dataset() -> None:
    """Write one tiny sample dataset under datasets/ if that prefix is empty."""
    try:
        if not runs_store.datasets_prefix_empty():
            return
        body = "\n".join(json.dumps(row) for row in _SAMPLE_DATASET).encode("utf-8")
        runs_store.put_object(
            runs_store.dataset_key(_SAMPLE_DATASET_ID), body, "application/jsonl"
        )
        logger.info("Seeded sample dataset: datasets/%s", _SAMPLE_DATASET_ID)
    except Exception:
        logger.warning("Sample-dataset seeding skipped (B2 unavailable)")
