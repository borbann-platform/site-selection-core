"""
Price Prediction Service - Pluggable Model Architecture.

Provides a unified interface for property price prediction with:
- Strategy pattern for swappable models (baseline, HGT, etc.)
- Model registry for runtime model selection
- Lazy loading for efficient resource usage
- Consistent response format across all models

Usage:
    from src.services.price_prediction import get_predictor, PredictorType

    predictor = get_predictor(PredictorType.BASELINE)
    result = predictor.predict(db, lat=13.74, lon=100.56, building_area=150)
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import h3
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Paths
MODELS_DIR = Path(__file__).parent.parent.parent / "models"
DATA_DIR = Path(__file__).parent.parent.parent / "data"
H3_FEATURES_PATH = DATA_DIR / "h3_features" / "h3_features_res9.parquet"
HEX2VEC_PATH = MODELS_DIR / "hex2vec" / "hex2vec_embeddings_res9.parquet"
FLOOD_RISK_PATH = DATA_DIR / "h3_features" / "flood_risk_by_district.parquet"
GTFS_STOPS_PATH = DATA_DIR / "bangkok-gtfs" / "stops.txt"

# Constants
H3_RESOLUTION = 9
CBD_LOCATIONS = {
    "siam_paragon": (13.7466, 100.5348),
    "asoke": (13.7371, 100.5603),
    "silom": (13.7286, 100.5343),
}


class PredictorType(str, Enum):
    """Available prediction model types."""

    BASELINE = "baseline"
    BASELINE_HEX2VEC = "baseline_hex2vec"
    HGT = "hgt"


@dataclass
class FeatureContribution:
    """Single feature's contribution to prediction."""

    feature: str
    feature_display: str
    value: float
    direction: str  # "positive" or "negative"
    contribution: float  # Relative importance score, SHAP value, or attention weight
    contribution_kind: str = "relative_signal"
    contribution_display: str | None = None


@dataclass
class PricePrediction:
    """Unified prediction result from any model."""

    predicted_price: float
    confidence: float  # 0-1 prediction confidence
    model_type: str  # Which model produced this prediction

    # Location context
    h3_index: str
    district: str | None = None
    is_cold_start: bool = False

    # Explanations
    feature_contributions: list[FeatureContribution] = field(default_factory=list)
    explanation_title: str = "Model Signals"
    explanation_summary: str = "Top factors that most influenced the model output."
    explanation_disclaimer: str = "These signals are not additive THB components and should not be read as percentages."
    explanation_method: str = "relative_signal"

    # Comparison metrics
    h3_cell_avg_price: float | None = None
    district_avg_price: float | None = None
    price_vs_district: float | None = None  # Percentage difference

    # Original property (if exists)
    property_id: int | None = None
    actual_price: float | None = None


class PricePredictor(ABC):
    """Abstract base class for price prediction models."""

    @property
    @abstractmethod
    def model_type(self) -> PredictorType:
        """Return the type of this predictor."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if model files exist and can be loaded."""
        ...

    @abstractmethod
    def predict(
        self,
        db: Session,
        lat: float,
        lon: float,
        building_area: float | None = None,
        land_area: float | None = None,
        building_age: float | None = None,
        no_of_floor: float | None = None,
        building_style: str | None = None,
        property_id: int | None = None,
    ) -> PricePrediction:
        """Generate price prediction with explanations."""
        ...

    def get_status(self) -> dict:
        """Return model status information."""
        return {
            "model_type": self.model_type.value,
            "available": self.is_available,
        }

    def predict_local_shap(
        self,
        db: Session,
        lat: float,
        lon: float,
        building_area: float | None = None,
        land_area: float | None = None,
        building_age: float | None = None,
        no_of_floor: float | None = None,
        building_style: str | None = None,
        property_id: int | None = None,
    ) -> PricePrediction:
        """Generate prediction with per-request local SHAP explanations."""
        raise NotImplementedError(
            f"Local SHAP not supported for model '{self.model_type.value}'"
        )


