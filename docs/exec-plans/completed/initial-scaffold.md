# Build plan — `unsloth-lora-checkpoint-versioning`

Source of truth: `.claude/scratch/vcsk-f858e16f-9c8a-4365-b4ed-21f5d825207a/` (fresh clone of
vibe-coding-starter-kit). Closest analog already in the tree: `finetune-dataset-generator`
(same ML domain, already on Standard-#3 env vars) — mirror its `settings.py` B2 block and
`repo/b2_client.py` UA convention.

---

## 1. Purpose

`unsloth-lora-checkpoint-versioning` is an MLOps experiment-tracking dashboard for **local
LoRA/QLoRA fine-tuning with [Unsloth](https://github.com/unslothai/unsloth)**, where every
artifact a run produces — the training dataset, per-epoch checkpoints, the final adapter,
the training config, and the metrics JSON — is **versioned on Backblaze B2 under a
run-keyed prefix**. It is for ML engineers and researchers running fine-tuning experiments
on open-weight models (Llama / Qwen / Gemma) on a single GPU who need reproducible,
rollback-able, shareable run artifacts without standing up a heavyweight MLOps stack. B2 is
the remote artifact store for the entire loop (ingest → train → checkpoint → archive →
serve/query), accessed via the S3-compatible API with a custom user-agent and standard
`B2_*` env vars. The value B2 shows: a **real accumulating-artifact curve** that grows with
every experiment sweep — datasets + adapters + checkpoints + configs piling up run over run.

## 2. Architecture delta from vibe-coding-starter-kit

The starter kit is the ceiling — strip what this app doesn't need, keep the reusable
B2-backed scaffolding, add the Runs domain.

### KEEP (as-is — starter contract, do not strip/rename/replace)
- **UI kit / design system** — `apps/web/src/components/ui/`, tokens in `globals.css`, the
  `/design` page. Build new screens from these primitives only.
- **Bucket explorer** — `/files` route, `apps/web/src/app/files/`,
  `apps/web/src/components/files/`. **NON-NEGOTIABLE keep** (full-bucket browse). The Files
  sidebar entry stays. This is the whole-bucket view; the sample-specific scoped explorer is
  a separate ADD (see below).
- **Upload** — `/upload` route + `apps/web/src/components/upload/`. Kept and **repurposed as
  the dataset-ingest surface** (workflow step 1): accept `.jsonl` / `.csv`, write under the
  `datasets/` prefix. Route, components, and sidebar entry stay; only accepted types + copy
  change.
- **FastAPI layered backend** — `types → config → repo → service → runtime`, structural
  tests, `/health`, `/metrics`, per-IP rate limiting, JSON logging, OpenAPI contract check,
  `check:agent-docs` gate. All invariants preserved (boto3 + all external SDKs confined to
  `repo/`; ≤300-line files; TanStack Query for every fetch; contract re-export on every route
  change).
- **Settings** page + `settings/settings-form.tsx` — kept; it is the in-repo **form-UX
  exemplar** the new run form mirrors (Select for finite fields, FormDescription for defaults).
- Sidebar shell, header, command palette, theme provider, error/empty/loading states.

### TRIM (remove or slim from starter)
- **Generic image/PDF metadata extraction** — `service/metadata.py` (Pillow/EXIF/PyPDF2 image
  dims) is irrelevant to training artifacts. Slim to a lightweight **dataset introspection**
  (row count + byte size + detected format for `.jsonl`/`.csv`); drop Pillow/PyPDF2-only code
  paths and their metadata doc. Keep basic content-type/size. Do NOT add heavy parse deps.
- **Illustrative dashboard internals** — `components/dashboard/` (generic upload stats/chart/
  recent-uploads) are ADAPTED, not deleted (see §4 dashboard). The generic "uploads today"
  framing is replaced with MLOps metrics.
- `e2e/upload.spec.ts` — adapt to the dataset-upload flow (keep one smoke spec; don't expand).

### ADD (new for this sample)
- **Runs domain (backend)** — the primary entity:
  - `types/runs.py` — Pydantic models: `RunConfig`, `RunSummary`, `RunDetail`, `RunStatus`
    (`queued|running|completed|failed`), `Artifact`, `EpochMetric`.
  - `repo/runs_store.py` — B2-backed run store: read/write `runs/<run_id>/run.json` (the run
    manifest is the source of truth), list runs (list `runs/` prefix), list a run's artifacts,
    delete a run (scoped `delete_object` sweep of `runs/<run_id>/` only — never wider).
  - `repo/trainer.py` (+ `repo/artifacts.py` if >300 lines) — the **training engine** (§4).
    Contains ALL torch / transformers / peft / unsloth imports (external-SDK containment
    invariant). Lazy-imports unsloth only inside the CUDA branch.
  - `service/runs.py` — orchestrates a run: resolve dataset from B2 → train (per-epoch
    checkpoint upload) → archive final bundle → update manifest status. Background execution
    via a thread with an in-process progress registry (current epoch + latest loss), merged
    into `GET /runs/{id}` while running; final state persists to B2. Single-replica caveat
    documented in `docs/RELIABILITY.md` (same class as the rate limiter / list cache).
  - `runtime/runs.py` — routes: `GET /runs` (list), `POST /runs` (create → status `queued`),
    `GET /runs/{id}` (detail), `POST /runs/{id}/start` (**run** verb; launch/re-run training),
    `PATCH /runs/{id}` (edit metadata: name/notes/tags), `DELETE /runs/{id}` (delete + scoped
    artifact sweep), `GET /runs/{id}/artifacts` (scoped artifact listing),
    `GET /runs/{id}/artifacts/{key}/download` (presigned URL). Re-export `openapi.json`;
    register any backend-only route in `SERVER_ONLY_OPERATIONS`.
- **Runs UI (frontend)**:
  - `/runs` — run list (read): table of status, base model, dataset, method, epochs, final
    loss, artifact count, size, created; "New run" button; row → detail.
  - `/runs/new` — **create** form (§4 form UX).
  - `/runs/[id]` — run detail: config summary; live status/progress; **loss-curve chart**
    (reuse Recharts `chart.tsx`); **scoped artifact explorer** (the mandatory sample-specific
    explorer — lists only `runs/<id>/…`: per-epoch checkpoints, final adapter, config.json,
    metrics.json, each with a presigned **download**); **Start / Re-run** (run), **Edit**
    (dialog, metadata), **Delete** (with AlertDialog confirm).
  - Edit = a dialog/form for run metadata (name, notes, tags) — mirrors settings-form.
  - Sidebar: add **Runs** entry (keep Dashboard, Upload, Files, Settings, Design).
  - All fetches through new TanStack Query hooks in `lib/queries.ts`; client routes registered
    in `lib/api-client.ts` (`API_CLIENT_ROUTES`).
- **Dashboard adaptation** — MLOps metrics: total runs, runs by status, total artifacts,
  **cumulative artifact size over time (the accumulating B2 curve)**, recent runs table.
- **`packages/shared/src/types.ts`** — shared Run/Artifact TS types mirroring the Pydantic
  models.

## 3. B2 surface (all S3-compatible — Standard #1 satisfied, no b2-native)

| Op | Used for |
|----|----------|
| `put_object` | ingest dataset; write per-epoch checkpoint, final adapter, config.json, metrics.json, run.json manifest |
| `list_objects_v2` | list runs (`runs/` prefix), list a run's artifacts, full-bucket `/files` explorer, dashboard aggregates |
| `head_object` | artifact size/type for the scoped explorer |
| `get_object` | read run.json manifest; read dataset for training |
| `generate_presigned_url` | download any versioned checkpoint/adapter (workflow step 5) |
| `delete_object` | delete a run's artifacts (scoped to `runs/<run_id>/`) |

**No b2-native API.** Reuse the starter's `repo/b2_client.py` / `repo/b2_object.py` verbatim
(single cached boto3 S3 client, `signature_version=s3v4`, `user_agent_extra`).

**B2 key layout** (the versioning story lives in the prefix structure — no dependency on
bucket-level S3 versioning being enabled):
```
datasets/<dataset_id>/<filename>            # ingest
runs/<run_id>/run.json                      # manifest (status, config, metrics) — source of truth
runs/<run_id>/config.json                   # frozen training config
runs/<run_id>/checkpoints/epoch-<n>/…       # per-epoch adapter snapshot (safetensors + adapter_config.json)
runs/<run_id>/adapter/…                     # final LoRA adapter
runs/<run_id>/metrics.json                  # loss curve + summary
```

## 4. Key features

1. **Local LoRA/QLoRA fine-tuning with Unsloth** — the core capability.
   - **External API provider:** NONE. Runs on local OSS; B2 credentials only. Base weights
     pull from Hugging Face (public open models need no key; **gated** models — Llama 3.x,
     Gemma — need an optional `HF_TOKEN` to accept the license). The CPU-demo model is
     ungated → the default demo needs no token.
   - **`deployment: local`** (explicit per-feature field). Heavy workload runs on-device.
   - **Hardware autodetect (hard rule — CPU default, GPU autodetect):** `repo/trainer.py`
     picks the first available of **CUDA → CPU** at runtime.
     - **CUDA present →** real **Unsloth** `FastLanguageModel` LoRA/QLoRA fine-tune of the
       selected 4-bit base model (the vendor's own engine — fidelity). `unsloth` imported
       lazily here only.
     - **No CUDA →** a **real but minimal `transformers` + `peft` LoRA fine-tune** of a tiny
       CPU-friendly causal LM (default `hf-internal-testing/tiny-random-LlamaForCausalLM`) for
       a bounded number of steps on the ingested dataset. This produces **genuine LoRA adapter
       safetensors + a real loss curve + real per-epoch checkpoints** — not a mock — so the
       full B2 versioning loop is real and verifiable on a GPU-less host (macOS/CI).
     - **MPS note:** Unsloth has **no** Apple-MPS path (Triton/bitsandbytes are CUDA-only), so
       on Apple Silicon this sample falls back CUDA→CPU (the PEFT tiny-model path), per the
       api-provider-selection MPS caveat. Document this in README + trainer docstring.
   - **Cost:** $0 per run (fully local). No provider key, no paywall.
   - **Install safety (pin everything):** base deps `torch` (CPU wheel), `transformers`,
     `peft`, `datasets`, `accelerate`, `safetensors` — all **pinned** (avoid the unpinned-ML
     clean-install false-green). `unsloth` + `bitsandbytes` + `xformers`/`triton` go in a
     **separate optional GPU requirements file** (`services/api/requirements-gpu.txt`) / extra,
     NOT the base lock — they do not install on macOS arm64 and would break clean install /
     verify. Trainer import must never touch unsloth on a non-CUDA host.
2. **Checkpoint & artifact versioning on B2** — every run keyed under `runs/<run_id>/`; each
   epoch snapshots a checkpoint; final bundle = adapter + config + metrics. The accumulating
   curve is the headline B2 metric.
3. **Run history & comparison** — browse all runs, compare base model / method / epochs /
   final loss across runs in the list table.
4. **Presigned checkpoint download** — one-click presigned URL for any versioned artifact.
5. **Dataset ingest** — upload JSONL/CSV training datasets to B2 as the canonical per-run
   source (repurposed Upload page).
6. **Full-bucket explorer** — the kept `/files` view for whole-bucket browse.

### Primary-entity lifecycle — entity: **Run** (a fine-tuning experiment)
DEFAULT is all verbs in the UI. Analysis:
- **create** ✅ `/runs/new` form → `POST /runs` (status `queued`).
- **read** ✅ `/runs` list + `/runs/[id]` detail.
- **run** ✅ "Start training" / "Re-run" button → `POST /runs/{id}/start` (background train,
  per-epoch checkpoint upload, manifest status transitions).
- **edit** ✅ metadata edit (name / notes / tags) via dialog → `PATCH /runs/{id}`. (The
  *training config* is intentionally immutable once a run has executed — a completed run is an
  experiment record; changing its hyperparameters would misrepresent its artifacts. "Change
  hyperparameters and try again" is served by **Re-run from this config** which creates a NEW
  run, not by editing the record. This is a scope choice, not an omission: the edit verb IS in
  the UI, over the run's mutable metadata.)
- **delete** ✅ `DELETE /runs/{id}` with confirm; scoped `runs/<run_id>/` artifact sweep.

**`omitted_ui_verbs`: none.** All five verbs are user-accessible.

### Form UX (create/edit) — mirror `settings/settings-form.tsx`
Create form (`/runs/new`) fields:
- `name` — text (free text; run label). *(placeholder guidance: "e.g. llama32-support-tone-v1")*
- `base_model` — **Select** (finite): `Tiny (CPU demo)` · `Llama 3.2 1B (Unsloth 4-bit)` ·
  `Qwen2.5 0.5B (Unsloth 4-bit)` · `Gemma 2 2B (Unsloth 4-bit)`. FormDescription notes gated
  models need `HF_TOKEN` + a CUDA GPU; the CPU-demo model is the safe default.
- `dataset` — **Select** populated from ingested datasets (`datasets/` prefix); empty-state
  links to Upload.
- `method` — **RadioGroup** (finite): `LoRA` · `QLoRA`.
- `epochs` — number input (small int; default 1).
- `learning_rate` — **Select** (finite): `1e-4` · `2e-4` · `5e-4`.
- `lora_rank` — **Select** (finite): `8` · `16` · `32` · `64`.

Selector rule: every finite-value field above uses Select/RadioGroup, never free text (applies
to both create and edit). Default-hint rule (create only): safe defaults surfaced as
placeholder / FormDescription for a sound first run — **base_model = Tiny (CPU demo), method =
LoRA, epochs = 1, lr = 2e-4, rank = 16, dataset = seeded sample** — guidance text only, never
an autofill button. Edit form opens pre-filled with the real run's metadata (name/notes/tags);
finite fields there (none currently — metadata is free text) would still use selectors.

## 5. Doc transforms
- **README.md** — full rewrite: purpose, 5-step workflow, quickstart, **GPU-vs-CPU behavior**
  (real Unsloth on CUDA / real tiny PEFT fine-tune on CPU), optional `HF_TOKEN` for gated
  models, B2 artifact-versioning story + curve, Standard-#3 env vars. Update screenshots
  section to placeholders (screenshots are a later pipeline step — do NOT create images).
- **PRODUCT.md** — rewrite audience (ML engineers/researchers) + purpose (reproducible,
  rollback-able fine-tune artifacts on B2). Keep brand-personality/accessibility sections.
- **ARCHITECTURE.md** — add Runs domain, trainer engine (autodetect), B2 prefix layout, the
  in-process progress registry + single-replica caveat.
- **AGENTS.md + shims** (`CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`) — update
  repo map / feature list / doc map; **keep all invariants + the mechanical-enforcement table
  intact** (agent-docs gate is CI-blocking). Register any new checked doc in
  `scripts/check-agent-docs.mjs` only if you add a gate — otherwise leave the checker's
  expected set matching reality.
- `docs/features/`: **rewrite** `dashboard.md` (MLOps metrics); **rewrite** `file-upload.md`
  → dataset-ingest framing; **keep** `file-browser.md` (bucket explorer) + note the scoped
  run-artifact explorer; **rewrite/trim** `metadata-extraction.md` → dataset-introspection (or
  delete + drop from doc map); **keep** `settings.md`. **Add** `training-runs.md` (core) and
  `checkpoint-versioning.md` (B2 story). Keep `_template.md`.
- `docs/app-workflows.md` — rewrite journeys: ingest dataset → configure run → start training →
  watch checkpoints land on B2 → browse/compare runs → presigned-download a checkpoint.
- `docs/dev-workflows.md` — add the GPU-optional / CPU-default trainer note + how to install the
  optional GPU extra; keep the verify/worktree sections.
- `docs/RELIABILITY.md` — add the in-process run-progress registry single-replica caveat.
- **.env.example** — Standard-#3 names + optional `HF_TOKEN` + note GPU optional.

## 6. Rename table

| Kind | From (starter) | To |
|------|----------------|----|
| kebab slug / repo | `vibe-coding-starter-kit` | `unsloth-lora-checkpoint-versioning` |
| npm workspace scope | `@vibe-coding-starter-kit/web`, `/shared` | `@unsloth-lora-checkpoint-versioning/web`, `/shared` |
| Title Case | "Vibe Coding Starter Kit" / "OSS Starter Kit" | "Unsloth LoRA Checkpoint Versioning" |
| `APP_NAME` (`lib/app-config.ts`) | `"OSS Starter Kit"` | `"Unsloth LoRA Checkpoint Versioning"` |
| `APP_DESCRIPTION` | "File management dashboard powered by Backblaze B2" | "Version every LoRA/QLoRA fine-tuning artifact on Backblaze B2" |
| snake (python pkg name in `pyproject.toml`) | `vibe_coding_starter_kit` (if present) | `unsloth_lora_checkpoint_versioning` |
| `user_agent_extra` (`repo/b2_client.py`) | `b2ai-oss-start` | `b2ai-unsloth-lora-checkpoint-versioning` |
| UTM `utm_content` (README links) | `b2ai-oss-start` | `b2ai-unsloth-lora-ckpt` |
| CI / image tags / railway slugs / workflow names | `vibe-coding-starter-kit` | `unsloth-lora-checkpoint-versioning` |
| **Env vars → Standard #3** | `B2_ENDPOINT`, `B2_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_PUBLIC_URL` | `B2_APPLICATION_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_REGION`, `B2_PUBLIC_URL_BASE` (+ optional `B2_ENDPOINT` override derived from `B2_REGION` as in `finetune-dataset-generator/settings.py`) |

Grep for every literal occurrence of `vibe-coding-starter-kit`, `vibe_coding_starter_kit`,
`Vibe Coding`, `OSS Starter Kit`, `b2ai-oss-start`, and the old `B2_KEY_ID`/`B2_ENDPOINT`/
`B2_PUBLIC_URL` names across the whole tree (code, docs, workflows, railway, package.json,
pnpm-workspace.yaml, tests) — leave none behind. Re-export `docs/api/openapi.json` and keep
`pnpm verify` green (agent-docs + api + web).

## 7. Non-negotiables recap for the builder
- Standard #1 S3-only (no b2-native). Standard #2 custom UA `b2ai-unsloth-lora-checkpoint-versioning`
  on the S3 client. Standard #3 the five `B2_*` names.
- Bucket explorer `/files` stays. Sample-specific scoped explorer (run-artifact view) added.
- All five Run verbs in the UI. External SDKs (torch/transformers/peft/unsloth) confined to
  `repo/`. TanStack Query for every fetch. ≤300-line files. `openapi.json` re-exported. Pin all
  ML deps; unsloth/bitsandbytes/xformers in an **optional GPU extra**, never the base lock.
- `pnpm verify` (agent-docs + api + web) must pass; structural + contract tests green.
