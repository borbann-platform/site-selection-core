"""
Property Valuation API endpoint.

Provides AI-powered property valuation using real ML models.
Integrates with the price prediction service and returns
comprehensive valuation reports including:
- Estimated price with confidence levels
- Price factors and their contributions
- Comparable properties from the database
- Market insights for the district

Also supports saving user-submitted properties for valuation history.
"""

import logging
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from src.config.database import get_db_session
from src.dependencies.auth import get_current_user_optional
from src.models.realestate import HousePrice, UserProperty
from src.models.user import User
from src.services.price_prediction import get_predictor, get_available_predictors

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/valuation", tags=["Property Valuation"])


# ============= Request/Response Models =============


class PropertyValuationRequest(BaseModel):
    """Request body for property valuation."""

    building_style: str = Field(
        ..., description="Building style (บ้านเดี่ยว, ทาวน์เฮ้าส์, etc.)"
    )
    building_area: float = Field(..., gt=0, description="Building area in sqm")
    land_area: float | None = Field(None, ge=0, description="Land area in sq wah")
    no_of_floor: int = Field(..., gt=0, description="Number of floors")
    building_age: float = Field(..., ge=0, description="Building age in years")
    amphur: str = Field(..., description="District (เขต)")
    tumbon: str | None = Field(None, description="Sub-district (แขวง)")
    village: str | None = Field(None, description="Village/project name")
    latitude: float = Field(..., ge=5, le=21, description="Latitude (Thailand bounds)")
    longitude: float = Field(
        ..., ge=97, le=106, description="Longitude (Thailand bounds)"
    )
    asking_price: float | None = Field(
        None, ge=0, description="User's asking price for comparison"
    )
    save_property: bool = Field(
        False, description="Whether to save this property to database"
    )
    user_id: str | None = Field(None, description="User ID for tracking (optional)")


class ValuationFactor(BaseModel):
    """Single factor contributing to property valuation."""

    name: str
    display_name: str
    impact: float = Field(description="Impact on price in THB")
    direction: Literal["positive", "negative", "neutral"]
    description: str


class ValuationComparable(BaseModel):
    """Comparable property from the database."""

    id: int
    price: float
    building_style_desc: str
    building_area: float
    distance_m: float
    similarity_score: float = Field(ge=0, le=100, description="Similarity percentage")


class MarketInsights(BaseModel):
    """Market insights for the property's district."""

    district_avg_price: float
    district_price_trend: float = Field(description="YoY price change percentage")
    days_on_market_avg: int


class ValuationResponse(BaseModel):
    """Complete property valuation response."""

    estimated_price: float
    price_range: dict[str, float] = Field(description="Min and max price range")
    confidence: Literal["high", "medium", "low"]
    price_per_sqm: float
    factors: list[ValuationFactor]
    comparable_properties: list[ValuationComparable]
    market_insights: MarketInsights
    # Additional metadata
    model_type: str = Field(description="ML model used for prediction")
    h3_index: str = Field(description="H3 hexagon index of location")
    is_cold_start: bool = Field(description="Whether area has limited transaction data")
    property_id: str | None = Field(
        None, description="Saved property ID if save_property was True"
    )


class UserPropertyResponse(BaseModel):
    """Response for user property operations."""

    id: str
    building_style: str | None
    building_area: float | None
    estimated_price: float | None
    confidence: str | None
    created_at: str


# ============= Helper Functions =============


def confidence_to_category(score: float) -> Literal["high", "medium", "low"]:
    """Convert numeric confidence score to categorical level."""
    if score >= 0.7:
        return "high"
    elif score >= 0.5:
        return "medium"
    return "low"


def calculate_price_range(
    price: float, confidence: Literal["high", "medium", "low"]
) -> dict[str, float]:
    """Calculate price range based on confidence level."""
    range_percent = {"high": 0.08, "medium": 0.12, "low": 0.18}[confidence]
    return {
        "min": round(price * (1 - range_percent)),
        "max": round(price * (1 + range_percent)),
    }


