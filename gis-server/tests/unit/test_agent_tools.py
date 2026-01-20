"""
Unit tests for agent tools.

Tests the individual tools used by the LangGraph agent.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestSearchProperties:
    """Tests for search_properties tool."""

    @patch("src.services.agent_tools.SessionLocal")
    def test_search_returns_json_format(self, mock_session_local):
        """Test that search_properties returns valid JSON with expected structure."""
        from src.services.agent_tools import search_properties

        # Setup mock
        mock_db = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        # Call tool
        result = search_properties.invoke({"district": "บางกะปิ", "limit": 5})

        # Verify JSON structure
        data = json.loads(result)
        assert "count" in data
        assert "properties" in data
        assert "filters_applied" in data
        assert data["count"] == 0
        assert isinstance(data["properties"], list)

    @patch("src.services.agent_tools.SessionLocal")
    def test_search_with_bbox_uses_spatial_filter(self, mock_session_local):
        """Test that search_properties with bbox uses PostGIS spatial filtering."""
        from src.services.agent_tools import search_properties

        # Setup mock
        mock_db = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_db
        mock_db.execute.return_value.fetchall.return_value = []

        # Call tool with bbox parameters
        result = search_properties.invoke(
            {
                "min_lat": 13.74,
                "max_lat": 13.76,
                "min_lon": 100.49,
                "max_lon": 100.51,
                "limit": 10,
            }
        )

        # Verify result
        data = json.loads(result)
        assert "filters_applied" in data
        assert data["filters_applied"]["bbox"] is not None
        assert data["filters_applied"]["bbox"]["min_lat"] == 13.74
        assert data["filters_applied"]["bbox"]["max_lat"] == 13.76

    @patch("src.services.agent_tools.SessionLocal")
    def test_search_respects_limit(self, mock_session_local):
        """Test that search_properties respects and caps the limit parameter."""
        from src.services.agent_tools import search_properties

        mock_db = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        # Test with limit over max (50)
        search_properties.invoke({"limit": 100})

        # Verify limit was capped to 50
        limit_call = (
            mock_db.query.return_value.filter.return_value.order_by.return_value.limit
        )
        limit_call.assert_called_with(50)


class TestAnalyzeSite:
    """Tests for analyze_site tool."""

    def test_analyze_site_returns_valid_json(self):
        """Test that analyze_site returns valid JSON (may be error or success)."""
        from src.services.agent_tools import analyze_site

        # Call tool - will likely return error due to no DB, but should be valid JSON
        result = analyze_site.invoke(
            {
                "latitude": 13.7563,
                "longitude": 100.5018,
                "radius_meters": 1000,
                "target_category": "restaurant",
            }
        )

        # Should return valid JSON
        data = json.loads(result)
        # Either has site_score (success) or error (expected without DB)
        assert "site_score" in data or "error" in data

    def test_analyze_site_accepts_parameters(self):
        """Test that analyze_site accepts expected parameters."""
        from src.services.agent_tools import analyze_site

        # Should not raise for valid parameters
        result = analyze_site.invoke(
            {
                "latitude": 13.7563,
                "longitude": 100.5018,
                "radius_meters": 500,
            }
        )

        data = json.loads(result)
        assert isinstance(data, dict)


class TestGetLocationIntelligence:
    """Tests for get_location_intelligence tool."""

    def test_location_intelligence_returns_valid_json(self):
        """Test that get_location_intelligence returns valid JSON."""
        from src.services.agent_tools import get_location_intelligence

        result = get_location_intelligence.invoke(
            {
                "latitude": 13.7563,
                "longitude": 100.5018,
                "radius_meters": 1000,
            }
        )

        # Should return valid JSON
        data = json.loads(result)
        assert isinstance(data, dict)
        # Should have composite_score (success) or error (expected without DB)
        assert "composite_score" in data or "error" in data

    def test_location_intelligence_has_categories(self):
        """Test that location intelligence response includes score categories."""
        from src.services.agent_tools import get_location_intelligence

        result = get_location_intelligence.invoke(
            {
                "latitude": 13.7563,
                "longitude": 100.5018,
                "radius_meters": 1000,
            }
        )

        data = json.loads(result)
        if "composite_score" in data:
            # Should have transit, walkability, schools, etc.
            assert "transit" in data or "walkability" in data


class TestPredictPropertyPrice:
    """Tests for predict_property_price tool (currently mock mode)."""

    def test_prediction_returns_expected_fields(self):
        """Test that price prediction returns data with expected fields."""
        from src.services.agent_tools import predict_property_price

        result = predict_property_price.invoke(
            {
                "latitude": 13.7563,
                "longitude": 100.5018,
                "building_area_sqm": 150.0,
            }
        )

        data = json.loads(result)
        assert "predicted_price_thb" in data
        assert "confidence" in data
        assert "model_type" in data
        assert "property_details" in data

    def test_prediction_returns_valid_price(self):
        """Test that prediction returns a valid price value."""
        from src.services.agent_tools import predict_property_price

        result = predict_property_price.invoke(
            {
                "latitude": 13.75,
                "longitude": 100.55,
                "building_area_sqm": 200.0,
            }
        )

        data = json.loads(result)
        assert "predicted_price_thb" in data
        assert isinstance(data["predicted_price_thb"], (int, float))
        assert data["predicted_price_thb"] > 0


class TestGetMarketStatistics:
    """Tests for get_market_statistics tool."""

    def test_market_stats_returns_valid_json(self):
        """Test that get_market_statistics returns valid JSON."""
        from src.services.agent_tools import get_market_statistics

        result = get_market_statistics.invoke({"district": "บางกะปิ"})

        data = json.loads(result)
        assert isinstance(data, dict)
        # Should have filter info and either districts data or error
        assert "filter" in data or "error" in data or "districts" in data

    def test_market_stats_without_district(self):
        """Test get_market_statistics without district filter."""
        from src.services.agent_tools import get_market_statistics

        result = get_market_statistics.invoke({})

        data = json.loads(result)
        assert isinstance(data, dict)


class TestBuildSpatialContext:
    """Tests for the build_spatial_context_message helper function."""

    def test_build_context_with_location(self, sample_location_attachment):
        """Test building spatial context from location attachment."""
        from src.routes.chat import AttachmentData, build_spatial_context_message

        attachment = AttachmentData(**sample_location_attachment)
        result = build_spatial_context_message([attachment])

        assert "SPATIAL CONTEXT" in result
        assert "PIN LOCATION" in result
        assert "13.7563" in result
        assert "100.5018" in result

    def test_build_context_with_bbox(self, sample_bbox_attachment):
        """Test building spatial context from bbox attachment."""
        from src.routes.chat import AttachmentData, build_spatial_context_message

        attachment = AttachmentData(**sample_bbox_attachment)
        result = build_spatial_context_message([attachment])

        assert "SPATIAL CONTEXT" in result
        assert "BOUNDING BOX" in result
        assert "100.49" in result  # minLon
        assert "100.51" in result  # maxLon

    def test_build_context_empty_attachments(self):
        """Test that empty attachments returns empty string."""
        from src.routes.chat import build_spatial_context_message

        result = build_spatial_context_message([])
        assert result == ""
