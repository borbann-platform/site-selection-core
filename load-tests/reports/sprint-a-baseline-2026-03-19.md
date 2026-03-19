# Sprint A Baseline Capacity Report

Date: 2026-03-19

Environment: local dev (single uvicorn process), Postgres local, then PgBouncer local

Commit SHA: working tree (not yet committed)

## Scenario

- Script: `load-tests/sprint-a-baseline.js`
- Base URL: `http://localhost:8000`
- Duration: ~7 minutes + graceful stop
- Max VUs reached: 300

## Run A (direct DB, no PgBouncer)

- k6 summary file: `/tmp/sprint-a-k6-summary.json`
- `http_req_failed`: `0.1821`
- `http_req_duration p95`: `42597.9654 ms`
- `checks`: `0.9914`
- `http_reqs`: `3685`
- `iterations`: `3062`

Observability snapshot (post-run): `/tmp/sprint-a-metrics.prom`

- `api_requests_total`: `3724`
- `api_request_errors_total`: `0`
- `db_pool_size`: `20`
- `db_pool_checked_out`: `0`
- `db_pool_overflow`: `0`
- `db_pool_checkout_timeout_total`: `0`
- `cache_listings_tile_hit_rate`: `0.0128`
- `cache_location_intelligence_hit_rate`: `0.0067`

## Run B (through PgBouncer)

- k6 summary file: `/tmp/sprint-a-k6-summary-pgbouncer.json`
- `http_req_failed`: `1.0`
- `http_req_duration p95`: `60001.1656 ms`
- `checks`: `0.1014`
- `http_reqs`: `1442`
- `iterations`: `1206`

Observability snapshot (post-run): `/tmp/sprint-a-metrics-fallback.prom`

- `api_requests_total`: `1231`
- `api_request_errors_total`: `935`
- `db_pool_size`: `20`
- `db_pool_checked_out`: `21`
- `db_pool_overflow`: `1`
- `db_pool_checkout_timeout_total`: `0`
- `cache_listings_tile_hit_rate`: `0.0`
- `cache_location_intelligence_hit_rate`: `0.0086`

## Findings

- PgBouncer path is currently misconfigured: backend logs show `server login failed: wrong password type` from PgBouncer to Postgres.
- This authentication mismatch causes widespread request timeout/failure and invalidates PgBouncer performance assessment.
- Without PgBouncer, timeout pressure still appears at high VU due to single-process local server and heavy endpoint mix.
- Listings tile cache hit rate remains near zero in this run, likely due to random tile distribution and no warmup phase.

## Run C (through PgBouncer after SCRAM fix)

- k6 summary file: `/tmp/sprint-a-k6-summary-pgbouncer-fixed.json`
- `http_req_failed` (`value`): `0.1775`
- `http_req_duration p95`: `47689.1495 ms`
- `checks` (`value`): `0.9891`
- `http_reqs`: `3431`
- `iterations`: `2879`

Observability snapshot (post-run): `/tmp/sprint-a-metrics-after-fixed.prom`

- `api_requests_total`: `3478`
- `api_request_errors_total`: `0`
- `db_pool_size`: `20`
- `db_pool_checked_out`: `0`
- `db_pool_overflow`: `0`
- `db_pool_checkout_timeout_total`: `0`
- `cache_listings_tile_hit_rate`: `0.01`
- `cache_location_intelligence_hit_rate`: `0.0`

Additional notes:

- PgBouncer auth mismatch is fixed (`auth_type=scram-sha-256`), and login failures are no longer observed.
- Despite auth recovery, p95 latency remains very high under this local profile; current bottleneck is now endpoint/service throughput, not pool auth.
- k6 summary `thresholds` flags in JSON may report `true` even when observed values violate targets; use raw metric values (`value`, `p(95)`) for gate decisions.

## Decision

- Sprint A gate: **Fail** (PgBouncer not yet operational in this environment).
- Next action:
  1. Fix PgBouncer auth mode compatibility with Postgres (`auth_type`, password hashing config, userlist).
  2. Re-run Sprint A baseline with warmup stage for tile cache.
  3. Re-capture before/after metrics and compare with same traffic seed/profile.

## Updated Decision (after Run C)

- Sprint A gate: **Fail** (PgBouncer operational, but latency/error SLO not met).
- Next action:
  1. Reduce `location-intelligence` request cost (query consolidation and cache effectiveness).
  2. Re-run Sprint A with warmup-enabled script and compare cache-hit deltas.
  3. Validate on multi-worker/staging profile to separate local single-process limits from code-path limits.

