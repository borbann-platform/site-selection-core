# Optimization, Observability, Reliability, and Performance Plan

This document tracks all identified optimization opportunities across backend and frontend.
Scope is to improve speed, stability, and operational visibility without breaking current behavior.

## How to Use This Plan

- Treat this as the source of truth for performance work.
- Keep changes incremental and measurable.
- Prefer low-risk, additive changes first.
- For each completed item: record before/after metrics.

## Success Metrics (Global)

- Backend API p95 latency reduced by at least 30% on top endpoints.
- Frontend LCP and INP reduced by at least 20% on main map and listing detail flows.
- Error rate less than 1% for critical endpoints.
- Cache hit rate at least 70% for cacheable workloads.
- No functional regressions in existing workflows.

## Priority 0 (Highest ROI, Start Here)

### 1) Database connection resilience and timeout controls

- Status: Completed (phase 1).
- Files:
  - `gis-server/src/config/database.py`
  - `gis-server/src/config/settings.py`
- Actions:
  - Configure SQLAlchemy pooling (`pool_pre_ping`, pool sizes, recycle, timeout). [done]
  - Apply per-session DB statement timeout. [done]
  - Add environment-controlled DB pool settings. [done]
- Implemented in:
  - `gis-server/src/config/database.py`
  - `gis-server/src/config/settings.py`
- Why:
  - Prevent stale connections and long-tail latency spikes under load.

### 2) Request-level observability baseline

- Status: Completed (phase 1).
- Files:
  - `gis-server/main.py`
- Actions:
  - Add request ID propagation (`X-Request-ID`). [done]
  - Add structured request completion and failure logs with duration. [done]
  - Standardize backend log level configuration. [done]
- Implemented in:
  - `gis-server/main.py`
- Why:
  - Needed to measure p95 latency, debug failures, and correlate incidents.

### 3) Remove backend N+1 query patterns

- Status: Completed.
- Hotspots:
  - `gis-server/src/routes/house_prices.py` [done]
  - `gis-server/src/routes/valuation.py` [done]
  - `gis-server/src/services/agent_tools.py` [done]
- Actions:
  - Inline `ST_X/ST_Y` in primary list queries instead of per-row follow-up queries. [done]
  - Validate query count reductions with benchmark logs.
- Notes:
  - Completed for house prices listing/detail, valuation user-property detail, and agent property search path.
- Why:
  - Large reduction in DB round trips and response time.

### 4) Frontend filter/query storm control

- Status: Completed (phase 1).
- Hotspots:
  - `frontend/src/hooks/usePropertyExplorer.ts`
  - `frontend/src/components/PropertyFilters.tsx`
- Actions:
  - Debounce slider-driven filter updates. [done]
  - Replace mutable object query keys with stable primitive query keys. [done]
- Implemented in:
  - `frontend/src/hooks/usePropertyExplorer.ts`
- Why:
  - Prevent excessive refetching while dragging filters.

### 5) Avoid overfetching when map tiles are active

- Status: Completed (phase 1).
- Hotspots:
  - `frontend/src/hooks/usePropertyExplorer.ts`
  - `frontend/src/hooks/useMapLayers.ts`
- Actions:
  - Gate large listing fetches by zoom tier. [done]
  - Reduce default limits and fetch only what is needed for current viewport mode. [done]
- Implemented in:
  - `frontend/src/hooks/usePropertyExplorer.ts`
- Why:
  - Reduces payload size, parse time, and memory pressure.

## Priority 1 (High Value)

### 6) Cache static/heavy analytics inputs

- Status: In progress (phase 1 implemented).
- Hotspots:
  - `gis-server/src/routes/analytics.py`
- Actions:
  - Cache parquet/csv-derived dataframes in memory with TTL and file mtime invalidation. [done]
  - Optional Redis-backed cache for multi-instance deployments.
- Implemented in:
  - `gis-server/src/routes/analytics.py`
- Why:
  - Avoid repeated disk I/O and parsing overhead on hot endpoints.

### 7) Bound all in-memory caches

- Status: In progress (phase 1 implemented).
- Hotspots:
  - `gis-server/src/services/location_intelligence.py` [done]
  - `gis-server/src/services/conversation_memory.py` [done]
  - `gis-server/src/services/agent_graph.py` [done]
  - `gis-server/src/routes/price_prediction.py` (local SHAP cache)
- Actions:
  - Add TTL + max-size eviction consistently (LRU/TTL strategy). [done for listed services]
  - Add cache hit/miss and current size metrics. [done for listed services]
- Why:
  - Prevent memory growth and stabilize long-running instances.

### 8) Spatial query index usage improvements

- Status: Pending.
- Hotspots:
  - `gis-server/src/routes/analytics.py`
  - `gis-server/src/routes/house_prices.py`
  - `gis-server/src/routes/listings.py`
  - `gis-server/src/routes/transit.py`
- Actions:
  - Avoid transforming table geometry in predicates when possible.
  - Transform envelope/bounds and compare against indexed geometry column.
- Why:
  - Better GiST index usage and lower query CPU cost.

### 9) Numeric normalization for listing filters/sorts

- Status: Pending.
- Hotspots:
  - `gis-server/src/routes/listings.py`
- Actions:
  - Replace regex-cast numeric extraction in WHERE/ORDER BY with normalized numeric columns.
  - Add indexes on normalized numeric columns.
- Why:
  - Current approach is expensive and non-index-friendly.

### 10) Frontend H3 and map rendering load

