# Sprint A Bottleneck Optimization Report (Materialized Tile Source)

Date: 2026-03-20

## Executive Outcome

We completed the planned bottleneck optimization cycle focused on `listings` tile performance using a precomputed/materialized source with allowed staleness (5-15 minutes). The tile path is now significantly cheaper and more stable under load, with major error-rate improvement and measurable latency reduction.

Current status:

- Tile-serving reliability improved and cache behavior is healthy.
- Overall mixed-workload tail latency improved but still above strict p95 SLO.
- Optimization accepted as current stopping point per product decision.

## Scope Executed

Implemented and validated phases 1-7 of the optimization plan:

1. Baseline bottleneck confirmation
2. Materialized tile source design
3. Refresh pipeline (scheduled + manual)
4. Tile endpoint query-path refactor
5. Indexing and query support tuning
6. Load validation
7. Operational visibility and controls

## Changes Implemented

### 1) Materialized Tile Source + Refresh Lifecycle

- Added refresh manager: `gis-server/src/services/listings_tile_refresh.py`
- Introduced materialized source: `mat_listings_tile_source`
- Added supporting indexes:
  - unique index on `listing_key`
  - GiST index on `geom_3857`
  - filter index (`source_type`, `amphur`, `building_style_desc`)
  - price/area index (`total_price`, `building_area`)
- Added advisory locks to avoid concurrent worker DDL/refresh races.
- Added periodic refresh with default 10-minute cadence and stale threshold control.

### 2) App Lifecycle Integration

- Startup/shutdown integration in `gis-server/main.py`:
  - starts tile refresh manager
  - stops manager on shutdown

### 3) Tile Endpoint Refactor

- Updated `GET /api/v1/listings/tile/{z}/{x}/{y}` in `gis-server/src/routes/listings.py`:
  - moved from runtime heavy multi-source union to `mat_listings_tile_source`
  - retained existing filters (district/style/price/area)
  - retained Redis tile cache behavior (`X-Cache`, TTL)

### 4) Admin and Observability Enhancements

- Added manual refresh endpoint in `gis-server/src/routes/admin.py`:
  - `POST /api/v1/admin/refresh-listings-tile-source`
- Extended cache-status response with tile source freshness metadata.
- Added tile source refresh/freshness metrics in `gis-server/src/routes/observability.py`:
  - `listings_tile_source_refresh_success_total`
  - `listings_tile_source_refresh_failure_total`
  - `listings_tile_source_refresh_duration_seconds`
  - `listings_tile_source_age_seconds`
  - `listings_tile_source_stale`

### 5) Configuration

- Added settings in `gis-server/src/config/settings.py`:
  - `LISTINGS_TILE_MATVIEW_REFRESH_SECONDS` (default `600`)
  - `LISTINGS_TILE_MATVIEW_STALE_SECONDS` (default `900`)

## Validation Results

## Functional Validation

- Tile endpoint returns successfully and cache headers remain active.
- Cold/warm sample behavior:
  - cold tile request observed around `~46ms`
  - warm tile request observed around `~2ms`
- Materialized refresh metrics are visible in Prometheus and backend metrics endpoint.

## Load Validation (k6)

Compared moderated mixed-traffic runs before/after materialized tile source path:

- Before optimization (representative moderated run):
  - `http_req_failed`: `1.81%`
  - `http_req_duration p95`: `12.6s`
- After optimization (representative moderated run):
  - `http_req_failed`: `0.00%`
  - `http_req_duration p95`: `6.63s`

Delta summary:

- Error rate improved from non-zero to zero in the tested profile.
- Tail latency improved materially (roughly halved in this workload), though still above strict target.

## Observability Evidence

Verified post-change metrics and health:

- Prometheus backend target returns `up` after warmup.
- Tile source refresh metrics emitted and queryable.
- Example observed values during run window:
  - `listings_tile_source_refresh_success_total = 1`
  - `listings_tile_source_refresh_failure_total = 0`
  - `listings_tile_source_refresh_duration_seconds ~ 2.7-3.1`

## Known Risks / Residual Bottlenecks

- Overall mixed-workload p95 remains above strict SLO; remaining tail likely comes from non-tile expensive endpoints (notably location intelligence stages).
- Multi-worker startup still triggers repeated startup refresh attempts; advisory locks prevent conflict but add startup overhead.
- Local workspace contains substantial unrelated generated artifacts; keep release scope controlled when staging commits.

## Final Decision for This Cycle

Given product acceptance for current optimization scope:

- **Accepted**: materialized tile source optimization is complete and operational.
- **Deferred**: next latency reduction wave (location intelligence query/stage optimization and deeper endpoint-specific load shaping).

## Recommended Next Wave (When Resumed)

1. Optimize `location_intelligence` hotspots (`transit`, `noise`) using bounded/index-friendly spatial patterns.
2. Add endpoint-specific k6 thresholds to isolate tail contributors faster.
3. Move refresh scheduling to a singleton worker/job model to avoid duplicate startup refresh attempts.
4. Re-run stress + soak to establish an updated safe concurrency ceiling.