class BaselinePredictor(PricePredictor):
    """
    LightGBM baseline predictor with spatial features.

    Uses pre-trained model from scripts/train_baseline.py
    """

    _instances: dict = {}

    def __new__(cls, use_hex2vec: bool = False):
        key = f"baseline_{'hex2vec' if use_hex2vec else 'plain'}"
        if key not in cls._instances:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instances[key] = instance
        return cls._instances[key]

    def __init__(self, use_hex2vec: bool = False):
        if self._initialized:
            return

        self._use_hex2vec = use_hex2vec
        self._model = None
        self._feature_names: list[str] = []
        self._h3_features: pd.DataFrame | None = None
        self._hex2vec: pd.DataFrame | None = None
        self._transit_tree: cKDTree | None = None
        self._transit_stops: pd.DataFrame | None = None
        self._building_style_encoder: dict = {}
        self._loaded = False
        self._initialized = True

        model_name = "baseline_hex2vec" if use_hex2vec else "baseline"
        self._model_dir = MODELS_DIR / model_name

    @property
    def model_type(self) -> PredictorType:
        return (
            PredictorType.BASELINE_HEX2VEC
            if self._use_hex2vec
            else PredictorType.BASELINE
        )

    @property
    def is_available(self) -> bool:
        return (self._model_dir / "lgbm_model.txt").exists()

    def _load_model(self):
        """Lazy load model and supporting data."""
        if self._loaded:
            return

        import lightgbm as lgb

        model_path = self._model_dir / "lgbm_model.txt"
        features_path = self._model_dir / "features.json"

        if not model_path.exists():
            raise FileNotFoundError(
                f"Model not found: {model_path}. "
                "Train it first: python -m scripts.train_baseline"
            )

        self._model = lgb.Booster(model_file=str(model_path))
        logger.info(f"Loaded baseline model from {model_path}")

        if features_path.exists():
            with open(features_path) as f:
                self._feature_names = json.load(f)
        else:
            self._feature_names = self._model.feature_name()

        if H3_FEATURES_PATH.exists():
            self._h3_features = pd.read_parquet(H3_FEATURES_PATH)
            logger.info(f"Loaded H3 features: {self._h3_features.shape}")

        if self._use_hex2vec and HEX2VEC_PATH.exists():
            self._hex2vec = pd.read_parquet(HEX2VEC_PATH)
            logger.info(f"Loaded Hex2Vec embeddings: {self._hex2vec.shape}")

        if GTFS_STOPS_PATH.exists():
            stops = pd.read_csv(GTFS_STOPS_PATH)
            self._transit_stops = stops[
                stops["stop_name"].str.contains("BTS|MRT|ARL", case=False, na=False)
            ]
            if len(self._transit_stops) > 0:
                coords = self._transit_stops[["stop_lat", "stop_lon"]].values
                self._transit_tree = cKDTree(coords)
                logger.info(f"Built transit tree with {len(self._transit_stops)} stops")

        self._building_style_encoder = {
            "บ้านเดี่ยว": 0,
            "ทาวน์เฮ้าส์": 1,
            "บ้านแฝด": 2,
            "อาคารพาณิชย์": 3,
            "คอนโด": 4,
            "unknown": 5,
        }

        self._loaded = True
        logger.info("Baseline predictor ready")

    def _haversine_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate distance in km using haversine formula."""
        R = 6371
        lat1_rad, lat2_rad = np.radians(lat1), np.radians(lat2)
        dlat = np.radians(lat2 - lat1)
        dlon = np.radians(lon2 - lon1)
        a = (
            np.sin(dlat / 2) ** 2
            + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
        )
        return R * 2 * np.arcsin(np.sqrt(a))

    def _build_features(
        self,
        lat: float,
        lon: float,
        h3_index: str,
        building_area: float | None,
        land_area: float | None,
        building_age: float | None,
        no_of_floor: float | None,
        building_style: str | None,
    ) -> np.ndarray:
        """Build feature vector for prediction."""
        features = {}

        # Intrinsic features
        features["building_area"] = building_area or 150.0  # Default median
        features["land_area"] = land_area or 30.0
        features["building_age"] = building_age or 10.0
        features["no_of_floor"] = no_of_floor or 2.0

        # Encode building style
        style_key = (
            building_style
            if building_style in self._building_style_encoder
            else "unknown"
        )
        features["building_style_encoded"] = self._building_style_encoder.get(
            style_key, 5
        )

        # Distance features
        for name, (cbd_lat, cbd_lon) in CBD_LOCATIONS.items():
            features[f"dist_to_{name}"] = self._haversine_distance(
                lat, lon, cbd_lat, cbd_lon
            )

        features["dist_to_cbd_min"] = min(
            features["dist_to_siam_paragon"],
            features["dist_to_asoke"],
            features["dist_to_silom"],
        )

        # Distance to nearest BTS/MRT
        if self._transit_tree is not None:
            dist_deg, _ = self._transit_tree.query([lat, lon], k=1)
            features["dist_to_bts"] = dist_deg * 111.0  # Approximate km
        else:
            features["dist_to_bts"] = 5.0  # Default 5km

        # H3 aggregated features
        h3_cols = [
            "poi_school",
            "poi_transit_stop",
            "poi_hospital",
            "poi_mall",
            "poi_restaurant",
            "poi_cafe",
            "poi_supermarket",
            "poi_park",
            "poi_temple",
            "poi_total",
            "transit_total",
            "property_count",
        ]

        if self._h3_features is not None:
            cell = self._h3_features[self._h3_features["h3_index"] == h3_index]
            if not cell.empty:
                row = cell.iloc[0]
                for col in h3_cols:
                    features[col] = row.get(col, 0.0) or 0.0
            else:
                for col in h3_cols:
                    features[col] = 0.0
        else:
            for col in h3_cols:
                features[col] = 0.0

        # Flood risk (default 0)
        features["flood_risk"] = 0

        # Hex2Vec embeddings
        if self._use_hex2vec and self._hex2vec is not None:
            emb = self._hex2vec[self._hex2vec["h3_index"] == h3_index]
            if not emb.empty:
                row = emb.iloc[0]
                for i in range(64):
                    features[f"emb_{i}"] = row.get(f"emb_{i}", 0.0) or 0.0
            else:
                for i in range(64):
                    features[f"emb_{i}"] = 0.0

        # Build vector in correct order
        return np.array([[features.get(f, 0.0) for f in self._feature_names]])

    def _get_feature_contributions(
        self, features: np.ndarray
    ) -> list[FeatureContribution]:
        """Get top feature contributions using model's feature importance."""
        importance = self._model.feature_importance(importance_type="gain")
        feature_values = features[0]
        contributions = []
        top_indices = np.argsort(importance)[-5:][::-1]

        name_map = {
            "building_area": "Building Area (sqm)",
            "land_area": "Land Area (sq wah)",
            "building_age": "Building Age (years)",
            "no_of_floor": "Number of Floors",
            "dist_to_bts": "Distance to BTS/MRT",
            "dist_to_cbd_min": "Distance to CBD",
            "dist_to_siam_paragon": "Distance to Siam",
            "dist_to_asoke": "Distance to Asoke",
            "poi_total": "Nearby POIs",
            "transit_total": "Transit Accessibility",
            "property_count": "Area Development",
        }

        for idx in top_indices:
            fname = self._feature_names[idx]
            direction = (
                "negative"
                if fname.startswith("dist_to") or fname == "building_age"
                else "positive"
            )
            contributions.append(
                FeatureContribution(
                    feature=fname,
                    feature_display=name_map.get(
                        fname, fname.replace("_", " ").title()
                    ),
                    value=float(feature_values[idx]),
                    contribution=float(importance[idx]),
                    contribution_kind="global_gain",
                    contribution_display=f"Gain {importance[idx]:.2f}",
                    direction=direction,
                )
            )
        return contributions

    def _get_local_shap_contributions(
        self,
        features: np.ndarray,
        predicted_price: float,
    ) -> list[FeatureContribution]:
        """Get per-request local SHAP contributions for this feature vector."""
        shap_with_base = self._model.predict(features, pred_contrib=True)[0]
        shap_values = np.asarray(shap_with_base[:-1], dtype=float)
        feature_values = features[0]

        top_indices = np.argsort(np.abs(shap_values))[-5:][::-1]

        name_map = {
            "building_area": "Building Area (sqm)",
            "land_area": "Land Area (sq wah)",
            "building_age": "Building Age (years)",
            "no_of_floor": "Number of Floors",
            "dist_to_bts": "Distance to BTS/MRT",
            "dist_to_cbd_min": "Distance to CBD",
            "dist_to_siam_paragon": "Distance to Siam",
            "dist_to_asoke": "Distance to Asoke",
            "poi_total": "Nearby POIs",
            "transit_total": "Transit Accessibility",
            "property_count": "Area Development",
        }

        contributions: list[FeatureContribution] = []
        for idx in top_indices:
            shap_value = float(shap_values[idx])
            feature_name = self._feature_names[idx]
            without_feature_price = float(
                np.expm1(np.log1p(predicted_price) - shap_value)
            )
            approx_price_impact = predicted_price - without_feature_price
            direction = "positive" if shap_value >= 0 else "negative"
            contributions.append(
                FeatureContribution(
                    feature=feature_name,
                    feature_display=name_map.get(
                        feature_name,
                        feature_name.replace("_", " ").title(),
                    ),
                    value=float(feature_values[idx]),
                    contribution=approx_price_impact,
                    contribution_kind="local_shap",
                    contribution_display=f"{approx_price_impact:+,.0f} THB",
                    direction=direction,
                )
            )

        return contributions

    def _get_comparison_metrics(
        self, db: Session, h3_index: str, lat: float, lon: float
    ) -> tuple[float | None, float | None, str | None]:
        """Get comparison prices from H3 cell and district."""
        h3_avg = None
        district_avg = None
        district = None

        # H3 cell average
        if self._h3_features is not None:
            cell = self._h3_features[self._h3_features["h3_index"] == h3_index]
            if not cell.empty and "avg_price" in cell.columns:
                h3_avg = cell.iloc[0].get("avg_price")

        # District average from DB
        try:
            result = db.execute(
                text(
                    """
                    SELECT amphur, AVG(total_price) as avg_price
                    FROM house_prices
                    WHERE ST_DWithin(
                        geometry::geography,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                        1000
                    )
                    GROUP BY amphur
                    LIMIT 1
                """
                ),
                {"lat": lat, "lon": lon},
            ).fetchone()

            if result:
                district = result[0]
                district_avg = float(result[1]) if result[1] else None
        except Exception as e:
            logger.warning(f"Failed to get district avg: {e}")

        return h3_avg, district_avg, district

    def predict(
        self,
        db: Session,
        lat: float,
        lon: float,
        building_area: float | None = None,
        land_area: float | None = None,
        building_age: float | None = None,
        no_of_floor: float | None = None,
        building_style: str | None = None,
        property_id: int | None = None,
    ) -> PricePrediction:
        """Generate price prediction."""
        self._load_model()

        # Get H3 index
        h3_index = h3.latlng_to_cell(lat, lon, H3_RESOLUTION)

        # Check cold start
        is_cold_start = True
        if self._h3_features is not None:
            cell = self._h3_features[self._h3_features["h3_index"] == h3_index]
            if not cell.empty:
                is_cold_start = bool(cell.iloc[0].get("is_cold_start", True))

        # Build features
        features = self._build_features(
            lat,
            lon,
            h3_index,
            building_area,
            land_area,
            building_age,
            no_of_floor,
            building_style,
        )

        # Predict (model outputs log_price)
        log_price = self._model.predict(features)[0]
        predicted_price = float(np.expm1(log_price))

        # Confidence based on cold-start and feature completeness
        confidence = 0.8 if not is_cold_start else 0.6
        if building_area is None:
            confidence -= 0.1
        if land_area is None:
            confidence -= 0.05

        # Get comparison metrics
        h3_avg, district_avg, district = self._get_comparison_metrics(
            db, h3_index, lat, lon
        )

        price_vs_district = None
        if district_avg and district_avg > 0:
            price_vs_district = ((predicted_price - district_avg) / district_avg) * 100

        # Get feature contributions
        contributions = self._get_feature_contributions(features)

        return PricePrediction(
            predicted_price=predicted_price,
            confidence=max(0.0, min(1.0, confidence)),
            model_type=self.model_type.value,
            h3_index=h3_index,
            district=district,
            is_cold_start=is_cold_start,
            feature_contributions=contributions,
            explanation_title="Model Signals",
            explanation_summary=(
                "These factors show which inputs most influenced the current estimate."
            ),
            explanation_disclaimer=(
                "Current baseline explanations are relative model signals derived from "
                "global feature importance. They are not additive THB breakdowns or percentages."
            ),
            explanation_method="global_gain",
            h3_cell_avg_price=h3_avg,
            district_avg_price=district_avg,
            price_vs_district=price_vs_district,
            property_id=property_id,
        )

    def predict_local_shap(
        self,
        db: Session,
        lat: float,
        lon: float,
        building_area: float | None = None,
        land_area: float | None = None,
        building_age: float | None = None,
        no_of_floor: float | None = None,
        building_style: str | None = None,
        property_id: int | None = None,
    ) -> PricePrediction:
        """Generate price prediction with local SHAP values for this request."""
        self._load_model()

        h3_index = h3.latlng_to_cell(lat, lon, H3_RESOLUTION)

        is_cold_start = True
        if self._h3_features is not None:
            cell = self._h3_features[self._h3_features["h3_index"] == h3_index]
            if not cell.empty:
                is_cold_start = bool(cell.iloc[0].get("is_cold_start", True))

        features = self._build_features(
            lat,
            lon,
            h3_index,
            building_area,
            land_area,
            building_age,
            no_of_floor,
            building_style,
        )

        log_price = self._model.predict(features)[0]
        predicted_price = float(np.expm1(log_price))

        confidence = 0.8 if not is_cold_start else 0.6
        if building_area is None:
            confidence -= 0.1
        if land_area is None:
            confidence -= 0.05

        h3_avg, district_avg, district = self._get_comparison_metrics(
            db, h3_index, lat, lon
        )

        price_vs_district = None
        if district_avg and district_avg > 0:
            price_vs_district = ((predicted_price - district_avg) / district_avg) * 100

        contributions = self._get_local_shap_contributions(features, predicted_price)

        return PricePrediction(
            predicted_price=predicted_price,
            confidence=max(0.0, min(1.0, confidence)),
            model_type=self.model_type.value,
            h3_index=h3_index,
            district=district,
            is_cold_start=is_cold_start,
            feature_contributions=contributions,
            explanation_title="Local SHAP Signals",
            explanation_summary=(
                "These factors are calculated per property request and show local SHAP"
                " impact converted to approximate THB effect."
            ),
            explanation_disclaimer=(
                "Local SHAP effects are request-specific directional estimates and are"
                " not an exact additive accounting ledger."
            ),
            explanation_method="local_shap",
            h3_cell_avg_price=h3_avg,
            district_avg_price=district_avg,
            price_vs_district=price_vs_district,
            property_id=property_id,
        )

    def get_status(self) -> dict:
        """Return detailed status."""
        status = super().get_status()
        status["use_hex2vec"] = self._use_hex2vec
        status["model_path"] = str(self._model_dir / "lgbm_model.txt")
        status["loaded"] = self._loaded
        if self._loaded:
            status["num_features"] = len(self._feature_names)
        return status


