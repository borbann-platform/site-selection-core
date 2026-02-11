# Dagger Pilot (Phase 0)

This repository now includes a Dagger module for CI parity checks.

## Installed Functions
- `ci-backend`: backend dependency sync + unit/integration tests (optional lint flag).
- `ci-frontend`: frontend install + lint + test + build.
- `ci-all`: runs backend then frontend checks.

## Quick Usage
From repo root:

```bash
dagger functions
dagger call ci-backend --silent
dagger call ci-frontend --silent
dagger call ci-all --silent
```

Or via Make shortcuts:

```bash
make dagger-ci-backend
make dagger-ci-frontend
make dagger-ci
```

## Notes
- Backend integration tests run with an ephemeral PostGIS service inside Dagger.
- This is an additive pilot; existing GitHub Actions and script/Make flows remain unchanged.
- Dagger module source lives under `.dagger/` with configuration in `dagger.json`.
