"""In-process live-progress registry for running training jobs.

Training runs in a background thread (see `service.runs`); this registry holds
the sub-epoch liveness (current epoch + latest loss + a status message) that is
too fast-moving to round-trip through the B2 manifest on every step. The B2
manifest stays the durable source of truth; this is a best-effort overlay that
`service.runs.get_run` merges in while a run's status is `running`.

This is in-process, per-replica state — like the rate limiter and the listing
cache. It does not survive a restart and is not shared across replicas; the
single-replica caveat is documented in docs/RELIABILITY.md.
"""

from __future__ import annotations

from threading import Lock

from app.types.runs import RunProgress

_progress: dict[str, RunProgress] = {}
_lock = Lock()


def set_progress(
    run_id: str,
    current_epoch: int,
    total_epochs: int,
    latest_loss: float | None = None,
    message: str = "",
) -> None:
    with _lock:
        _progress[run_id] = RunProgress(
            current_epoch=current_epoch,
            total_epochs=total_epochs,
            latest_loss=latest_loss,
            message=message,
        )


def get_progress(run_id: str) -> RunProgress | None:
    with _lock:
        return _progress.get(run_id)


def clear_progress(run_id: str) -> None:
    with _lock:
        _progress.pop(run_id, None)