class HGTPredictorAdapter(PricePredictor):
    """Adapter to make HGT service conform to PricePredictor interface."""

    def __init__(self, hgt_service):
        self._service = hgt_service

    @property
    def model_type(self) -> PredictorType:
        return PredictorType.HGT

    @property
    def is_available(self) -> bool:
        try:
            return (
                self._service._loaded
                or Path("models/hgt_valuator/hgt_valuator.pt").exists()
            )
        except Exception:
            return False

    def predict(
        self,
        db: Session,
        lat: float,
        lon: float,
        building_area: float | None = None,
        land_area: float | None = None,
        building_age: float | None = None,
        no_of_floor: float | None = None,
        building_style: str | None = None,
        property_id: int | None = None,
    ) -> PricePrediction:
        """Delegate to HGT service and convert result."""
        result = self._service.predict(
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

        # Convert HGTPrediction to PricePrediction
        contributions = [
            FeatureContribution(
                feature=exp.node_type,
                feature_display=exp.node_name,
                value=exp.distance_m,
                contribution=exp.attention_weight,
                contribution_kind="attention_weight",
                contribution_display=f"Attention {exp.attention_weight:.2f}",
                direction=exp.impact_direction,
            )
            for exp in result.attention_explanations
        ]

        return PricePrediction(
            predicted_price=result.predicted_price,
            confidence=result.confidence,
            model_type=PredictorType.HGT.value,
            h3_index=result.h3_index,
            district=result.district,
            is_cold_start=result.is_cold_start,
            feature_contributions=contributions,
            explanation_title="Attention Signals",
            explanation_summary=(
                "These anchors received the highest model attention for this estimate."
            ),
            explanation_disclaimer=(
                "Attention weights indicate model focus, not additive THB components or "
                "validated causal effects."
            ),
            explanation_method="attention_weight",
            h3_cell_avg_price=result.h3_cell_avg_price,
            district_avg_price=result.district_avg_price,
            price_vs_district=result.price_vs_cell,
            property_id=result.property_id,
        )


# Model Registry
class PredictorRegistry:
    """Registry for available predictors with lazy initialization."""

    _predictors: dict[PredictorType, PricePredictor] = {}

    @classmethod
    def get(cls, predictor_type: PredictorType) -> PricePredictor:
        """Get predictor instance (creates if needed)."""
        if predictor_type not in cls._predictors:
            if predictor_type == PredictorType.BASELINE:
                cls._predictors[predictor_type] = BaselinePredictor(use_hex2vec=False)
            elif predictor_type == PredictorType.BASELINE_HEX2VEC:
                cls._predictors[predictor_type] = BaselinePredictor(use_hex2vec=True)
            elif predictor_type == PredictorType.HGT:
                # Lazy import to avoid torch dependency if not using HGT
                from src.services.hgt_prediction import hgt_prediction_service

                cls._predictors[predictor_type] = HGTPredictorAdapter(
                    hgt_prediction_service
                )
            else:
                raise ValueError(f"Unknown predictor type: {predictor_type}")

        return cls._predictors[predictor_type]

    @classmethod
    def get_available(cls) -> list[dict]:
        """List all available predictors with status."""
        results = []
        for ptype in PredictorType:
            try:
                predictor = cls.get(ptype)
                results.append(predictor.get_status())
            except Exception as e:
                results.append(
                    {
                        "model_type": ptype.value,
                        "available": False,
                        "error": str(e),
                    }
                )
        return results

    @classmethod
    def get_default(cls) -> PricePredictor:
        """Get best available predictor."""
        # Priority: HGT > Baseline+Hex2Vec > Baseline
        for ptype in [
            PredictorType.HGT,
            PredictorType.BASELINE_HEX2VEC,
            PredictorType.BASELINE,
        ]:
            try:
                predictor = cls.get(ptype)
                if predictor.is_available:
                    return predictor
            except Exception:
                continue

        raise RuntimeError(
            "No prediction models available. Train baseline model first."
        )


# Convenience functions
def get_predictor(predictor_type: PredictorType | None = None) -> PricePredictor:
    """Get predictor by type or default best available."""
    if predictor_type is None:
        return PredictorRegistry.get_default()
    return PredictorRegistry.get(predictor_type)


def get_available_predictors() -> list[dict]:
    """List all available predictors."""
    return PredictorRegistry.get_available()
