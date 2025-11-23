from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.config.database import get_db_session
from src.models.catchment import (
    CatchmentAnalysisResponse,
    CatchmentRequest,
    CatchmentResponse,
)
from src.services.catchment import catchment_service

router = APIRouter()


@router.post(
    "/catchment/analyze",
    response_model=CatchmentAnalysisResponse,
    summary="Analyze catchment area (Isochrone + Population)",
)
def analyze_catchment(payload: CatchmentRequest, db: Session = Depends(get_db_session)):
    """
    Calculates the isochrone and the population within it.
    """
    try:
        # 1. Get Isochrone
        isochrone_geom = catchment_service.get_isochrone(
            payload.latitude, payload.longitude, payload.minutes, payload.mode
        )
        if not isochrone_geom:
            raise HTTPException(
                status_code=404, detail="Could not calculate isochrone."
            )

        # 2. Calculate Population
        population = catchment_service.calculate_population(db, isochrone_geom)

        # 3. Calculate Score (Simple placeholder logic for now)
        # e.g. Score = Population / 100 (capped at 100)
        score = min(population / 100, 100.0)

        return CatchmentAnalysisResponse(
            geometry=isochrone_geom,
            population=population,
            score=round(score, 2),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/catchment/isochrone",
    response_model=CatchmentResponse,
    summary="Calculate travel time isochrone",
)
def get_isochrone(payload: CatchmentRequest):
    """
    Calculates the area reachable within a given time and mode.
    """
    try:
        result = catchment_service.get_isochrone(
            payload.latitude, payload.longitude, payload.minutes, payload.mode
        )
        if not result:
            raise HTTPException(
                status_code=404, detail="Could not calculate isochrone."
            )

        return CatchmentResponse(geometry=result, properties={})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
