"""
Admin endpoints for system maintenance tasks.
These endpoints should be protected in production.
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
from src.routes.analytics import _tile_cache, clear_tile_cache

router = APIRouter(prefix="/admin", tags=["Admin"])

logger = logging.getLogger(__name__)


class RefreshResponse(BaseModel):
    success: bool
    message: str
    timestamp: str
    details: dict | None = None


class CacheStatusResponse(BaseModel):
    tile_cache_size: int
    timestamp: str


@router.post("/refresh-pois", response_model=RefreshResponse)
def refresh_poi_materialized_view(
    db: Annotated[Session, Depends(get_db_session)],
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

        # Clear tile cache to serve fresh data
        cleared_count = clear_tile_cache()

        logger.info(
            f"mat_all_pois refreshed successfully. Cleared {cleared_count} cached tiles."
        )

        return RefreshResponse(
            success=True,
            message="POI materialized view refreshed successfully",
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            details={
                "view_name": "mat_all_pois",
                "tiles_cleared": cleared_count,
            },
        )
    except SQLAlchemyError:
        logger.exception("Failed to refresh materialized view")
        raise HTTPException(
            status_code=500,
            detail="Failed to refresh materialized view. Check server logs for details.",
        ) from None


@router.post("/clear-tile-cache", response_model=RefreshResponse)
def clear_tile_cache_endpoint():
    """
    Clear the server-side tile cache.
    Useful when you want to force fresh tile generation without refreshing the view.
    """
    cleared_count = clear_tile_cache()
    logger.info(f"Tile cache cleared. {cleared_count} tiles removed.")

    return RefreshResponse(
        success=True,
        message=f"Tile cache cleared successfully. {cleared_count} tiles removed.",
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
        details={"tiles_cleared": cleared_count},
    )


@router.get("/cache-status", response_model=CacheStatusResponse)
def get_cache_status():
    """
    Get current cache status.
    """
    return CacheStatusResponse(
        tile_cache_size=len(_tile_cache),
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
    )