def calculate_similarity_score(
    target_area: float,
    target_style: str,
    comp_area: float | None,
    comp_style: str | None,
    distance_m: float,
) -> float:
    """
    Calculate similarity score between target property and comparable.
    Based on: building area similarity, style match, and distance.
    """
    score = 100.0

    # Area similarity (up to -30 points)
    if comp_area and target_area > 0:
        area_diff_pct = abs(target_area - comp_area) / target_area
        score -= min(30, area_diff_pct * 100)

    # Style match (-20 points if different)
    if comp_style and comp_style != target_style:
        score -= 20

    # Distance penalty (up to -30 points for far properties)
    distance_penalty = min(30, (distance_m / 2000) * 30)
    score -= distance_penalty

    return max(0, min(100, score))


def get_comparable_properties(
    db: Session,
    lat: float,
    lon: float,
    building_style: str,
    building_area: float,
    radius_m: int = 2000,
    limit: int = 5,
) -> list[ValuationComparable]:
    """Fetch comparable properties from the database."""
    sql = text("""
        SELECT 
            id,
            building_style_desc,
            building_area,
            total_price,
            ST_Distance(
                geometry::geography, 
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            ) as distance_m
        FROM house_prices
        WHERE ST_DWithin(
            geometry::geography,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
            :radius
        )
        AND total_price IS NOT NULL
        AND total_price > 0
        ORDER BY 
            CASE WHEN building_style_desc = :building_style THEN 0 ELSE 1 END,
            ABS(COALESCE(building_area, 0) - :building_area),
            distance_m
        LIMIT :limit
    """)

    result = db.execute(
        sql,
        {
            "lat": lat,
            "lon": lon,
            "radius": radius_m,
            "building_style": building_style,
            "building_area": building_area,
            "limit": limit,
        },
    ).fetchall()

    comparables = []
    for row in result:
        similarity = calculate_similarity_score(
            building_area,
            building_style,
            row.building_area,
            row.building_style_desc,
            row.distance_m,
        )
        comparables.append(
            ValuationComparable(
                id=row.id,
                price=float(row.total_price),
                building_style_desc=row.building_style_desc or "Unknown",
                building_area=float(row.building_area) if row.building_area else 0,
                distance_m=round(row.distance_m, 1),
                similarity_score=round(similarity, 1),
            )
        )

    return comparables


def get_market_insights(db: Session, amphur: str) -> MarketInsights:
    """Get market insights for a district."""
    # Get district average price
    avg_result = db.execute(
        text("""
            SELECT 
                AVG(total_price) as avg_price,
                COUNT(*) as count
            FROM house_prices
            WHERE amphur = :amphur
            AND total_price IS NOT NULL
            AND total_price > 0
        """),
        {"amphur": amphur},
    ).fetchone()

    district_avg = (
        float(avg_result.avg_price) if avg_result and avg_result.avg_price else 0
    )

    # Price trend: We don't have time-series data, so we'll estimate based on
    # the difference between recent and older appraisals if available
    # For now, use a placeholder positive trend (typical Bangkok market)
    # In production, this would use actual historical data
    district_price_trend = 5.0  # 5% YoY assumed growth

    # Days on market: We don't have listing duration data
    # Use industry average for Bangkok
    days_on_market_avg = 45

    return MarketInsights(
        district_avg_price=round(district_avg),
        district_price_trend=district_price_trend,
        days_on_market_avg=days_on_market_avg,
    )


def save_user_property(
    db: Session,
    request: PropertyValuationRequest,
    estimated_price: float,
    confidence: str,
    confidence_score: float,
    model_type: str,
    h3_index: str,
    is_cold_start: bool,
    factors: list[ValuationFactor],
    market_insights: MarketInsights,
) -> UserProperty:
    """Save user property with valuation results to database."""
    from geoalchemy2.functions import ST_SetSRID, ST_MakePoint

    property = UserProperty(
        user_id=request.user_id,
        building_style=request.building_style,
        building_area=request.building_area,
        land_area=request.land_area,
        no_of_floor=request.no_of_floor,
        building_age=request.building_age,
        amphur=request.amphur,
        tumbon=request.tumbon,
        village=request.village,
        asking_price=request.asking_price,
        estimated_price=estimated_price,
        confidence=confidence,
        confidence_score=confidence_score,
        model_type=model_type,
        h3_index=h3_index,
        is_cold_start=is_cold_start,
        valuation_factors=[f.model_dump() for f in factors],
        market_insights=market_insights.model_dump(),
        geometry=ST_SetSRID(ST_MakePoint(request.longitude, request.latitude), 4326),
    )

    db.add(property)
    db.commit()
    db.refresh(property)

    return property


