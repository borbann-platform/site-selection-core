"""Location Intelligence API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.config.database import get_db_session
from src.models.location_intelligence import (
    LocationIntelligenceResponse,
    LocationRequest,
)
from src.services.location_intelligence import location_intelligence_service

router = APIRouter()


@router.post(
    "/location-intelligence/analyze",
    response_model=LocationIntelligenceResponse,
    summary="Analyze location intelligence for a geographic point",
    description="""
    Calculates comprehensive location intelligence scores including:
    - **Transit Score**: Proximity to BTS/MRT, bus stops, ferry
    - **Walkability Score**: Nearby amenities (restaurants, cafes, shops, etc.)
    - **Schools Score**: Educational facilities within range
    - **Flood Risk**: Based on district flood warning data
    - **Noise Level**: Estimated from proximity to major roads
    - **Composite Score**: Weighted average of all factors
    
    Results are cached by location grid cell (~100m precision) for performance.
    """,
)
def analyze_location(
    payload: LocationRequest, db: Session = Depends(get_db_session)
) -> LocationIntelligenceResponse:
    """Analyze location intelligence for a given coordinate."""
    return location_intelligence_service.analyze(
        db=db,
        lat=payload.latitude,
        lon=payload.longitude,
        radius=payload.radius_meters,
    )
