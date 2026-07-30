<!-- last_verified: 2026-07-30 -->
# Feature: Dashboard

## Purpose
Give an at-a-glance MLOps overview of fine-tuning runs and the artifacts they
version on Backblaze B2, including the cumulative artifact-storage curve.

## Used By
- UI: `/` page (dashboard home)
- API: `GET /runs/stats`, `GET /runs`

## Core Functions
- `apps/web/src/components/dashboard/stats-cards.tsx` — 4 stat cards (runs,
  completed, artifacts on B2, storage on B2), plus the loading notice
- `apps/web/src/components/dashboard/artifact-growth-chart.tsx` — area chart of
  cumulative artifact bytes over time (the accumulating-artifact curve)
- `apps/web/src/components/dashboard/recent-runs-table.tsx` — the 8 most recent
  runs with status and final loss
- `apps/web/src/lib/queries.ts` — `useRunStats()`, `useRuns()` (both poll while a
  run is active)
- `services/api/app/service/runs.py` — `get_run_stats()` aggregation
- `services/api/app/service/run_view.py` — `build_stats()` (the cumulative curve)

## Canonical Files
- Pattern exemplar: `apps/web/src/components/dashboard/artifact-growth-chart.tsx`

## Inputs
- None (reads scoped listings of the app's own `runs/` prefix)

## Outputs
- `GET /runs/stats` → `RunStats` (totals, status breakdown, `cumulative[]`)
- `GET /runs` → `RunSummary[]` for the recent-runs table (newest first)

## Flow
- Page loads → stats cards read `GET /runs/stats` (aggregated from each run's
  manifest plus a scoped `runs/` listing).
- The growth chart plots `RunStats.cumulative` — per-day cumulative artifact
  bytes, which only grows as runs accumulate on B2.
- The recent-runs table reads `GET /runs` and links each row to its detail.
- All aggregations flow through the `runtime -> service -> repo` layering and are
  exposed via TanStack Query hooks (no bare `useEffect + fetch`). Both queries
  poll on an interval so a training run's numbers update live.

## Edge Cases
- No runs yet → empty states on every card/chart/table.
- API unreachable → inline `ErrorState` with Retry (never fabricated zeros).
- A run in progress → stats reflect only the checkpoints already written to B2.

## UX States
- Empty: "No runs yet" / "No artifacts yet".
- Loading: skeletons + a loading notice for the (rare) cold scan.
- Error: inline error state with Retry.
- Loaded: populated cards, growth curve, recent-runs table.

## Verification
- Test files: `apps/web/src/lib/queries.test.ts`, `apps/web/src/lib/api-contract.test.ts`
- Required cases: stats render, empty state, error state
- Focused verify command: `pnpm test:web`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full` when the E2E/live prerequisites in [Dev Workflows](../dev-workflows.md#commands) are available
- Pass criteria: cards + curve + recent-runs render from live `/runs/stats` data

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [Checkpoint Versioning](checkpoint-versioning.md)
- [App Workflows](../app-workflows.md)
