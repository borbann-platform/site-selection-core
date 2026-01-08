"""
HGT (Heterogeneous Graph Transformer) Price Prediction API.

Provides advanced price prediction using graph neural networks with:
- Spatial context from H3 hexagonal grid
- Transit network centrality effects
- Attention-based explainability
- Cold-start handling for areas without transaction history
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.config.database import get_db_session
from src.services.hgt_prediction import HAS_TORCH, hgt_prediction_service

router = APIRouter(prefix="/hgt-valuation", tags=["HGT Price Prediction"])


class AttentionExplanationResponse(BaseModel):
    """Attention-based explanation for a factor affecting price."""

    node_type: str = Field(
        ..., description="Type of spatial feature (transit, amenity, flood_zone)"
    )
    node_name: str = Field(..., description="Name of the feature (e.g., 'BTS Asoke')")
    attention_weight: float = Field(
        ..., ge=0, le=1, description="Importance weight (0-1)"
    )
    distance_m: float = Field(..., description="Distance to property in meters")
    impact_direction: str = Field(
        ..., description="positive or negative impact on price"
    )


class HGTPredictionRequest(BaseModel):
    """Request for HGT price prediction."""

    lat: float = Field(..., description="Latitude of property location")
    lon: float = Field(..., description="Longitude of property location")
    building_area: float | None = Field(None, description="Building area in sqm")
    land_area: float | None = Field(None, description="Land area in sq wah")
    building_age: float | None = Field(None, description="Building age in years")
    no_of_floor: float | None = Field(None, description="Number of floors")
    building_style: str | None = Field(
        None, description="Building style (บ้านเดี่ยว, ทาวน์เฮ้าส์, etc.)"
    )


class HGTPredictionResponse(BaseModel):
    """Response from HGT price prediction."""

    predicted_price: float = Field(..., description="Predicted price in THB")
    confidence: float = Field(
        ..., ge=0, le=1, description="Prediction confidence (0-1)"
    )
    is_cold_start: bool = Field(
        ..., description="True if area has no transaction history"
    )

    h3_index: str = Field(..., description="H3 hexagon index of location")
    district: str | None = Field(None, description="District name")

    attention_explanations: list[AttentionExplanationResponse] = Field(
        default_factory=list,
        description="Top factors affecting price with attention weights",
    )

    h3_cell_avg_price: float | None = Field(
        None, description="Average price in same H3 cell"
    )
    district_avg_price: float | None = Field(
        None, description="Average price in district"
    )
    price_vs_cell: float | None = Field(
        None, description="Percentage difference from cell average"
    )


class ModelStatusResponse(BaseModel):
    """Status of the HGT model."""

    available: bool
    pytorch_available: bool
    model_loaded: bool
    metadata: dict = Field(default_factory=dict)


@router.get("/status", response_model=ModelStatusResponse)
def get_model_status():
    """Check if HGT model is available and loaded."""
    model_loaded = False
    metadata = {}

    if HAS_TORCH:
        try:
            hgt_prediction_service._load_model()
            model_loaded = hgt_prediction_service._loaded
            metadata = hgt_prediction_service._metadata
        except FileNotFoundError:
            pass
        except Exception as e:
            metadata = {"error": str(e)}

    return ModelStatusResponse(
        available=HAS_TORCH and model_loaded,
        pytorch_available=HAS_TORCH,
        model_loaded=model_loaded,
        metadata=metadata,
    )


@router.post("/predict", response_model=HGTPredictionResponse)
def predict_price(
    request: HGTPredictionRequest,
    db: Session = Depends(get_db_session),
):
    """
    Predict property price using Heterogeneous Graph Transformer.

    The model uses:
    - Property intrinsic features (area, age, floors)
    - Spatial context from H3 hexagonal grid
    - Transit network proximity and centrality
    - Neighborhood POI density and type
    - Flood risk zones (when GISTDA API available)

    Returns prediction with confidence score and attention-based explanations.
    Cold-start areas (no prior transactions) are handled with spatial imputation.
    """
    if not HAS_TORCH:
        raise HTTPException(
            status_code=503,
            detail="PyTorch not available. Install with: pip install torch torch-geometric",
        )

    try:
        prediction = hgt_prediction_service.predict(
            db=db,
            lat=request.lat,
            lon=request.lon,
            building_area=request.building_area,
            land_area=request.land_area,
            building_age=request.building_age,
            no_of_floor=request.no_of_floor,
            building_style=request.building_style,
        )

        return HGTPredictionResponse(
            predicted_price=prediction.predicted_price,
            confidence=prediction.confidence,
            is_cold_start=prediction.is_cold_start,
            h3_index=prediction.h3_index,
            district=prediction.district,
            attention_explanations=[
                AttentionExplanationResponse(
                    node_type=exp.node_type,
                    node_name=exp.node_name,
                    attention_weight=exp.attention_weight,
                    distance_m=exp.distance_m,
                    impact_direction=exp.impact_direction,
                )
                for exp in prediction.attention_explanations
            ],
            h3_cell_avg_price=prediction.h3_cell_avg_price,
            district_avg_price=prediction.district_avg_price,
            price_vs_cell=prediction.price_vs_cell,
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e!s}")


@router.get("/{property_id}/predict", response_model=HGTPredictionResponse)
def predict_property_price(
    property_id: int,
    db: Session = Depends(get_db_session),
):
    """
    Predict price for an existing property by ID.

    Uses stored property attributes and optimized graph lookup.
    """
    if not HAS_TORCH:
        raise HTTPException(status_code=503, detail="PyTorch not available")

    # Fetch property data
    result = db.execute(
        text(
            """
            SELECT id, ST_X(geometry) as lon, ST_Y(geometry) as lat,
                   building_area, land_area, building_age, no_of_floor,
                   building_style_desc, amphur
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
    ) = result

    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="Property has no location data")

    try:
        prediction = hgt_prediction_service.predict(
            db=db,
            lat=lat,
            lon=lon,
            building_area=building_area,
            land_area=land_area,
            building_age=building_age,
            no_of_floor=no_of_floor,
            building_style=building_style,
            property_id=property_id,
        )

        return HGTPredictionResponse(
            predicted_price=prediction.predicted_price,
            confidence=prediction.confidence,
            is_cold_start=prediction.is_cold_start,
            h3_index=prediction.h3_index,
            district=prediction.district,
            attention_explanations=[
                AttentionExplanationResponse(
                    node_type=exp.node_type,
                    node_name=exp.node_name,
                    attention_weight=exp.attention_weight,
                    distance_m=exp.distance_m,
                    impact_direction=exp.impact_direction,
                )
                for exp in prediction.attention_explanations
            ],
            h3_cell_avg_price=prediction.h3_cell_avg_price,
            district_avg_price=prediction.district_avg_price,
            price_vs_cell=prediction.price_vs_cell,
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e!s}")
