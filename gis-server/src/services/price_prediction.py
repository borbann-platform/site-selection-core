"""Price prediction service with SHAP explainability."""

import json
import logging
import os
from dataclasses import dataclass

import joblib
import numpy as np
import shap
from sqlalchemy.orm import Session
from src.services.price_features import (
    FEATURE_DISPLAY_NAMES,
    feature_extraction_service,
)

logger = logging.getLogger(__name__)

MODELS_DIR = "models"
MODEL_PATH = os.path.join(MODELS_DIR, "price_model.joblib")
METADATA_PATH = os.path.join(MODELS_DIR, "model_metadata.json")


@dataclass
class FeatureContribution:
    """Single feature's contribution to price."""

    feature: str
    feature_display: str  # Human-readable name
    value: float  # Actual feature value
    contribution: float  # SHAP value (THB impact)
    direction: str  # "positive" or "negative"


@dataclass
class PriceExplanation:
    """Complete price explanation for a property."""

    property_id: int
    predicted_price: float
    base_price: float  # Expected value (average)
    feature_contributions: list[FeatureContribution]
    district_avg_price: float
    price_vs_district: float  # Percentage difference


class PricePredictionService:
    """Service for predicting prices and explaining them with SHAP."""

    def __init__(self):
        self._model = None
        self._explainer = None
        self._feature_names: list[str] = []
        self._loaded = False

    def _load_model(self):
        """Load model and create SHAP explainer."""
        if self._loaded:
            return

        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Model not found at {MODEL_PATH}. Run 'uv run python scripts/train_price_model.py' first."
            )

        logger.info("Loading price prediction model...")
        self._model = joblib.load(MODEL_PATH)

        # Load metadata
        with open(METADATA_PATH) as f:
            metadata = json.load(f)
            self._feature_names = metadata["feature_names"]

        # Create SHAP explainer (TreeExplainer for GBM)
        self._explainer = shap.TreeExplainer(self._model)
        self._loaded = True
        logger.info("Model and SHAP explainer loaded")

    def explain(
        self,
        db: Session,
        property_id: int,
        lat: float,
        lon: float,
        building_area: float | None,
        land_area: float | None,
        building_age: float | None,
        no_of_floor: float | None,
        building_style: str | None,
        amphur: str | None,
        actual_price: float | None = None,
        top_k: int = 5,
    ) -> PriceExplanation:
        """
        Generate price explanation for a property.

        Args:
            top_k: Number of top contributing features to return

        """
        self._load_model()

        # Extract features
        features = feature_extraction_service.extract_features(
            db,
            property_id=property_id,
            lat=lat,
            lon=lon,
            building_area=building_area,
            land_area=land_area,
            building_age=building_age,
            no_of_floor=no_of_floor,
            building_style=building_style,
            amphur=amphur,
        )

        # Convert to array
        X = np.array([feature_extraction_service.features_to_array(features)])

        # Predict
        predicted_price = float(self._model.predict(X)[0])

        # Get SHAP values
        shap_values = self._explainer.shap_values(X)
        base_value = float(self._explainer.expected_value)

        # Build contribution list
        contributions = []
        feature_array = feature_extraction_service.features_to_array(features)

        for i, (fname, shap_val, fval) in enumerate(
            zip(self._feature_names, shap_values[0], feature_array)
        ):
            contributions.append(
                FeatureContribution(
                    feature=fname,
                    feature_display=FEATURE_DISPLAY_NAMES.get(fname, fname),
                    value=float(fval),
                    contribution=float(shap_val),
                    direction="positive" if shap_val >= 0 else "negative",
                )
            )

        # Sort by absolute contribution, take top_k
        contributions.sort(key=lambda x: abs(x.contribution), reverse=True)
        top_contributions = contributions[:top_k]

        # Calculate district comparison
        district_avg = features.district_avg_price_sqm
        if district_avg > 0 and building_area and building_area > 0:
            expected_district_price = district_avg * building_area
            price_vs_district = (
                (predicted_price - expected_district_price) / expected_district_price
            ) * 100
        else:
            price_vs_district = 0.0

        return PriceExplanation(
            property_id=property_id,
            predicted_price=predicted_price,
            base_price=base_value,
            feature_contributions=top_contributions,
            district_avg_price=district_avg * (building_area or 0),
            price_vs_district=price_vs_district,
        )


# Singleton
price_prediction_service = PricePredictionService()
