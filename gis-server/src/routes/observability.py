"""Observability endpoints for metrics and cache visibility."""

from fastapi import APIRouter, Response

from src.routes.analytics import get_analytics_cache_stats
from src.routes.listings import get_listings_tile_cache_stats
from src.config.database import db_pool_metrics
from src.services.agent_graph import agent_service
from src.services.conversation_memory import conversation_memory
from src.services.location_intelligence import location_intelligence_service
from src.services.cache_backend import cache_backend
from src.services.observability import (
    cache_backend_metrics,
    location_intelligence_metrics,
    request_metrics,
)
from src.services.listings_tile_refresh import listings_tile_refresh_manager

router = APIRouter(prefix="/observability", tags=["Observability"])


@router.get("/metrics")
def get_metrics() -> Response:
    """Prometheus-style metrics endpoint for request and cache telemetry."""
    request_metrics_payload = request_metrics.render_prometheus()
    location_stats = location_intelligence_service.get_cache_stats()
    conversation_stats = conversation_memory.get_cache_stats()
    agent_runtime_stats = agent_service.get_cache_stats()
    analytics_cache_stats = get_analytics_cache_stats()
    listings_tile_cache_stats = get_listings_tile_cache_stats()

    selected_backend = cache_backend.backend_name
    cache_lines = [
        "# HELP cache_backend_selected Selected cache backend mode",
        "# TYPE cache_backend_selected gauge",
        f'cache_backend_selected{{backend="memory"}} {1 if selected_backend == "memory" else 0}',
        f'cache_backend_selected{{backend="redis"}} {1 if selected_backend == "redis" else 0}',
        "# HELP cache_location_intelligence_size Number of entries in location intelligence cache",
        "# TYPE cache_location_intelligence_size gauge",
        f"cache_location_intelligence_size {location_stats['size']}",
        "# HELP cache_location_intelligence_hit_rate Cache hit rate for location intelligence",
        "# TYPE cache_location_intelligence_hit_rate gauge",
        f"cache_location_intelligence_hit_rate {location_stats['hit_rate']}",
        "# HELP cache_conversation_sessions Number of in-memory conversation sessions",
        "# TYPE cache_conversation_sessions gauge",
        f"cache_conversation_sessions {conversation_stats['sessions']}",
        "# HELP cache_conversation_hit_rate Cache hit rate for conversation history",
        "# TYPE cache_conversation_hit_rate gauge",
        f"cache_conversation_hit_rate {conversation_stats['cache_hit_rate']}",
        "# HELP cache_agent_runtime_entries Number of cached agent runtime entries",
        "# TYPE cache_agent_runtime_entries gauge",
        f"cache_agent_runtime_entries {agent_runtime_stats['entries']}",
        "# HELP cache_agent_runtime_hit_rate Cache hit rate for runtime model cache",
        "# TYPE cache_agent_runtime_hit_rate gauge",
        f"cache_agent_runtime_hit_rate {agent_runtime_stats['hit_rate']}",
    ]

    tile_stats = analytics_cache_stats["tile_cache"]
    df_stats = analytics_cache_stats["dataframe_cache"]
    tile_refresh_stats = listings_tile_refresh_manager.get_stats()
    cache_lines.extend(
        [
            "# HELP cache_analytics_tile_size Number of entries in analytics tile cache",
            "# TYPE cache_analytics_tile_size gauge",
            f"cache_analytics_tile_size {tile_stats['size']}",
            "# HELP cache_analytics_tile_hit_rate Tile cache hit rate",
            "# TYPE cache_analytics_tile_hit_rate gauge",
            f"cache_analytics_tile_hit_rate {tile_stats['hit_rate']}",
            "# HELP cache_analytics_dataframe_size Number of entries in analytics dataframe cache",
            "# TYPE cache_analytics_dataframe_size gauge",
            f"cache_analytics_dataframe_size {df_stats['size']}",
            "# HELP cache_analytics_dataframe_hit_rate Dataframe cache hit rate",
            "# TYPE cache_analytics_dataframe_hit_rate gauge",
            f"cache_analytics_dataframe_hit_rate {df_stats['hit_rate']}",
            "# HELP cache_analytics_dataframe_evictions Total evictions from dataframe cache",
            "# TYPE cache_analytics_dataframe_evictions counter",
            f"cache_analytics_dataframe_evictions {df_stats['evictions']}",
            "# HELP cache_listings_tile_size Number of entries in listings tile cache",
            "# TYPE cache_listings_tile_size gauge",
            f"cache_listings_tile_size {listings_tile_cache_stats['size']}",
            "# HELP cache_listings_tile_hit_rate Listings tile cache hit rate",
            "# TYPE cache_listings_tile_hit_rate gauge",
            f"cache_listings_tile_hit_rate {listings_tile_cache_stats['hit_rate']}",
            "# HELP listings_tile_source_refresh_success_total Total successful listings tile source refreshes",
            "# TYPE listings_tile_source_refresh_success_total counter",
            f"listings_tile_source_refresh_success_total {tile_refresh_stats.total_success}",
            "# HELP listings_tile_source_refresh_failure_total Total failed listings tile source refreshes",
            "# TYPE listings_tile_source_refresh_failure_total counter",
            f"listings_tile_source_refresh_failure_total {tile_refresh_stats.total_failure}",
            "# HELP listings_tile_source_refresh_duration_seconds Last listings tile source refresh duration",
            "# TYPE listings_tile_source_refresh_duration_seconds gauge",
            f"listings_tile_source_refresh_duration_seconds {tile_refresh_stats.last_duration_seconds:.6f}",
            "# HELP listings_tile_source_age_seconds Age of last successful listings tile source refresh",
            "# TYPE listings_tile_source_age_seconds gauge",
            f"listings_tile_source_age_seconds {tile_refresh_stats.age_seconds if tile_refresh_stats.last_success_epoch > 0 else 0}",
            "# HELP listings_tile_source_stale Whether listings tile source is stale",
            "# TYPE listings_tile_source_stale gauge",
            f"listings_tile_source_stale {1 if tile_refresh_stats.stale else 0}",
        ]
    )

    db_payload = db_pool_metrics.render_prometheus()
    location_intelligence_payload = location_intelligence_metrics.render_prometheus()
    cache_backend_payload = cache_backend_metrics.render_prometheus()
    payload = (
        request_metrics_payload
        + "\n"
        + db_payload
        + "\n"
        + location_intelligence_payload
        + "\n"
        + cache_backend_payload
        + "\n"
        + "\n".join(cache_lines)
        + "\n"
    )
    return Response(content=payload, media_type="text/plain; version=0.0.4")
