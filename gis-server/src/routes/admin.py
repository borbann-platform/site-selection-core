"""
Admin endpoints for system maintenance tasks.
These endpoints require system administrator access.
"""

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.config.database import get_db_session
from src.dependencies.permissions import require_system_admin
from src.models.user import User
from src.routes.analytics import clear_tile_cache, get_analytics_cache_stats
from src.routes.listings import clear_listings_tile_cache
from src.services.location_intelligence import location_intelligence_service
from src.services.listings_tile_refresh import listings_tile_refresh_manager

router = APIRouter(prefix="/admin", tags=["Admin"])

logger = logging.getLogger(__name__)


class RefreshResponse(BaseModel):
    success: bool
    message: str
    timestamp: str
    details: dict | None = None


class CacheStatusResponse(BaseModel):
    analytics_tile_cache_size: int
    listings_tile_cache_size: int
    location_intelligence_cache_size: int
    listings_tile_source_last_success: str | None = None
    listings_tile_source_age_seconds: float | None = None
    listings_tile_source_stale: bool | None = None
    timestamp: str


@router.post("/refresh-pois", response_model=RefreshResponse)
def refresh_poi_materialized_view(
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(require_system_admin)],
):
    """
    Refresh the mat_all_pois materialized view.
    This updates the POI data from all source tables.
    Should be called after POI data is updated.
    """
    try:
        logger.info("Starting refresh of mat_all_pois materialized view...")

        # Refresh materialized view using session execute
        db.execute(text("REFRESH MATERIALIZED VIEW mat_all_pois"))
        db.commit()

        # Clear relevant caches to serve fresh data
        cleared_analytics = clear_tile_cache()
        cleared_listings = clear_listings_tile_cache()
        cleared_locint = location_intelligence_service.clear_cache()
        cleared_count = max(cleared_analytics, cleared_listings, cleared_locint)

        logger.info(
            f"mat_all_pois refreshed successfully. Cleared {cleared_count} cached tiles."
        )

        return RefreshResponse(
            success=True,
            message="POI materialized view refreshed successfully",
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            details={
                "view_name": "mat_all_pois",
                "analytics_tiles_cleared": cleared_analytics,
                "listings_tiles_cleared": cleared_listings,
                "location_intelligence_cleared": cleared_locint,
                "max_cleared": cleared_count,
            },
        )
    except SQLAlchemyError:
        logger.exception("Failed to refresh materialized view")
        raise HTTPException(
            status_code=500,
            detail="Failed to refresh materialized view. Check server logs for details.",
        ) from None


@router.post("/clear-tile-cache", response_model=RefreshResponse)
def clear_tile_cache_endpoint(
    current_user: Annotated[User, Depends(require_system_admin)],
):
    """
    Clear the server-side tile cache.
    Useful when you want to force fresh tile generation without refreshing the view.
    """
    cleared_analytics = clear_tile_cache()
    cleared_listings = clear_listings_tile_cache()
    cleared_locint = location_intelligence_service.clear_cache()
    cleared_count = max(cleared_analytics, cleared_listings, cleared_locint)
    logger.info(
        "Caches cleared analytics=%s listings=%s location_intelligence=%s",
        cleared_analytics,
        cleared_listings,
        cleared_locint,
    )


@router.post("/refresh-listings-tile-source", response_model=RefreshResponse)
def refresh_listings_tile_source(
    current_user: Annotated[User, Depends(require_system_admin)],
):
    """Refresh materialized listings tile source and clear listings tile cache."""
    try:
        listings_tile_refresh_manager.refresh_now(concurrent=True)
        cleared_listings = clear_listings_tile_cache()
        stats = listings_tile_refresh_manager.get_stats()
        return RefreshResponse(
            success=True,
            message="Listings tile materialized source refreshed",
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            details={
                "listings_tiles_cleared": cleared_listings,
                "last_success": stats.last_success_iso,
                "last_duration_seconds": round(stats.last_duration_seconds, 3),
                "refresh_failures": stats.total_failure,
            },
        )
    except Exception:
        logger.exception("Failed to refresh listings tile materialized source")
        raise HTTPException(
            status_code=500,
            detail="Failed to refresh listings tile source. Check server logs for details.",
        ) from None

    return RefreshResponse(
        success=True,
        message="Caches cleared successfully",
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
        details={
            "analytics_tiles_cleared": cleared_analytics,
            "listings_tiles_cleared": cleared_listings,
            "location_intelligence_cleared": cleared_locint,
            "max_cleared": cleared_count,
        },
    )


@router.get("/cache-status", response_model=CacheStatusResponse)
def get_cache_status(
    current_user: Annotated[User, Depends(require_system_admin)],
):
    """
    Get current cache status.
    """
    from src.routes.listings import get_listings_tile_cache_stats

    analytics_size = int(get_analytics_cache_stats()["tile_cache"]["size"])
    listings_size = int(get_listings_tile_cache_stats().get("size", 0))
    location_size = int(location_intelligence_service.get_cache_stats().get("size", 0))
    tile_refresh_stats = listings_tile_refresh_manager.get_stats()

    return CacheStatusResponse(
        analytics_tile_cache_size=analytics_size,
        listings_tile_cache_size=listings_size,
        location_intelligence_cache_size=location_size,
        listings_tile_source_last_success=tile_refresh_stats.last_success_iso or None,
        listings_tile_source_age_seconds=round(tile_refresh_stats.age_seconds, 3)
        if tile_refresh_stats.last_success_epoch > 0
        else None,
        listings_tile_source_stale=tile_refresh_stats.stale,
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
    )
