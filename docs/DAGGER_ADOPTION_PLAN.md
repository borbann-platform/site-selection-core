# Dagger Adoption Plan

## Status
- Branch: `codex/dagger-adoption`
- Scope: Introduce Dagger as orchestration for CI + MLOps workflows while keeping existing `Makefile`/scripts as fallback.
- Progress:
  - Phase 0 implemented locally (Dagger module + CI pilot functions + Make shortcuts + docs).
  - Verified: `dagger call ci-backend --silent`, `dagger call ci-frontend --silent`, `dagger call ci-all --silent`.

## What Dagger Can Do (and Why It Matters Here)
1. Pipelines as code (Python/TypeScript/Go/etc.) instead of large YAML-only logic.
   - Benefit: easier refactor/reuse across your many `gis-server/scripts/*`.
2. Run the same pipeline locally and in CI.
   - Benefit: fewer "works in CI but not local" issues.
3. Built-in caching (layers, volumes, function calls).
   - Benefit: faster `uv`, `npm`, model workflow steps.
4. Reusable Functions/Modules.
   - Benefit: standardize repeated steps (lint/test/build/train/promote).
5. First-class secrets handling.
   - Benefit: safer handling of API tokens and cloud credentials.
6. Ephemeral service containers (e.g., Postgres/Redis/etc.) in pipeline steps.
   - Benefit: cleaner integration/e2e tests and MLOps smoke checks.
7. Rich observability (TUI + traces/OpenTelemetry in Dagger Cloud).
   - Benefit: faster debugging of flaky CI and long ML steps.
8. Keep current CI provider (GitHub Actions) and invoke Dagger from it.
   - Benefit: incremental migration, low disruption.

## Fit Assessment for This Repository
- Strong fit for:
  - Backend CI (`ruff`, `pytest unit/integration` with Postgres service).
  - Frontend CI (`npm ci`, lint/test/build).
  - MLOps orchestration (`train -> evaluate -> gate -> promote -> leaderboard`).
- Medium fit for:
  - Release automation and image builds.
- Low/optional fit for now:
  - Rewriting all one-off data ETL scripts.

## Adoption Strategy (Incremental)

## Phase 0: Pilot Skeleton (1 PR)
- Deliverables:
  - [x] Add Dagger module in repo root (Python SDK recommended to match backend).
  - [x] Add baseline functions:
    - `ci-backend`
    - `ci-frontend`
    - `ci-all` (run both, parallel where safe)
  - [x] Keep current GitHub workflow as source of truth.
- Exit criteria:
  - [x] Local `dagger call ci-all` passes.
  - [x] Results are CI-parity for test/build flow (lint remains optional in backend, matching current non-blocking lint policy).

## Phase 1: CI Migration-in-Place (1 PR)
- Deliverables:
  - Update `.github/workflows/test.yml` to call Dagger functions for jobs.
  - Keep existing job names/check names unchanged.
  - Add cache volume strategy for:
    - Python (`uv`/pip caches)
    - Node (`npm` cache)
- Exit criteria:
  - CI green for 3+ PRs consecutively.
  - Measurable runtime improvement or equal runtime with better debuggability.

## Phase 2: MLOps Workflow Orchestration (1 PR)
- Deliverables:
  - Add Dagger functions to orchestrate existing scripts:
    - `ml-train-baseline`
    - `ml-train-hgt`
    - `ml-promote` (wrap strict gate script)
    - `ml-leaderboard`
  - Keep your existing scripts as underlying execution units.
  - Add one manual GitHub Action that triggers Dagger MLOps function(s).
- Exit criteria:
  - Manual trigger runs end-to-end and publishes artifacts/reports.
  - Promotion behavior remains strict and identical to current gate logic.

## Phase 3: Developer Experience Consolidation (optional, 1 PR)
- Deliverables:
  - Add `make dagger-ci`, `make dagger-mlops` shortcuts.
  - Add troubleshooting docs and a migration matrix:
    - old command -> new Dagger function.
- Exit criteria:
  - New contributors can run CI flow locally with one command.

## Concrete Function Map for Current Project
- `ci_backend`:
  - checkout src -> install uv deps -> ruff check -> pytest unit -> pytest integration (with Postgres service).
- `ci_frontend`:
  - checkout frontend -> npm ci -> lint -> test -> build.
- `ci_all`:
  - run `ci_backend` + `ci_frontend` and aggregate status.
- `ml_train_baseline`:
  - call `python -m scripts.train_baseline_mlflow` with dataset/version args.
- `ml_train_hgt`:
  - call `python -m scripts.train_hgt_mlflow` and optional pipeline args.
- `ml_promote`:
  - call `python -m scripts.promote_model --run-id ...`.
- `ml_leaderboard`:
  - call `python -m scripts.export_experiment_leaderboard ...`.

## Productivity Gains to Expect
1. Less duplicated YAML/script wiring.
2. Faster feedback from cache reuse.
3. Better local reproducibility for CI + ML checks.
4. Better failure diagnosis with trace-level visibility.
5. Cleaner path to scale model experiments without ad-hoc command sprawl.

## Risks and Mitigations
1. Learning curve for team.
   - Mitigation: keep Make/script commands as compatibility layer.
2. CI behavior drift during migration.
   - Mitigation: phased rollout, keep legacy workflow until parity proven.
3. Cache confusion / invalidation bugs.
   - Mitigation: document cache keys and add explicit bust flag.
4. Over-engineering early.
   - Mitigation: start with CI + MLOps orchestration only.

## Recommended Decision on Data Versioning (DVC)
- Recommendation: defer DVC until Phase 2 is stable.
- Reason: biggest immediate gain is orchestration/reproducibility of existing MLflow-based workflow; dataset versioning can be introduced after stable Dagger path.