## Run D (Option 1 rerun before server restart)

- k6 summary file: `/tmp/sprint-a-k6-summary-option1-rerun.json`
- `http_req_failed` (`value`): `0.1724`
- `http_req_duration avg`: `17758.4175 ms`
- `http_req_duration p95`: `45263.9858 ms`
- `checks` (`value`): `0.9902`
- `http_reqs`: `3840`
- `iterations`: `3113`

## Run E (Option 1 rerun after server restart with latest metrics code)

- k6 summary file: `/tmp/sprint-a-k6-summary-option1-rerun-after-restart.json`
- `http_req_failed` (`value`): `0.1653`
- `http_req_duration avg`: `14918.2251 ms`
- `http_req_duration p95`: `39671.5316 ms`
- `checks` (`value`): `0.9973`
- `http_reqs`: `4525`
- `iterations`: `3670`

Observability snapshot (post-run): `/tmp/sprint-a-metrics-option1-rerun-after-restart.prom`

- `api_requests_total`: `4556`
- `api_request_errors_total`: `4`
- `db_query_total`: `5835`
- `db_query_errors_total`: `1093`
- `cache_listings_tile_hit_rate`: `0.0599`
- `cache_location_intelligence_hit_rate`: `0.0055`

Location intelligence stage timings (new per-stage metrics):

- `analyze_total`: total `365`, avg `0.7898 s`
- `transit`: total `363`, avg `0.7583 s`
- `schools`: total `363`, avg `0.0123 s`
- `walkability`: total `363`, avg `0.0087 s`
- `flood`: total `363`, avg `0.0077 s`
- `noise`: total `363`, avg `0.0071 s`

Interpretation:

- Run E improved over Run C on all primary top-line metrics (error rate, avg latency, p95, throughput) but still misses Sprint A SLO targets.
- New stage-level observability identifies `transit` as the dominant location-intelligence latency contributor in this profile.
- `walkability` is no longer the primary per-request bottleneck after query consolidation and spatial index prefiltering.

## Updated Decision (after Runs D/E)

- Sprint A gate: **Fail** (improved, but still above p95 and failure targets).
- Next action:
  1. Optimize transit score path further (query shape/index strategy and/or bounded radius policy) and re-test.
  2. Reduce DB query error volume observed in Run E (`db_query_errors_total=1093`) and classify root causes.
  3. Validate with multi-worker/staging profile to remove single-process local ceiling from decision quality.

## Run F (Sprint A after transit-query rewrite + transaction-recovery fix)

- k6 summary file: `/tmp/sprint-a-k6-summary-sprint-a-transit-fix.json`
- `http_req_failed` (`value`): `0.1590`
- `http_req_duration avg`: `15635.4773 ms`
- `http_req_duration p95`: `37167.72 ms`
- `checks` (`value`): `1.0`
- `http_reqs`: `4321`
- `iterations`: `3513`

Observability snapshot (post-run): `/tmp/sprint-a-metrics-sprint-a-transit-fix.prom`

- `api_requests_total`: `4336`
- `api_request_errors_total`: `0`
- `db_query_total`: `5734`
- `db_query_errors_total`: `0` (fixed from prior 1093 by removing SQL syntax error + rollback recovery)
- `cache_listings_tile_hit_rate`: `0.0591`
- `cache_location_intelligence_hit_rate`: `0.0`

Location intelligence stage timing (Run F):

- `analyze_total` avg: `0.8113 s`
- `transit` avg: `0.7576 s` (still dominant)
- `schools` avg: `0.0101 s`
- `walkability` avg: `0.0240 s`
- `flood` avg: `0.0081 s`
- `noise` avg: `0.0112 s`

Delta vs Run E (`/tmp/sprint-a-k6-summary-option1-rerun-after-restart.json`):

- `http_req_failed`: `0.1653 -> 0.1590` (`-3.82%`)
- `http_req_duration p95`: `39671.53ms -> 37167.72ms` (`-6.31%`)
- `http_req_duration avg`: `14918.23ms -> 15635.48ms` (`+4.81%`)

Interpretation:

- Transit query rewrite and transaction recovery removed DB query-error noise and improved p95/failure rate.
- Sprint A remains SLO-fail in local profile, but now with cleaner metrics and a confirmed dominant hotspot (`transit` stage).