# ============= API Endpoints =============


@router.post("", response_model=ValuationResponse)
def get_property_valuation(
    request: PropertyValuationRequest,
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    """
    Get AI-powered property valuation.

    This endpoint uses real ML models (LightGBM baseline or HGT Graph Neural Network)
    to predict property values based on:
    - Property characteristics (area, age, floors, style)
    - Location features (distance to CBD, transit, POIs)
    - Spatial context (H3 hexagon aggregates)

    Returns comprehensive valuation including:
    - Estimated price with confidence level
    - Price factors and their contributions
    - Comparable properties from the database
    - Market insights for the district

    Optionally saves the property for valuation history tracking.
    """
    # Get the best available predictor
    try:
        predictor = get_predictor()
    except RuntimeError as e:
        logger.error(f"No prediction model available: {e}")
        raise HTTPException(
            status_code=503,
            detail="Prediction model not available. Please ensure the baseline model is trained.",
        )

    # Run prediction
    try:
        prediction = predictor.predict(
            db,
            lat=request.latitude,
            lon=request.longitude,
            building_area=request.building_area,
            land_area=request.land_area,
            building_age=request.building_age,
            no_of_floor=float(request.no_of_floor),
            building_style=request.building_style,
        )
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate prediction: {str(e)}",
        )

    # Convert confidence to category
    confidence_level = confidence_to_category(prediction.confidence)

    # Calculate price range
    price_range = calculate_price_range(prediction.predicted_price, confidence_level)

    # Calculate price per sqm
    price_per_sqm = round(prediction.predicted_price / request.building_area)

    # Convert feature contributions to valuation factors
    factors = []
    for contrib in prediction.feature_contributions:
        # Calculate impact in THB (contribution as percentage of predicted price)
        # The contribution from the ML model is relative importance
        # We scale it to create a meaningful THB impact for display
        impact_pct = contrib.contribution / 100 if contrib.contribution > 0 else 0.05
        impact = prediction.predicted_price * impact_pct

        # Determine direction based on feature type
        direction: Literal["positive", "negative", "neutral"] = "neutral"
        if contrib.direction == "positive":
            direction = "positive"
        elif contrib.direction == "negative":
            direction = "negative"
            impact = -abs(impact)

        # Generate description based on feature
        description = _generate_factor_description(
            contrib.feature, contrib.value, direction
        )

        factors.append(
            ValuationFactor(
                name=contrib.feature,
                display_name=contrib.feature_display,
                impact=round(impact),
                direction=direction,
                description=description,
            )
        )

    # Sort factors by absolute impact
    factors.sort(key=lambda f: abs(f.impact), reverse=True)

    # Get comparable properties
    comparables = get_comparable_properties(
        db,
        request.latitude,
        request.longitude,
        request.building_style,
        request.building_area,
    )

    # Get market insights
    market_insights = get_market_insights(db, request.amphur)

    # Override district avg from prediction if available
    if prediction.district_avg_price:
        market_insights.district_avg_price = round(prediction.district_avg_price)

    # Save property if requested
    property_id = None
    if request.save_property:
        try:
            saved_property = save_user_property(
                db,
                request,
                prediction.predicted_price,
                confidence_level,
                prediction.confidence,
                prediction.model_type,
                prediction.h3_index,
                prediction.is_cold_start,
                factors,
                market_insights,
            )
            property_id = str(saved_property.id)
        except Exception as e:
            logger.warning(f"Failed to save property: {e}")
            # Don't fail the whole request if saving fails

    return ValuationResponse(
        estimated_price=round(prediction.predicted_price),
        price_range=price_range,
        confidence=confidence_level,
        price_per_sqm=price_per_sqm,
        factors=factors,
        comparable_properties=comparables,
        market_insights=market_insights,
        model_type=prediction.model_type,
        h3_index=prediction.h3_index,
        is_cold_start=prediction.is_cold_start,
        property_id=property_id,
    )


