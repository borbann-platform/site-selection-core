"""
Price prediction API endpoint.

Uses pluggable prediction service with support for:
- Baseline LightGBM model (spatial features)
- Baseline + Hex2Vec embeddings
- HGT Graph Neural Network (when available)
- Automatic model selection based on availability
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.config.database import get_db_session
from src.services.price_prediction import (
    PredictorType,
    get_available_predictors,
    get_predictor,
)

router = APIRouter(prefix="/house-prices", tags=["Price Prediction"])


class FeatureContributionResponse(BaseModel):
    """Single feature contribution to predicted price."""

    feature: str
    feature_display: str
    value: float
    contribution: float
    direction: str


class PriceExplanationResponse(BaseModel):
    """Price explanation with feature contributions."""

    property_id: int | None = None
    predicted_price: float
    confidence: float = Field(ge=0, le=1, description="Prediction confidence (0-1)")
    model_type: str = Field(description="Model used for prediction")
    actual_price: float | None = None
    feature_contributions: list[FeatureContributionResponse]
    district: str | None = None
    district_avg_price: float | None = None
    price_vs_district: float | None = None  # Percentage
    h3_index: str = Field(description="H3 hexagon index of location")
    is_cold_start: bool = Field(
        default=False, description="True if area has no transaction history"
    )


class PredictRequest(BaseModel):
    """Request for price prediction at arbitrary location."""

    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    building_area: float | None = Field(None, description="Building area in sqm")
    land_area: float | None = Field(None, description="Land area in sq wah")
    building_age: float | None = Field(None, description="Building age in years")
    no_of_floor: float | None = Field(None, description="Number of floors")
    building_style: str | None = Field(
        None, description="Building style (บ้านเดี่ยว, ทาวน์เฮ้าส์, etc.)"
    )


class ModelStatusResponse(BaseModel):
    """Status of prediction models."""

    models: list[dict]
    default_model: str | None


@router.get("/models/status", response_model=ModelStatusResponse)
def get_models_status():
    """Get status of all available prediction models."""
    available = get_available_predictors()
    default = None
    try:
        default = get_predictor().model_type.value
    except Exception:
        pass

    return ModelStatusResponse(models=available, default_model=default)


@router.get("/{property_id}/explain", response_model=PriceExplanationResponse)
def explain_price(
    property_id: int,
    model: PredictorType | None = Query(
        None, description="Model to use for prediction"
    ),
    db: Session = Depends(get_db_session),
):
    """
    Get price prediction and explanation for an existing property.

    Uses the trained baseline model (LightGBM) with spatial features.
    Optionally specify model type via query parameter.
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

    # Get predictor
    try:
        predictor = get_predictor(model)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"No prediction model available: {e}. Train baseline first.",
        )

    # Run prediction
    prediction = predictor.predict(
        db,
        lat,
        lon,
        building_area,
        land_area,
        building_age,
        no_of_floor,
        building_style,
        property_id,
    )

    return PriceExplanationResponse(
        property_id=property_id,
        predicted_price=round(prediction.predicted_price, 0),
        confidence=prediction.confidence,
        model_type=prediction.model_type,
        actual_price=actual_price,
        feature_contributions=[
            FeatureContributionResponse(
                feature=c.feature,
                feature_display=c.feature_display,
                value=c.value,
                contribution=c.contribution,
                direction=c.direction,
            )
            for c in prediction.feature_contributions
        ],
        district=prediction.district or amphur,
        district_avg_price=round(prediction.district_avg_price, 0)
        if prediction.district_avg_price
        else None,
        price_vs_district=round(prediction.price_vs_district, 1)
        if prediction.price_vs_district
        else None,
        h3_index=prediction.h3_index,
        is_cold_start=prediction.is_cold_start,
    )


@router.post("/predict", response_model=PriceExplanationResponse)
def predict_price(
    request: PredictRequest,
    model: PredictorType | None = Query(
        None, description="Model to use for prediction"
    ),
    db: Session = Depends(get_db_session),
):
    """
    Predict price for a new property at given location.

    Provide coordinates and optional property attributes.
    Uses the best available model (HGT > Baseline+Hex2Vec > Baseline).
    """
    try:
        predictor = get_predictor(model)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"No prediction model available: {e}. Train baseline first.",
        )

    prediction = predictor.predict(
        db,
        request.lat,
        request.lon,
        request.building_area,
        request.land_area,
        request.building_age,
        request.no_of_floor,
        request.building_style,
    )

    return PriceExplanationResponse(
        predicted_price=round(prediction.predicted_price, 0),
        confidence=prediction.confidence,
        model_type=prediction.model_type,
        feature_contributions=[
            FeatureContributionResponse(
                feature=c.feature,
                feature_display=c.feature_display,
                value=c.value,
                contribution=c.contribution,
                direction=c.direction,
            )
            for c in prediction.feature_contributions
        ],
        district=prediction.district,
        district_avg_price=round(prediction.district_avg_price, 0)
        if prediction.district_avg_price
        else None,
        price_vs_district=round(prediction.price_vs_district, 1)
        if prediction.price_vs_district
        else None,
        h3_index=prediction.h3_index,
        is_cold_start=prediction.is_cold_start,
    )
