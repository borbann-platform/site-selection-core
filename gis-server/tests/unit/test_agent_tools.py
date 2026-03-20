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
    def test_search_properties_returns_reference_fields(self, mock_session_local):
        from src.services.agent_tools import search_properties

        mock_db = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_db
        query = MagicMock()
        query.filter.return_value = query
        query.with_entities.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = query
        row = MagicMock()
        row.id = 42
        row.amphur = "บางกะปิ"
        row.tumbon = "หัวหมาก"
        row.building_style_desc = "บ้านเดี่ยว"
        row.building_area = 240
        row.land_area = 80
        row.building_age = 4
        row.total_price = 9500000
        row.no_of_floor = 2
        query.with_entities.return_value.order_by.return_value.limit.return_value.all.return_value = [
            (row, 100.61, 13.77)
        ]

        result = search_properties.invoke({"district": "บางกะปิ", "limit": 1})

        data = json.loads(result)
        assert data["count"] == 1
        assert data["properties"][0]["listing_key"] == "house:42"
        assert data["properties"][0]["house_ref"] == "house:42"
        assert data["properties"][0]["locator"] == "house:42"

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
        query = mock_db.query.return_value.filter.return_value
        query.with_entities.return_value.order_by.return_value.limit.return_value.all.return_value = []

        # Test with limit over max (50)
        search_properties.invoke({"limit": 100})

        # Verify limit was capped to 50
        limit_call = query.with_entities.return_value.order_by.return_value.limit
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


class TestValidateHouseReference:
    """Tests for validate_house_reference tool."""

    def test_validate_house_reference_returns_json(self):
        """Should always return valid JSON structure."""
        from src.services.agent_tools import validate_house_reference

        result = validate_house_reference.invoke(
            {
                "property_id": 12345,
                "latitude": 13.75,
                "longitude": 100.55,
            }
        )
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "is_valid" in data or "error" in data


class TestFinancialAndLegalTools:
    def test_compute_financial_projection_shape(self):
        from src.services.agent_tools import compute_financial_projection

        result = compute_financial_projection.invoke(
            {
                "asset_price_thb": 20000000,
                "loan_ratio": 0.5,
                "annual_interest_rate": 0.06,
                "annual_revenue_thb": 1800000,
                "annual_expense_thb": 600000,
            }
        )
        data = json.loads(result)
        assert "inputs" in data
        assert "derived" in data
        assert "timeline" in data

    def test_compute_dsr_shape(self):
        from src.services.agent_tools import compute_dsr_and_affordability

        result = compute_dsr_and_affordability.invoke(
            {
                "monthly_income_thb": 80000,
                "existing_monthly_debt_thb": 12000,
                "annual_interest_rate": 0.06,
                "tenure_years": 30,
            }
        )
        data = json.loads(result)
        assert "results" in data
        assert "estimated_max_loan_thb" in data["results"]

    def test_legal_checklist_has_disclaimer(self):
        from src.services.agent_tools import legal_estate_sale_checklist_th

        result = legal_estate_sale_checklist_th.invoke({})
        data = json.loads(result)
        assert "steps" in data
        assert "disclaimer" in data

    def test_compare_candidates_scores(self):
        from src.services.agent_tools import compare_candidates_by_criteria

        candidates = json.dumps(
            [
                {"name": "A", "price": 5000000, "district": "อารีย์"},
                {"name": "B", "price": 7000000, "district": "สะพานควาย"},
            ],
            ensure_ascii=False,
        )
        criteria = json.dumps(
            [
                {"field": "price", "op": "lte", "value": 6000000, "weight": 2},
                {
                    "field": "district",
                    "op": "contains",
                    "value": "อารีย์",
                    "weight": 1,
                },
            ],
            ensure_ascii=False,
        )

        result = compare_candidates_by_criteria.invoke(
            {"candidates_json": candidates, "criteria_json": criteria}
        )
        data = json.loads(result)
        assert data["count"] == 2
        assert data["ranked"][0]["candidate"]["name"] == "A"

    def test_query_internal_knowledge_returns_fixture_match(self):
        from src.services.agent_tools import query_internal_knowledge

        result = query_internal_knowledge.invoke(
            {
                "query": "ผู้จัดการมรดก เงินมัดจำ",
                "domain": "legal_guidelines_th",
                "limit": 3,
            }
        )
        data = json.loads(result)
        assert data["count"] >= 1


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