@router.get("/models", response_model=dict)
def get_valuation_models(
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
):
    """Get status of available prediction models."""
    return {
        "models": get_available_predictors(),
        "default": get_predictor().model_type.value if get_predictor() else None,
    }


@router.get("/user-properties", response_model=list[UserPropertyResponse])
def list_user_properties(
    user_id: str | None = Query(None, description="Filter by user ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    """List user-submitted properties with their valuations."""
    query = db.query(UserProperty)

    if user_id:
        query = query.filter(UserProperty.user_id == user_id)

    query = query.order_by(UserProperty.created_at.desc())
    properties = query.offset(offset).limit(limit).all()

    return [
        UserPropertyResponse(
            id=str(p.id),
            building_style=p.building_style,
            building_area=p.building_area,
            estimated_price=p.estimated_price,
            confidence=p.confidence,
            created_at=p.created_at.isoformat(),
        )
        for p in properties
    ]


@router.get("/user-properties/{property_id}", response_model=dict)
def get_user_property(
    property_id: UUID,
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    """Get details of a user-submitted property."""
    property = db.query(UserProperty).filter(UserProperty.id == property_id).first()

    if not property:
        raise HTTPException(status_code=404, detail="Property not found")

    # Get coordinates
    coords = db.execute(
        text(
            "SELECT ST_X(geometry), ST_Y(geometry) FROM user_properties WHERE id = :id"
        ),
        {"id": str(property_id)},
    ).fetchone()

    return {
        "id": str(property.id),
        "user_id": property.user_id,
        "building_style": property.building_style,
        "building_area": property.building_area,
        "land_area": property.land_area,
        "no_of_floor": property.no_of_floor,
        "building_age": property.building_age,
        "amphur": property.amphur,
        "tumbon": property.tumbon,
        "village": property.village,
        "asking_price": property.asking_price,
        "estimated_price": property.estimated_price,
        "confidence": property.confidence,
        "confidence_score": property.confidence_score,
        "model_type": property.model_type,
        "h3_index": property.h3_index,
        "is_cold_start": property.is_cold_start,
        "valuation_factors": property.valuation_factors,
        "market_insights": property.market_insights,
        "latitude": coords[1] if coords else None,
        "longitude": coords[0] if coords else None,
        "created_at": property.created_at.isoformat(),
        "updated_at": property.updated_at.isoformat(),
    }


# ============= Helper Functions for Factor Descriptions =============


def _generate_factor_description(feature: str, value: float, direction: str) -> str:
    """Generate human-readable description for a valuation factor."""
    descriptions = {
        "building_area": f"{value:.0f} sqm of building area",
        "land_area": f"{value:.0f} sq wah of land",
        "building_age": f"Building is {value:.0f} years old",
        "no_of_floor": f"{value:.0f} floor(s) of living space",
        "dist_to_bts": f"{value:.2f} km to nearest BTS/MRT",
        "dist_to_cbd_min": f"{value:.2f} km to CBD",
        "dist_to_siam_paragon": f"{value:.2f} km to Siam",
        "dist_to_asoke": f"{value:.2f} km to Asoke",
        "dist_to_silom": f"{value:.2f} km to Silom",
        "poi_total": f"{value:.0f} points of interest nearby",
        "poi_school": f"{value:.0f} schools nearby",
        "poi_hospital": f"{value:.0f} hospitals nearby",
        "poi_mall": f"{value:.0f} shopping malls nearby",
        "transit_total": f"Transit accessibility score: {value:.0f}",
        "property_count": f"{value:.0f} properties in area (development level)",
        "flood_risk": f"Flood risk level: {value:.0f}",
    }

    base_desc = descriptions.get(feature, f"{feature}: {value:.2f}")

    # Add impact note
    if direction == "positive":
        return f"{base_desc} - adds value"
    elif direction == "negative":
        return f"{base_desc} - reduces value"
    return base_desc
