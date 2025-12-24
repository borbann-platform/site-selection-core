"""Price prediction API endpoint with SHAP explanations."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.config.database import get_db_session
from src.services.price_prediction import price_prediction_service

router = APIRouter(prefix="/house-prices", tags=["Price Prediction"])


class FeatureContributionResponse(BaseModel):
    """Single feature contribution to predicted price."""

    feature: str
    feature_display: str
    value: float
    contribution: float
    direction: str


class PriceExplanationResponse(BaseModel):
    """Price explanation with SHAP-based feature contributions."""

    property_id: int
    predicted_price: float
    base_price: float
    actual_price: float | None
    feature_contributions: list[FeatureContributionResponse]
    district_avg_price: float
    price_vs_district: float  # Percentage


@router.get("/{property_id}/explain", response_model=PriceExplanationResponse)
def explain_price(
    property_id: int,
    db: Session = Depends(get_db_session),
):
    """
    Get price explanation for a property.

    Returns predicted price with SHAP-based feature contributions showing
    which factors increase or decrease the predicted value.
    """
    # Fetch property data
    result = db.execute(
        text(
            """
            SELECT id, ST_X(geometry) as lon, ST_Y(geometry) as lat,
                   building_area, land_area, building_age, no_of_floor,
                   building_style_desc, amphur, total_price
            FROM house_prices
            WHERE id = :id
            """
        ),
        {"id": property_id},
    ).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Property not found")

    (
        prop_id,
        lon,
        lat,
        building_area,
        land_area,
        building_age,
        no_of_floor,
        building_style,
        amphur,
        actual_price,
    ) = result

    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="Property has no location data")

    try:
        explanation = price_prediction_service.explain(
            db,
            property_id=prop_id,
            lat=lat,
            lon=lon,
            building_area=building_area,
            land_area=land_area,
            building_age=building_age,
            no_of_floor=no_of_floor,
            building_style=building_style,
            amphur=amphur,
            actual_price=actual_price,
            top_k=5,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return PriceExplanationResponse(
        property_id=explanation.property_id,
        predicted_price=explanation.predicted_price,
        base_price=explanation.base_price,
        actual_price=actual_price,
        feature_contributions=[
            FeatureContributionResponse(
                feature=c.feature,
                feature_display=c.feature_display,
                value=c.value,
                contribution=c.contribution,
                direction=c.direction,
            )
            for c in explanation.feature_contributions
        ],
        district_avg_price=explanation.district_avg_price,
        price_vs_district=explanation.price_vs_district,
    )
