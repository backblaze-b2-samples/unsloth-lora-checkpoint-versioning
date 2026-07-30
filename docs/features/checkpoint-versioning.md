<!-- last_verified: 2026-07-30 -->
# Feature: Checkpoint & Artifact Versioning on B2

## Purpose
Version every artifact a fine-tuning run produces on Backblaze B2 under a
run-keyed prefix, so runs are reproducible, rollback-able, shareable, and their
storage footprint accumulates visibly run over run.

## Used By
- UI: `/runs/[id]` scoped artifact explorer (lists only `runs/<id>/…` with
  presigned downloads); the Dashboard cumulative artifact-size curve
- API: `GET /runs/{run_id}/artifacts`,
  `GET /runs/{run_id}/artifacts/download?key=...`, `GET /runs/stats`

## Core Functions
- `services/api/app/repo/runs_store.py` — `put_object`, `list_run_objects`,
  `run_size_bytes`, `delete_run` (scoped `delete_objects`), `presign`
- `services/api/app/service/run_view.py` — `artifact_kind`, `build_artifacts`,
  `build_stats` (the cumulative curve)
- `apps/web/src/components/dashboard/artifact-growth-chart.tsx`

## Canonical Files
- Pattern exemplar: `services/api/app/repo/runs_store.py`

## Inputs
- A run id and its artifact object keys (all under `runs/<run_id>/`)

## Outputs
- `Artifact[]` (key, filename, kind, size, presigned `download_url`)
- `RunStats.cumulative`: per-day cumulative artifact count + bytes
- Side effect: presigned GET URLs (attachment disposition, 10-min expiry)

## Flow
- The versioning story lives in the **prefix structure** — no dependency on
  bucket-level S3 versioning:
  ```
  datasets/<dataset_id>
  runs/<run_id>/run.json          # manifest (source of truth)
  runs/<run_id>/config.json       # frozen config
  runs/<run_id>/checkpoints/epoch-<n>/...
  runs/<run_id>/adapter/...
  runs/<run_id>/metrics.json
  ```
- As a run trains, each epoch's adapter is uploaded with `put_object`; the
  scoped explorer lists them via `list_objects_v2` on `runs/<id>/`.
- Download: the API validates the requested key is within the run's prefix, then
  presigns it — one click fetches any versioned checkpoint or the final adapter.
- Delete: `delete_run` sweeps only `runs/<id>/` via batched `delete_objects` —
  never bucket-wide.
- The dashboard sums each run's bytes by creation day into a **cumulative curve**
  that only grows as experiments pile up — the headline B2 metric.

## Edge Cases
- Download key outside the run's prefix or containing `..` → `400`.
- Missing run → `404`.
- Empty bucket / no runs → the curve and explorer show empty states.

## UX States
- Empty: "No artifacts yet — start training to version checkpoints here."
- Loading: skeleton table / chart.
- Error: inline error state with Retry.

## Verification
- Test files: `services/api/tests/test_structure.py`,
  `services/api/tests/test_openapi_contract.py`
- Required cases: scoped listing, presign within-prefix guard, scoped delete,
  cumulative stats
- Focused verify command: `pnpm test:api`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full` when E2E/live prerequisites apply
- Pass criteria: artifacts appear under `runs/<id>/` and the cumulative curve
  grows across runs

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [Training Runs](training-runs.md)
