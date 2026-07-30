<!-- last_verified: 2026-07-30 -->
# Feature: Training Runs (primary entity)

## Purpose
Run a local LoRA/QLoRA fine-tuning experiment end to end — configure it, launch
it, watch it train, and keep a reproducible record — with every artifact
versioned on Backblaze B2.

## Used By
- UI: `/runs` (list), `/runs/new` (create form), `/runs/[id]` (detail: live
  progress, loss curve, scoped artifact explorer, start/re-run, edit, delete)
- API: `GET /runs`, `POST /runs`, `GET /runs/{run_id}`,
  `POST /runs/{run_id}/start`, `PATCH /runs/{run_id}`, `DELETE /runs/{run_id}`,
  `GET /runs/options`, `GET /runs/stats`,
  `GET /runs/{run_id}/artifacts`, `GET /runs/{run_id}/artifacts/download?key=...`
- Job: a background daemon thread per started run (`service/runs.py::_execute_run`)

## Core Functions
- `services/api/app/service/runs.py` — lifecycle orchestration (create, list,
  get, start/re-run, update, delete) + the background training worker
- `services/api/app/service/run_view.py` — read-model shaping + dataset parsing
- `services/api/app/repo/trainer.py` — the training engine (device autodetect;
  CUDA→Unsloth, CPU→transformers+PEFT); all ML SDKs contained here
- `services/api/app/repo/runs_store.py` — B2 read/write/list/delete, scoped to
  `runs/<id>/`
- `services/api/app/repo/run_progress.py` — in-process live-progress registry
- `apps/web/src/components/runs/*` — table, create form, detail, loss chart,
  edit/delete dialogs; hooks in `apps/web/src/lib/queries.ts`

## Canonical Files
- Pattern exemplar: `services/api/app/service/runs.py`

## Inputs
- `CreateRunRequest`: name (string), notes (string), tags (string[]), and a
  `RunConfig` — base_model (Select), dataset_id (Select from `datasets/`),
  method (LoRA|QLoRA), epochs (1–5), learning_rate (1e-4|2e-4|5e-4),
  lora_rank (8|16|32|64). Finite fields are validated server-side against
  `GET /runs/options`.
- `UpdateRunRequest`: name / notes / tags (metadata only — config is immutable).

## Outputs
- `RunDetail` / `RunSummary` / `RunStats` / `RunOptions` (typed models)
- Side effects on B2: `config.json`, `run.json` manifest, per-epoch checkpoints,
  final `adapter/`, and `metrics.json` under `runs/<run_id>/`

## Flow
- Create → validate config, freeze `config.json`, write `run.json` (status
  `queued`).
- Start → status `running`, spawn a background thread; the request returns at
  once. The thread resolves the dataset from B2, parses it into text examples,
  and calls the trainer.
- Trainer auto-detects the device (CUDA → CPU). Each epoch: fine-tune a bounded
  number of steps, save the adapter, upload it to
  `runs/<id>/checkpoints/epoch-<n>/`, append an `EpochMetric`, persist the
  manifest, and update the in-process progress registry.
- Finish → archive the final adapter + `metrics.json`, set status `completed`
  with `final_loss` and `base_model_resolved`. On error → status `failed` with
  the message on the manifest.
- Re-run → `POST /runs/{id}/start` on a completed/failed run retrains from the
  same frozen config, overwriting the checkpoints.

## Edge Cases
- Missing/empty dataset → run fails with a recorded error.
- Start on an already-running run → `409 Conflict`.
- No CUDA GPU (incl. Apple Silicon) → the trainer falls back to the CPU PEFT path
  and records `device=cpu` + a note; QLoRA quantization and the 4-bit base models
  degrade to a real LoRA fine-tune of the CPU-demo model.
- Gated base model without `HF_TOKEN` / GPU → the CPU path is used instead;
  the requested model is preserved in the config for the record.
- Process restart mid-training → manifest keeps its last-persisted state; live
  progress is lost (re-run to continue). See RELIABILITY.md.

## UX States
- Empty: "No runs yet" with a New run action.
- Loading: skeleton rows / cards.
- Running: progress bar + message + latest loss; the list and detail poll.
- Error: inline error state with Retry; a failed run shows its error message.

## Verification
- Test files: `services/api/tests/test_structure.py` (layering + ML-SDK
  containment), `services/api/tests/test_openapi_contract.py`,
  `apps/web/src/lib/api-contract.test.ts`
- Required cases: create→queued, start→running→completed with checkpoints on B2,
  scoped delete, invalid-config rejection, device autodetect (CPU fallback)
- Focused verify command: `pnpm test:api`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full` when E2E/live prerequisites apply
- Pass criteria: a CPU run produces real adapter safetensors + a real loss curve
  under `runs/<id>/`, visible in the detail's artifact explorer

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [Checkpoint Versioning](checkpoint-versioning.md)
- [docs/app-workflows.md](../app-workflows.md)