- Status: Pending.
- Hotspots:
  - `frontend/src/hooks/usePropertyExplorer.ts`
  - `frontend/src/hooks/useMapLayers.ts`
- Actions:
  - Fetch H3 cells by viewport bounds.
  - Make layer detail/pickability adaptive by zoom.
- Why:
  - Reduce GPU/CPU load and keep pan/zoom smooth.

## Priority 2 (Reliability/Operational Hardening)

### 11) Async/sync endpoint consistency

- Status: Pending.
- Hotspots:
  - `gis-server/src/routes/organizations.py`
  - `gis-server/src/routes/teams.py`
  - `gis-server/src/routes/invitations.py`
  - `gis-server/src/routes/chat_sessions.py`
- Actions:
  - For sync DB calls, prefer sync route handlers or migrate module to `AsyncSession` safely.
- Why:
  - Avoid blocking event loop under concurrent load.

### 12) Add metrics and tracing

- Status: In progress (metrics endpoint phase 1 done).
- Actions:
  - Backend Prometheus metrics: request count/latency/error, cache metrics, DB timing. [partially done]
  - OpenTelemetry traces across HTTP, DB, and model/tool boundaries.
  - Frontend Web Vitals and error telemetry wiring.
- Implemented in:
  - `gis-server/src/services/observability.py`
  - `gis-server/src/routes/observability.py`
  - `gis-server/main.py`
- Why:
  - Enables objective performance tuning and early regression detection.

### 13) Circuit-breakers, retry budgets, and timeouts for external/model calls

- Status: Pending.
- Hotspots:
  - `gis-server/src/services/chat_service.py`
  - `gis-server/src/services/agent_graph.py`
  - `gis-server/src/services/model_provider.py`
- Actions:
  - Add bounded retries for transient errors, timeout budgets, and fallback behavior.
- Why:
  - Improve reliability during provider/model instability.

### 14) Startup reliability and warmup strategy

- Status: Pending.
- Hotspots:
  - `gis-server/main.py`
  - `gis-server/src/services/catchment.py`
- Actions:
  - Move heavy startup loading to non-blocking warmup where safe.
  - Expose readiness states clearly.
- Why:
  - Faster and safer service startup in CI/deploy environments.

## Frontend-Specific Backlog (Detailed)

1. Tune React Query defaults in `frontend/src/integrations/tanstack-query/root-provider.tsx`.
2. Add long stale times for mostly static map overlays (schools/transit).
3. Batch token-stream updates in chat store to reduce render churn.
4. Memoize large chat message components and consider list virtualization for long histories.
5. Stabilize thinking indicator timers and start-time semantics.
6. Ensure devtools and debug-only dependencies are fully excluded from production builds.
7. Trim font variants and verify impact on first contentful paint.

## Backend-Specific Backlog (Detailed)

1. Add/verify indexes for frequent filters and joins:
   - house prices by district/style/price
   - organization/team membership composite keys
   - geometry GiST indexes for map and spatial routes
2. Add cursor pagination option for high-cardinality endpoints while preserving existing offset behavior.
3. Add EXPLAIN ANALYZE checks for top routes and keep SQL snapshots in docs.

## Current Work Log

### Completed in this branch (initial top-priority foundation)

- Added DB pooling and timeout settings + statement timeout setup.
- Added request-level timing and request-id logging middleware.
- Added configurable backend log level.
- Removed coordinate N+1 lookups in:
  - `gis-server/src/routes/house_prices.py`
  - `gis-server/src/routes/valuation.py`
- Added frontend performance guards in:
  - `frontend/src/hooks/usePropertyExplorer.ts`
  - filter debounce (250ms)
  - stable primitive React Query keys
  - zoom-tier listing fetch limits
- Added analytics dataframe cache:
  - TTL + file mtime invalidation
  - bounded cache size and cache stats
  - implemented in `gis-server/src/routes/analytics.py`
- Added bounded service caches and cache stats:
  - `gis-server/src/services/location_intelligence.py`
  - `gis-server/src/services/conversation_memory.py`
  - `gis-server/src/services/agent_graph.py`
- Added observability metrics endpoint:
  - `GET /api/v1/observability/metrics`
  - implemented in `gis-server/src/routes/observability.py`
  - request/counter/histogram metrics implemented in `gis-server/src/services/observability.py`
- Completed remaining N+1 cleanup in agent tools:
  - `gis-server/src/services/agent_tools.py`
- Tuned frontend React Query defaults and static overlay stale times:
  - `frontend/src/integrations/tanstack-query/root-provider.tsx`
  - `frontend/src/hooks/usePropertyExplorer.ts`

### Commits

- `61ba288` `chore(observability): add request timing and db pool safeguards`
- `a481fcf` `perf(api): remove coordinate N+1 lookups in valuation routes`
- `0d36984` `perf(frontend): debounce listing filters and stabilize query keys`

### Next immediate implementation focus

1. Add cache stats/admin visibility to existing admin cache status endpoint.
2. Add DB query timing instrumentation (simple middleware + logging buckets).
3. Extend analytics tile queries to avoid `ST_Transform(column, 3857)` in WHERE.
4. Start Redis adapter behind feature flag for distributed cache mode.
5. Add frontend Web Vitals shipping endpoint integration.

## Ready-Next Checklist

- [ ] Benchmark query counts before/after for house-price and valuation endpoints.
- [ ] Add lightweight request counters + latency histograms.
- [ ] Implement analytics dataframe cache and expose cache hit-rate logs.
- [ ] Open follow-up PR for React Query defaults + overlay staleTime tuning.
