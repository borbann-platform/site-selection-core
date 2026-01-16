"""
Unit tests for price prediction service.

Tests the core price prediction functionality including:
- Predictor types and initialization
- Haversine distance calculations
- Feature contribution dataclass
- Predictor registry
"""

import pytest


class TestPredictorType:
    """Tests for PredictorType enum."""

    def test_predictor_types_exist(self):
        """Test that all expected predictor types are defined."""
        from src.services.price_prediction import PredictorType

        assert hasattr(PredictorType, "BASELINE")
        assert hasattr(PredictorType, "BASELINE_HEX2VEC")
        assert hasattr(PredictorType, "HGT")

    def test_predictor_type_values(self):
        """Test that predictor types have correct string values."""
        from src.services.price_prediction import PredictorType

        assert PredictorType.BASELINE.value == "baseline"
        assert PredictorType.BASELINE_HEX2VEC.value == "baseline_hex2vec"
        assert PredictorType.HGT.value == "hgt"


class TestBaselinePredictor:
    """Tests for BaselinePredictor class."""

    def test_predictor_type_baseline(self):
        """Test that baseline predictor has correct type."""
        from src.services.price_prediction import BaselinePredictor, PredictorType

        predictor = BaselinePredictor(use_hex2vec=False)
        assert predictor.model_type == PredictorType.BASELINE

    def test_predictor_type_hex2vec(self):
        """Test that hex2vec predictor has correct type."""
        from src.services.price_prediction import BaselinePredictor, PredictorType

        predictor = BaselinePredictor(use_hex2vec=True)
        assert predictor.model_type == PredictorType.BASELINE_HEX2VEC

    def test_haversine_distance_same_point(self):
        """Test haversine distance between same point is zero."""
        from src.services.price_prediction import BaselinePredictor

        predictor = BaselinePredictor(use_hex2vec=False)
        distance = predictor._haversine_distance(13.75, 100.55, 13.75, 100.55)
        assert distance == pytest.approx(0.0, abs=0.001)

    def test_haversine_distance_known_values(self):
        """Test haversine distance calculation with known values."""
        from src.services.price_prediction import BaselinePredictor

        predictor = BaselinePredictor(use_hex2vec=False)
        # Siam Paragon to Asoke is approximately 3km
        distance = predictor._haversine_distance(
            13.7466,
            100.5348,  # Siam Paragon
            13.7371,
            100.5603,  # Asoke
        )
        # Distance should be between 2.5 and 3.5 km
        assert 2.5 < distance < 3.5

    def test_get_status_returns_dict(self):
        """Test that get_status returns a dictionary with expected keys."""
        from src.services.price_prediction import BaselinePredictor

        predictor = BaselinePredictor(use_hex2vec=False)
        status = predictor.get_status()

        assert isinstance(status, dict)
        assert "model_type" in status
        assert "available" in status
        assert status["model_type"] == "baseline"


class TestFeatureContribution:
    """Tests for FeatureContribution dataclass."""

    def test_feature_contribution_creation(self):
        """Test creating a FeatureContribution."""
        from src.services.price_prediction import FeatureContribution

        contrib = FeatureContribution(
            feature="building_area",
            feature_display="Building Area (sqm)",
            value=150.0,
            contribution=0.25,
            direction="positive",
        )

        assert contrib.feature == "building_area"
        assert contrib.feature_display == "Building Area (sqm)"
        assert contrib.value == 150.0
        assert contrib.contribution == 0.25
        assert contrib.direction == "positive"

    def test_feature_contribution_negative_direction(self):
        """Test creating a FeatureContribution with negative direction."""
        from src.services.price_prediction import FeatureContribution

        contrib = FeatureContribution(
            feature="dist_to_bts",
            feature_display="Distance to BTS/MRT",
            value=2.5,
            contribution=-0.15,
            direction="negative",
        )

        assert contrib.direction == "negative"
        assert contrib.contribution == -0.15


class TestPricePrediction:
    """Tests for PricePrediction dataclass."""

    def test_price_prediction_creation(self):
        """Test creating a PricePrediction with minimal fields."""
        from src.services.price_prediction import PricePrediction

        prediction = PricePrediction(
            predicted_price=5_000_000.0,
            confidence=0.85,
            model_type="baseline",
            h3_index="89283082837ffff",
        )

        assert prediction.predicted_price == 5_000_000.0
        assert prediction.confidence == 0.85
        assert prediction.model_type == "baseline"
        assert prediction.h3_index == "89283082837ffff"
        # Check defaults
        assert prediction.district is None
        assert prediction.is_cold_start is False
        assert prediction.feature_contributions == []


class TestPredictorRegistry:
    """Tests for PredictorRegistry."""

    def test_get_available_returns_list(self):
        """Test that get_available returns a list."""
        from src.services.price_prediction import PredictorRegistry

        result = PredictorRegistry.get_available()
        assert isinstance(result, list)
        # Should have at least baseline listed
        assert len(result) >= 1

    def test_get_available_contains_model_type(self):
        """Test that each result has model_type field."""
        from src.services.price_prediction import PredictorRegistry

        result = PredictorRegistry.get_available()
        for predictor_status in result:
            assert "model_type" in predictor_status
            assert "available" in predictor_status
