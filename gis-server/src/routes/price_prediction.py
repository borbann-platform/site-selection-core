"""
Price prediction API endpoint.

Uses pluggable prediction service with support for:
- Baseline LightGBM model (spatial features)
- Baseline + Hex2Vec embeddings
- HGT Graph Neural Network (when available)
- Automatic model selection based on availability
"""

import hashlib
import json
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.database import get_db_session
from src.dependencies.auth import get_current_user_optional
from src.models.user import User
from src.services.explainability_artifacts import load_explainability_evidence
from src.services.explanation_narration import generate_natural_language_explanation
from src.services.price_prediction import (
    PredictorType,
    get_available_predictors,
    get_predictor,
)

router = APIRouter(prefix="/house-prices", tags=["Price Prediction"])

_local_shap_cache: dict[str, tuple[dict, float]] = {}
_LOCAL_SHAP_CACHE_TTL_SECONDS = 900
_LOCAL_SHAP_CACHE_MAX_SIZE = 300


class FeatureContributionResponse(BaseModel):
    """Single feature contribution to predicted price."""

    feature: str
    feature_display: str
    value: float
    direction: str
    contribution: float
    contribution_kind: str = Field(
        description="How to interpret the contribution value"
    )
    contribution_display: str | None = Field(
        default=None,
        description="Human-readable contribution label for the UI",
    )


class PriceExplanationResponse(BaseModel):
    """Price explanation with feature contributions."""

    property_id: int | None = None
    predicted_price: float
    confidence: float = Field(ge=0, le=1, description="Prediction confidence (0-1)")
    model_type: str = Field(description="Model used for prediction")
    actual_price: float | None = None
    feature_contributions: list[FeatureContributionResponse]
    explanation_title: str
    explanation_summary: str
    explanation_disclaimer: str
    explanation_method: str
    explanation_narrative: str | None = None
    district: str | None = None
    district_avg_price: float | None = None
    price_vs_district: float | None = None  # Percentage
    h3_index: str = Field(description="H3 hexagon index of location")
    is_cold_start: bool = Field(
        default=False, description="True if area has no transaction history"
    )


class ExplainabilityTopFeatureResponse(BaseModel):
    """Top SHAP-ranked feature from offline analysis."""

    feature: str
    importance: float


class ExplainabilityEvidenceResponse(BaseModel):
    """Explainability benchmark evidence for a prediction model."""

    model_type: str
    runtime_explanation_method: str
    evidence_available: bool
    evaluation_complete: bool
    generated_at: str | None = None
    summary: str
    model_performance: dict[str, float] = Field(default_factory=dict)
    explanation_metrics: dict[str, float] = Field(default_factory=dict)
    top_shap_features: list[ExplainabilityTopFeatureResponse] = Field(
        default_factory=list
    )
    missing_artifacts: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


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


def _to_price_explanation_response(
    prediction,
    actual_price: float | None = None,
    district_override: str | None = None,
) -> PriceExplanationResponse:
    return PriceExplanationResponse(
        property_id=prediction.property_id,
        predicted_price=round(prediction.predicted_price, 0),
        confidence=prediction.confidence,
        model_type=prediction.model_type,
        actual_price=actual_price,
        feature_contributions=[
            FeatureContributionResponse(
                feature=c.feature,
                feature_display=c.feature_display,
                value=c.value,
                direction=c.direction,
                contribution=c.contribution,
                contribution_kind=c.contribution_kind,
                contribution_display=c.contribution_display,
            )
            for c in prediction.feature_contributions
        ],
        explanation_title=prediction.explanation_title,
        explanation_summary=prediction.explanation_summary,
        explanation_disclaimer=prediction.explanation_disclaimer,
        explanation_method=prediction.explanation_method,
        explanation_narrative=generate_natural_language_explanation(
            prediction, actual_price
        ),
        district=prediction.district or district_override,
        district_avg_price=round(prediction.district_avg_price, 0)
        if prediction.district_avg_price
        else None,
        price_vs_district=round(prediction.price_vs_district, 1)
        if prediction.price_vs_district
        else None,
        h3_index=prediction.h3_index,
        is_cold_start=prediction.is_cold_start,
    )


def _get_local_shap_cached(cache_key: str) -> dict | None:
    cached = _local_shap_cache.get(cache_key)
    if not cached:
        return None
    payload, ts = cached
    if time.time() - ts < _LOCAL_SHAP_CACHE_TTL_SECONDS:
        return payload
    del _local_shap_cache[cache_key]
    return None


