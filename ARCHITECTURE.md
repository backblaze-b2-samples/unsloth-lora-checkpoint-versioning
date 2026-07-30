<!-- last_verified: 2026-07-28 -->
# Architecture

## Components

- **apps/web/** — Next.js 16 frontend (App Router, Tailwind v4, shadcn/ui)
  - Runs domain (`/runs`, `/runs/new`, `/runs/[id]`) — the primary entity:
    create, read, start/re-run, edit, delete; live progress, loss-curve chart,
    scoped artifact explorer
  - Dashboard with MLOps metrics + the cumulative artifact-size curve
  - Dataset ingest (repurposed Upload page) + whole-bucket File browser
  - Dark mode via `next-themes`
- **services/api/** — FastAPI backend (layered architecture)
  - REST API for the Run lifecycle (`/runs*`), dataset ingest (`/upload`), and
    the whole-bucket file browser (`/files*`)
  - The **training engine** (`repo/trainer.py`) — local LoRA/QLoRA fine-tuning;
    all torch/transformers/peft/unsloth imports are contained here
  - B2 S3 integration via boto3 (all in `repo/`)
  - Background training thread + in-process run-progress registry
  - Health check endpoint with B2 connectivity verification
  - Structured JSON logging with request tracing
  - Prometheus-format metrics endpoint
- **packages/shared/** — TypeScript type definitions
  - Mirrors Pydantic models from the API
  - Consumed by `apps/web/` as workspace dependency

## Backend Layering

The API follows a strict layered architecture:

```
types/     Pydantic models — no logic, no imports from other layers
  |
config/    Settings (pydantic-settings) — depends only on types
  |
repo/      Data access (boto3 B2 client) — no business logic
  |
service/   Business logic — calls repo, returns types
  |
runtime/   FastAPI routes — calls service, never repo directly
```

### Layering Rules

1. Dependencies flow downward only: `types` -> `config` -> `repo` -> `service` -> `runtime`
2. No backward imports (e.g., service must not import from runtime)
3. `boto3` only allowed in `repo/` layer
4. All boundary data uses Pydantic models (no raw dicts across layers)
5. Each file stays under 300 lines

### Directory Structure

```
services/api/
  main.py                  App entrypoint, middleware, router registration
  app/
    types/                 Pydantic models (runs, files, upload, stats)
    config/                Settings loaded from environment
    repo/                  Data access: b2_client, runs_store, trainer,
                           run_progress (B2 + ML SDKs contained here)
    service/               Business logic (runs, run_view, upload, files, metadata)
    runtime/               FastAPI route handlers (runs, upload, files, ...)
  tests/                   pytest tests (structural + integration)
  requirements.txt         Human-edited deps (base, CPU-portable ML stack)
  requirements-gpu.txt     Optional GPU extra (unsloth/bitsandbytes/xformers)
```

## Runs Domain & Training Engine

The `Run` is the primary entity. Its lifecycle is orchestrated in
`service/runs.py`:

1. **Create** (`POST /runs`) freezes the config to `runs/<id>/config.json` and
   writes the `run.json` manifest with status `queued`.
2. **Start** (`POST /runs/{id}/start`, the `run` verb) flips status to `running`
   and launches training in a **background daemon thread** — the request returns
   immediately.
3. The thread resolves the dataset from B2, then calls `repo/trainer.py`, which
   **auto-detects the device at runtime (CUDA → CPU)**. On CUDA it runs a real
   Unsloth `FastLanguageModel` fine-tune (unsloth imported lazily, only here);
   with no GPU it runs a real transformers + PEFT LoRA fine-tune of a tiny
   CPU-friendly model. Both produce genuine adapter safetensors and a real loss
   curve.
4. Each epoch uploads a checkpoint to `runs/<id>/checkpoints/epoch-<n>/` and
   persists an updated manifest; the final adapter + `metrics.json` are archived
   on completion. Failures set status `failed` with the error on the manifest.

**In-process run-progress registry** (`repo/run_progress.py`): a thread-safe map
of sub-epoch liveness (current epoch, latest loss, message) merged into
`GET /runs/{id}` while a run is `running`. It is per-replica in-process state —
the durable source of truth stays the B2 manifest. Single-replica caveat in
[docs/RELIABILITY.md](docs/RELIABILITY.md#in-process-run-progress-registry).

### B2 key layout (the versioning story is in the prefix structure)

```
datasets/<dataset_id>                        # ingested JSONL/CSV training file
runs/<run_id>/run.json                       # manifest (status, config, metrics) — source of truth
runs/<run_id>/config.json                    # frozen training config
runs/<run_id>/checkpoints/epoch-<n>/...      # per-epoch adapter snapshot (safetensors + adapter_config.json)
runs/<run_id>/adapter/...                    # final LoRA adapter
runs/<run_id>/metrics.json                   # loss curve + summary
```

No dependency on bucket-level S3 versioning — the run-keyed prefixes are the
versioning mechanism.

## Boundary Invariants

- **No external SDK leakage**: `boto3` is only imported in `app/repo/`, and the ML SDKs (torch / transformers / peft / unsloth) are only imported in `app/repo/trainer.py` — lazily, with `unsloth` reached only on the CUDA branch. All other layers interact with B2 and the trainer through the repo interface.
- **No raw dicts at boundaries**: All data crossing layer boundaries uses typed Pydantic models.
- **No cross-layer mutable state**: Configuration is read-only after init, and no mutable state is shared *between* layers. Intra-layer caches/counters (the listing cache in `repo/list_cache.py`, the B2 connectivity cache in `repo/b2_client.py`, the download counter in `repo/counter.py`, the run-progress registry in `repo/run_progress.py`, the rate-limit and metrics state in `runtime/`) are module-local and guarded by a `threading.Lock`. The listing cache owns a stale-while-revalidate background thread (warmed once at startup by `main.lifespan`); each training run owns a background daemon thread that writes checkpoints to B2 and updates the run-progress registry.
- **Validated inputs**: All HTTP inputs validated by FastAPI/Pydantic. File keys reject empty and path-traversal patterns; optional prefix confinement via `ALLOWED_KEY_PREFIX` (off by default).

## Deployment

- **Local dev** — `pnpm dev` runs both services via `concurrently`
  - Web: `localhost:3000`
  - API: `localhost:8000`
- **Railway** — two services from the same repository: `web` builds from the
  repository root because it consumes `packages/shared`; `api` builds from
  `services/api`. The versioned per-service configs and the human-approved
  staging/production contract live in [infra/railway/README.md](infra/railway/README.md).
  External provisioning and deployment remain explicit user-approved actions.

## Data Stores

- **Backblaze B2** — object storage (S3-compatible API)
  - Datasets under `datasets/`, run artifacts under `runs/<run_id>/` (see the
    key layout above); the `run.json` manifest is the source of truth per run
  - Listing/metadata via S3 `list_objects_v2` / `head_object`; artifacts written
    with `put_object`; downloads via `generate_presigned_url`; scoped deletes via
    `delete_objects`
  - No application database — B2 is the sole data store

## External Services

- **Backblaze B2 S3 API** — file storage, retrieval, deletion, presigned URLs

## Trust Boundaries

See [docs/SECURITY.md](docs/SECURITY.md) for full security documentation.

- **Frontend -> API** — CORS-restricted to configured origins. `CORSMiddleware` is registered LAST in `main.py` (outermost) so it wraps **every** response, including uncaught-exception 500s — otherwise the browser would block error responses and the UI would only see an opaque "network error". See [docs/RELIABILITY.md](docs/RELIABILITY.md#error-handling). A per-IP rate-limit middleware sits inner to CORS; see [docs/SECURITY.md](docs/SECURITY.md#rate-limiting).
- **API -> B2** — authenticated via application keys, signature v4
- **Client -> B2** — presigned URLs for download (10-min expiry, forced attachment)

## Data Flows

- **Create run**: Browser -> `POST /runs` -> service validates config -> repo writes `config.json` + `run.json` (status `queued`) to B2 -> response
- **Start/re-run**: Browser -> `POST /runs/{id}/start` -> service flips status to `running`, spawns a background thread -> trainer fine-tunes (device auto-detected) -> per-epoch checkpoint `put_object` + manifest update -> final adapter + `metrics.json` archived -> status `completed`
- **Run detail (with live progress)**: Browser polls `GET /runs/{id}` -> service reads manifest, lists artifacts, merges the in-process progress registry while `running`
- **Ingest dataset**: Browser -> `POST /upload` (multipart) -> service validates -> repo writes under `datasets/` -> response
- **Presigned download**: Browser -> `GET /runs/{id}/artifacts/download?key=...` -> service validates the key is within `runs/<id>/` -> repo presigns -> browser downloads
- **Delete run**: Browser -> `DELETE /runs/{id}` -> service -> repo scoped `delete_objects` sweep of `runs/<id>/` only

## Observability

- Structured JSON logging on all requests with `request_id`
- Request timing middleware (logs duration per request; also the catch-all that converts uncaught exceptions to a typed JSON 500)
- `/metrics` endpoint (Prometheus format: request count, latency, upload count)
- `/health` endpoint (B2 connectivity check)

## API Contract

- Checked-in OpenAPI artifact: `docs/api/openapi.json`
- Export/check command: `pnpm contract:export` / `pnpm contract:check`
- FastAPI freshness test: `services/api/tests/test_openapi_contract.py`
- Frontend route drift test: `apps/web/src/lib/api-contract.test.ts`

The frontend client keeps a small `API_CLIENT_ROUTES` registry in
`apps/web/src/lib/api-client.ts`. Tests compare that registry to the checked-in
OpenAPI artifact so route changes fail loudly before the hand-written client can
silently drift from FastAPI. `GET /metrics` is intentionally server-only.

## Canonical Files

- Run route handlers: `services/api/app/runtime/runs.py`
- Run orchestration (background training, manifest lifecycle): `services/api/app/service/runs.py`
- Read-model shaping (summary/detail/options/stats): `services/api/app/service/run_view.py`
- Training engine (ML SDKs contained; device autodetect): `services/api/app/repo/trainer.py`
- Run/dataset B2 store: `services/api/app/repo/runs_store.py`
- In-process progress registry: `services/api/app/repo/run_progress.py`
- B2 data access (repo layer): `services/api/app/repo/b2_client.py`
- Pydantic models: `services/api/app/types/` (`runs.py`, `files.py`, `upload.py`, `stats.py`, `formatting.py`)
- Config (pydantic-settings): `services/api/app/config/settings.py`
- Structural tests: `services/api/tests/test_structure.py`
- OpenAPI contract: `docs/api/openapi.json`
- Frontend API client: `apps/web/src/lib/api-client.ts`
- Shared TypeScript types: `packages/shared/src/types.ts`

## Core Features

- [Training Runs](docs/features/training-runs.md)
- [Checkpoint Versioning](docs/features/checkpoint-versioning.md)
- [Dataset Ingest](docs/features/file-upload.md)
- [File Browser](docs/features/file-browser.md)
- [Dashboard](docs/features/dashboard.md)
- [Dataset Introspection](docs/features/metadata-extraction.md)

## References

- [docs/SECURITY.md](docs/SECURITY.md) — security principles and implementation
- [docs/RELIABILITY.md](docs/RELIABILITY.md) — reliability expectations
- [AGENTS.md](AGENTS.md) — architectural invariants and agent instructions
