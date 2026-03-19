# Sprint A Load Testing

This folder contains the baseline load test harness for Sprint A.

## Prerequisites

- Install k6: <https://k6.io/docs/get-started/installation/>
- Start backend API locally or in staging.

## Baseline Scenario

- Script: `sprint-a-baseline.js`
- Traffic mix:
  - 70% listings tile reads
  - 20% detail flow reads
  - 10% location intelligence requests
- Ramp profile:
  - 20 -> 100 VUs in 2 minutes
  - 100 -> 300 VUs in 3 minutes
  - 300 -> 100 VUs in 2 minutes

## Run

```bash
k6 run load-tests/sprint-a-baseline.js
```

Or against staging:

```bash
BASE_URL=https://your-staging-api.example.com k6 run load-tests/sprint-a-baseline.js
```

Optional warmup controls:

- `WARMUP_ENABLED=true|false` (default: `true`)
- `WARMUP_REQUESTS=<n>` (default: `120`)

Example:

```bash
BASE_URL=http://localhost:8000 WARMUP_REQUESTS=200 k6 run load-tests/sprint-a-baseline.js
```

## Required Outputs (record after each run)

- k6 summary output (latency + error rate)
- `/api/v1/observability/metrics` snapshot (before and after run)
- notes on DB pool timeout metric `db_pool_checkout_timeout_total`
