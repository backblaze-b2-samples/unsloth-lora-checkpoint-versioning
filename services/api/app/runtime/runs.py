import logging

# Sync `def` handlers on purpose: the call chain is blocking (B2 I/O); Starlette
# runs sync handlers in its threadpool so one slow B2 round-trip doesn't stall
# the event loop. Training itself runs in its own background thread (see
# service.runs), so `start` returns immediately.
from fastapi import APIRouter, HTTPException

from app.service.runs import (
    InvalidRunConfigError,
    RunConflictError,
    RunNotFoundError,
    create_run,
    delete_run,
    get_artifact_download_url,
    get_run,
    get_run_options,
    get_run_stats,
    list_runs,
    start_run,
    update_run,
)
from app.types.runs import (
    Artifact,
    CreateRunRequest,
    DeleteResponse,
    RunDetail,
    RunOptions,
    RunStats,
    RunSummary,
    UpdateRunRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# SECURITY: like the files routes, these are intentionally unauthenticated and
# scoped to the sample's own bucket prefixes (single-tenant demo — see
# docs/SECURITY.md). Every write/delete is confined to `runs/<run_id>/`, so
# nothing here can touch other apps' data.


# --- Static paths first so they win over /runs/{run_id} ---


@router.get("/runs/options", response_model=RunOptions)
def run_options_endpoint():
    return get_run_options()


@router.get("/runs/stats", response_model=RunStats)
def run_stats_endpoint():
    return get_run_stats()


@router.get("/runs", response_model=list[RunSummary])
def list_runs_endpoint():
    return list_runs()


@router.post("/runs", response_model=RunDetail)
def create_run_endpoint(req: CreateRunRequest):
    try:
        detail = create_run(req)
    except InvalidRunConfigError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    logger.info("Run created: id=%s", detail.id)
    return detail


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run_endpoint(run_id: str):
    try:
        return get_run(run_id)
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None


@router.post("/runs/{run_id}/start", response_model=RunDetail)
def start_run_endpoint(run_id: str):
    try:
        return start_run(run_id)
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None
    except RunConflictError as e:
        raise HTTPException(status_code=409, detail=e.detail) from None


@router.patch("/runs/{run_id}", response_model=RunDetail)
def update_run_endpoint(run_id: str, req: UpdateRunRequest):
    try:
        return update_run(run_id, req)
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None


@router.delete("/runs/{run_id}", response_model=DeleteResponse)
def delete_run_endpoint(run_id: str):
    try:
        delete_run(run_id)
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None
    return DeleteResponse(deleted=True, id=run_id)


@router.get("/runs/{run_id}/artifacts", response_model=list[Artifact])
def run_artifacts_endpoint(run_id: str):
    try:
        return get_run(run_id).artifacts
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None


@router.get("/runs/{run_id}/artifacts/download")
def run_artifact_download_endpoint(run_id: str, key: str):
    try:
        return {"url": get_artifact_download_url(run_id, key)}
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None
    except InvalidRunConfigError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
