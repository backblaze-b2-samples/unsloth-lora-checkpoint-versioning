<!-- last_verified: 2026-07-30 -->
# App Workflows

User journeys inside the application. The core loop is: **ingest a dataset →
configure a run → start training → watch checkpoints land on B2 → browse/compare
runs → presigned-download a checkpoint.**

## Ingest a Dataset

- User navigates to `/upload` ("Ingest a dataset")
- Drops or selects a JSONL/CSV training file (the picker is scoped to those
  formats); client validates size (max 100MB) and type
- A determinate bar tracks the bytes leaving the browser, then the row switches
  to "Storing in B2..." with an indeterminate sweep for the server-side phase
- On success the file lands under `datasets/` and becomes selectable in the
  run-create form; a "View in Files" link goes to the browser
- A tiny sample dataset is seeded automatically on first run, so this step is
  optional for a first experiment
- See: [Dataset Ingest](features/file-upload.md)

## Configure and Start a Run (primary journey)

- User navigates to `/runs` → **New run**
- Fills the create form: name, notes, tags, and the training config — **base
  model** (Select), **dataset** (Select from `datasets/`), **method**
  (LoRA/QLoRA RadioGroup), **epochs** (1–5), **learning rate** (Select),
  **LoRA rank** (Select). Safe defaults are pre-filled (Tiny CPU-demo model,
  LoRA, 1 epoch, 2e-4, rank 16, seeded dataset); the form warns that gated models
  need `HF_TOKEN` + a CUDA GPU
- Submitting creates the run with status `queued`; the config is frozen to
  `runs/<id>/config.json` and the app routes to the run detail page
- On the detail page the user presses **Start training** — the run flips to
  `running` and training launches in the background
- See: [Training Runs](features/training-runs.md)

## Watch Training & Version Checkpoints

- The detail page polls while the run is `running`: a progress bar + message +
  latest loss update in place, and the **loss curve** fills in per epoch
- Each completed epoch uploads a checkpoint to
  `runs/<id>/checkpoints/epoch-<n>/`, which appears in the scoped artifact
  explorer as it lands
- On completion, the final adapter (`adapter/`) and `metrics.json` are archived;
  status becomes `completed` with the final loss shown
- A failed run shows its error message and can be re-run
- See: [Checkpoint Versioning](features/checkpoint-versioning.md)

## Browse, Compare & Download

- `/runs` lists every run with status, base model, method, epochs, final loss,
  artifact count, size, and created date — compare experiments at a glance
- The run detail's **scoped artifact explorer** lists only `runs/<id>/…` and each
  artifact has a one-click **presigned download** (config, per-epoch checkpoints,
  final adapter, metrics)
- **Re-run** retrains from the same frozen config; **Edit** changes metadata
  (name/notes/tags) via a dialog; **Delete** removes the run with a confirm and a
  scoped `runs/<id>/` sweep
- See: [Training Runs](features/training-runs.md)

## Browse the Whole Bucket

- User navigates to `/files` — the kept whole-bucket explorer (everything on B2,
  including `datasets/` and `runs/`)
- Tree view with preview, download, and delete; the 100 most recent objects load
  first with an on-screen loading notice for the cold scan
- See: [File Browser](features/file-browser.md)

## View Dashboard

- User navigates to `/` (home)
- Stat cards show total runs, completed runs, artifacts on B2, and storage on B2
- The **artifact-growth chart** plots cumulative artifact bytes over time — the
  accumulating-artifact curve that grows with every experiment
- The recent-runs table links each run to its detail; both queries poll while a
  run is active
- Empty state until the first run exists
- See: [Dashboard](features/dashboard.md)

## Change Preferences

- User navigates to `/settings`
- A banner states the page is mostly a demonstration: only Theme is wired up for
  real; the rest showcases what a settings page can look like when you adapt the
  kit. It is the in-repo form-UX exemplar the run form mirrors
- **Theme** (real): editing and saving applies + persists it (`next-themes`)
- Profile/preference fields are demo-only (`localStorage`), and the Danger Zone
  runs no real delete
- See: [Settings](features/settings.md)