def _set_local_shap_cached(cache_key: str, payload: dict) -> None:
    if len(_local_shap_cache) >= _LOCAL_SHAP_CACHE_MAX_SIZE:
        oldest_key = min(_local_shap_cache, key=lambda k: _local_shap_cache[k][1])
        del _local_shap_cache[oldest_key]
    _local_shap_cache[cache_key] = (payload, time.time())


@router.get("/models/status", response_model=ModelStatusResponse)
def get_models_status(
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
):
    """Get status of all available prediction models."""
    available = get_available_predictors()
    default = None
    try:
        default = get_predictor().model_type.value
    except Exception:
        pass

    return ModelStatusResponse(models=available, default_model=default)


@router.get(
    "/models/{model_type}/explainability-evidence",
    response_model=ExplainabilityEvidenceResponse,
)
def get_explainability_evidence(
    model_type: PredictorType,
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
):
    """Return offline explainability benchmark artifacts for the selected model."""
    evidence = load_explainability_evidence(model_type.value)
    return ExplainabilityEvidenceResponse(
        model_type=evidence.model_type,
        runtime_explanation_method=evidence.runtime_explanation_method,
        evidence_available=evidence.evidence_available,
        evaluation_complete=evidence.evaluation_complete,
        generated_at=evidence.generated_at,
        summary=evidence.summary,
        model_performance=evidence.model_performance,
        explanation_metrics=evidence.explanation_metrics,
        top_shap_features=[
            ExplainabilityTopFeatureResponse(
                feature=item.feature,
                importance=item.importance,
            )
            for item in evidence.top_shap_features
        ],
        missing_artifacts=evidence.missing_artifacts,
        notes=evidence.notes,
    )


@router.get("/{property_id}/explain", response_model=PriceExplanationResponse)
def explain_price(
    property_id: int,
    model: PredictorType | None = Query(
        None, description="Model to use for prediction"
    ),
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
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

    return _to_price_explanation_response(
        prediction,
        actual_price=actual_price,
        district_override=amphur,
    )


@router.get("/{property_id}/local-shap", response_model=PriceExplanationResponse)
def explain_price_local_shap(
    property_id: int,
    model: PredictorType | None = Query(
        PredictorType.BASELINE, description="Model to use for local SHAP explanation"
    ),
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    """Get per-property local SHAP explanation with short-lived cache."""
    cache_key = f"property:{property_id}:model:{model.value if model else 'default'}"
    cached = _get_local_shap_cached(cache_key)
    if cached:
        return PriceExplanationResponse(**cached)

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
        _,
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
        predictor = get_predictor(model)
        prediction = predictor.predict_local_shap(
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
    except NotImplementedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"No prediction model available: {e}. Train baseline first.",
        )

    response = _to_price_explanation_response(
        prediction,
        actual_price=actual_price,
        district_override=amphur,
    )
    payload = response.model_dump()
    _set_local_shap_cached(cache_key, payload)
    return response


@router.post("/local-shap/predict", response_model=PriceExplanationResponse)
def predict_price_local_shap(
    request: PredictRequest,
    model: PredictorType | None = Query(
        PredictorType.BASELINE, description="Model to use for local SHAP explanation"
    ),
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    """Get local SHAP explanation for arbitrary listing features and location."""
    cache_payload = {
        "model": model.value if model else "default",
        "lat": round(request.lat, 6),
        "lon": round(request.lon, 6),
        "building_area": request.building_area,
        "land_area": request.land_area,
        "building_age": request.building_age,
        "no_of_floor": request.no_of_floor,
        "building_style": request.building_style,
    }
    cache_key = hashlib.sha256(
        json.dumps(cache_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    cached = _get_local_shap_cached(cache_key)
    if cached:
        return PriceExplanationResponse(**cached)

    try:
        predictor = get_predictor(model)
        prediction = predictor.predict_local_shap(
            db,
            request.lat,
            request.lon,
            request.building_area,
            request.land_area,
            request.building_age,
            request.no_of_floor,
            request.building_style,
        )
    except NotImplementedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"No prediction model available: {e}. Train baseline first.",
        )

    response = _to_price_explanation_response(prediction)
    payload = response.model_dump()
    _set_local_shap_cached(cache_key, payload)
    return response


@router.post("/predict", response_model=PriceExplanationResponse)
def predict_price(
    request: PredictRequest,
    model: PredictorType | None = Query(
        None, description="Model to use for prediction"
    ),
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
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

    return _to_price_explanation_response(prediction)
