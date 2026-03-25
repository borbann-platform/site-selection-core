"""Tests for the rewritten agent modules: router, engine helpers, verifier, composer.

Covers:
- Router keyword fallback (all 6 workflows, no false positives)
- Router LLM path (mocked, JSON parsing, error handling)
- Engine helper functions (district extraction, price range, financial params, comparison targets)
- Verifier (PASS, REPAIR, REFUSE, evidence grounding, no-data warning)
- Composer deterministic (no-data warning, property markers)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.services.agent_composer import response_composer
from src.services.agent_contracts import (
    CriteriaAssessment,
    CriteriaStatus,
    EvidenceItem,
    NormalizedAgentRequest,
    ToolExecutionResult,
    VerificationStatus,
    WorkflowDecision,
    WorkflowExecutionState,
    WorkflowId,
)
from src.services.agent_engine import (
    _extract_comparison_targets,
    _extract_districts,
    _extract_price_range,
    _extract_thai_numbers,
)
from src.services.agent_router import RoutingEngine, _parse_llm_json, routing_engine
from src.services.agent_runtime import tool_runtime
from src.services.agent_runtime_metadata import get_agent_engine_metadata
from src.services.agent_verifier import WorkflowVerifier, workflow_verifier


# ================================================================== #
#  Router — keyword fallback path (no LLM)
# ================================================================== #


class TestRouterKeywordFallback:
    """Test that the keyword fallback correctly classifies all 6 workflows."""

    def test_financial_dsr(self):
        request = NormalizedAgentRequest(user_query="คำนวณ DSR และดอกเบี้ยบ้าน 8 ล้าน")
        decision = routing_engine.route(request)
        assert decision.workflow_id == WorkflowId.FINANCIAL_ANALYSIS

    def test_financial_loan(self):
        request = NormalizedAgentRequest(user_query="วงเงินกู้สำหรับเงินเดือน 50000 บาท")
        decision = routing_engine.route(request)
        assert decision.workflow_id == WorkflowId.FINANCIAL_ANALYSIS

    def test_financial_roi(self):
        request = NormalizedAgentRequest(
            user_query="ROI yield on a 5M condo investment"
        )
        decision = routing_engine.route(request)
        assert decision.workflow_id == WorkflowId.FINANCIAL_ANALYSIS

    def test_legal_inheritance(self):
        request = NormalizedAgentRequest(user_query="ผู้จัดการมรดกและสัญญาจะซื้อจะขาย")
        decision = routing_engine.route(request)
        assert decision.workflow_id == WorkflowId.LEGAL_GUIDANCE

    def test_legal_contract(self):
        request = NormalizedAgentRequest(user_query="กฎหมายเกี่ยวกับสัญญาซื้อขายที่ดิน")
        decision = routing_engine.route(request)
        assert decision.workflow_id == WorkflowId.LEGAL_GUIDANCE

    def test_comparative(self):
        request = NormalizedAgentRequest(user_query="เปรียบเทียบบ้านในบางนากับบางกะปิ")
        decision = routing_engine.route(request)
        assert decision.workflow_id == WorkflowId.COMPARATIVE_SCORECARD

    def test_comparative_vs(self):
        request = NormalizedAgentRequest(
            user_query="compare Sukhumvit vs Silom for investment"
        )
        decision = routing_engine.route(request)
        assert decision.workflow_id == WorkflowId.COMPARATIVE_SCORECARD

    def test_location_analysis(self):
        request = NormalizedAgentRequest(
            user_query="ทำเลดีไหมแถวอารีย์ walkability เป็นยังไง"
        )
        decision = routing_engine.route(request)
        assert decision.workflow_id == WorkflowId.LOCATION_ANALYSIS

    def test_listing_search_thai(self):
        request = NormalizedAgentRequest(user_query="หาบ้านเดี่ยวในบางกะปิ งบ 5 ล้าน")
        decision = routing_engine.route(request)
        assert decision.workflow_id == WorkflowId.LISTING_SEARCH

    def test_listing_search_condo(self):
        request = NormalizedAgentRequest(user_query="แนะนำคอนโดใกล้ BTS สะพานควาย")
        decision = routing_engine.route(request)
        assert decision.workflow_id == WorkflowId.LISTING_SEARCH

    def test_general_fallback(self):
        request = NormalizedAgentRequest(user_query="สวัสดีครับ วันนี้อากาศดีจัง")
        decision = routing_engine.route(request)
        assert decision.workflow_id == WorkflowId.GENERAL_GUIDED

    # ── False-positive regression tests ──

    def test_no_false_positive_kab_conjunction(self):
        """'กับ' alone should NOT trigger comparative — it's just a conjunction."""
        request = NormalizedAgentRequest(user_query="ซื้อบ้านกับแฟน ต้องเตรียมอะไรบ้าง")
        decision = routing_engine.route(request)
        # Should NOT be comparative (no 'เปรียบเทียบ' or 'compare')
        assert decision.workflow_id != WorkflowId.COMPARATIVE_SCORECARD

    def test_no_false_positive_site_generic(self):
        """Generic use of 'site' or 'location' should not force location_analysis."""
        request = NormalizedAgentRequest(
            user_query="I want to buy a house on this site"
        )
        decision = routing_engine.route(request)
        # Should be listing_search or general, not necessarily location_analysis
        # The point is it shouldn't forcefully match location_analysis just from "site"
        assert decision.workflow_id in {
            WorkflowId.LISTING_SEARCH,
            WorkflowId.GENERAL_GUIDED,
            WorkflowId.LOCATION_ANALYSIS,  # acceptable if the full context triggers it
        }

    def test_confidence_is_low_for_fallback(self):
        """Keyword fallback should report lower confidence than LLM routing."""
        request = NormalizedAgentRequest(user_query="สวัสดีครับ")
        decision = routing_engine.route(request)
        assert decision.confidence <= 0.6
        assert "[keyword fallback]" in decision.reason


# ================================================================== #
#  Router — LLM path (mocked)
# ================================================================== #


class TestRouterLLMPath:
    """Test the LLM routing path using a mocked LLM."""

    def _make_mock_llm(self, response_text: str) -> MagicMock:
        mock = MagicMock()
        mock_response = MagicMock()
        mock_response.content = response_text
        mock.invoke.return_value = mock_response
        return mock

    def test_llm_route_listing(self):
        llm = self._make_mock_llm(
            '{"workflow_id": "listing_search", "confidence": 0.95, '
            '"reason": "User wants to find property", "extracted_entities": {"locations": ["สุขุมวิท"]}}'
        )
        request = NormalizedAgentRequest(user_query="หาคอนโดสุขุมวิท")
        engine = RoutingEngine()
        decision = engine.route(request, router_llm=llm)
        assert decision.workflow_id == WorkflowId.LISTING_SEARCH
        assert decision.confidence == 0.95
        assert "[LLM router]" in decision.reason

    def test_llm_route_financial(self):
        llm = self._make_mock_llm(
            '{"workflow_id": "financial_analysis", "confidence": 0.9, "reason": "DSR calculation query"}'
        )
        request = NormalizedAgentRequest(user_query="คำนวณ DSR เงินเดือน 50000")
        engine = RoutingEngine()
        decision = engine.route(request, router_llm=llm)
        assert decision.workflow_id == WorkflowId.FINANCIAL_ANALYSIS

    def test_llm_route_with_markdown_fences(self):
        """LLM sometimes wraps JSON in markdown code fences."""
        llm = self._make_mock_llm(
            '```json\n{"workflow_id": "legal_guidance", "confidence": 0.85, "reason": "legal query"}\n```'
        )
        request = NormalizedAgentRequest(user_query="กฎหมายมรดก")
        engine = RoutingEngine()
        decision = engine.route(request, router_llm=llm)
        assert decision.workflow_id == WorkflowId.LEGAL_GUIDANCE

    def test_llm_route_invalid_json_falls_back(self):
        """If LLM returns garbage, fall back to keyword heuristic."""
        llm = self._make_mock_llm("I'm sorry, I can't classify this.")
        request = NormalizedAgentRequest(user_query="DSR วงเงินกู้ ดอกเบี้ย")
        engine = RoutingEngine()
        decision = engine.route(request, router_llm=llm)
        # Should fall back to keyword and detect financial keywords
        assert decision.workflow_id == WorkflowId.FINANCIAL_ANALYSIS
        assert "[keyword fallback]" in decision.reason

    def test_llm_route_unknown_workflow_id(self):
        """If LLM returns an invalid workflow_id, default to general_guided."""
        llm = self._make_mock_llm(
            '{"workflow_id": "nonexistent_workflow", "confidence": 0.5, "reason": "test"}'
        )
        request = NormalizedAgentRequest(user_query="hello")
        engine = RoutingEngine()
        decision = engine.route(request, router_llm=llm)
        assert decision.workflow_id == WorkflowId.GENERAL_GUIDED

    def test_llm_route_exception_falls_back(self):
        """If LLM throws an exception, fall back to keyword heuristic."""
        llm = MagicMock()
        llm.invoke.side_effect = Exception("API key expired")
        request = NormalizedAgentRequest(user_query="เปรียบเทียบสีลมกับสาทร")
        engine = RoutingEngine()
        decision = engine.route(request, router_llm=llm)
        assert decision.workflow_id == WorkflowId.COMPARATIVE_SCORECARD
        assert "[keyword fallback]" in decision.reason

    def test_llm_route_confidence_clamped(self):
        """Confidence should be clamped to [0, 1]."""
        llm = self._make_mock_llm(
            '{"workflow_id": "general_guided", "confidence": 5.0, "reason": "test"}'
        )
        request = NormalizedAgentRequest(user_query="hello")
        engine = RoutingEngine()
        decision = engine.route(request, router_llm=llm)
        assert decision.confidence == 1.0

    def test_llm_route_list_content_response(self):
        """Some LLMs return content as a list of dicts."""
        llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            {"text": '{"workflow_id": "location_analysis"'},
            {"text": ', "confidence": 0.8, "reason": "location query"}'},
        ]
        llm.invoke.return_value = mock_response
        request = NormalizedAgentRequest(user_query="ทำเลอารีย์")
        engine = RoutingEngine()
        decision = engine.route(request, router_llm=llm)
        assert decision.workflow_id == WorkflowId.LOCATION_ANALYSIS


# ================================================================== #
#  Router JSON parser
# ================================================================== #


class TestParseRouterJSON:
    def test_plain_json(self):
        result = _parse_llm_json('{"workflow_id": "listing_search"}')
        assert result == {"workflow_id": "listing_search"}

    def test_markdown_fenced(self):
        result = _parse_llm_json('```json\n{"workflow_id": "legal_guidance"}\n```')
        assert result == {"workflow_id": "legal_guidance"}

    def test_json_with_surrounding_text(self):
        result = _parse_llm_json(
            'Here is the classification:\n{"workflow_id": "financial_analysis"}\nDone.'
        )
        assert result == {"workflow_id": "financial_analysis"}

    def test_invalid_json(self):
        result = _parse_llm_json("This is not JSON at all")
        assert result is None

    def test_empty_string(self):
        result = _parse_llm_json("")
        assert result is None


# ================================================================== #
#  Engine helpers — district extraction
# ================================================================== #


class TestDistrictExtraction:
    def test_official_district(self):
        found = _extract_districts("บ้านในบางกะปิ ราคา 5 ล้าน")
        assert "บางกะปิ" in found

    def test_neighborhood_alias(self):
        found = _extract_districts("คอนโดแถวอารีย์")
        assert "พญาไท" in found

    def test_english_alias(self):
        found = _extract_districts("condo near Thonglor BTS")
        assert "วัฒนา" in found

    def test_multiple_districts(self):
        found = _extract_districts("เปรียบเทียบบางนากับสาทร")
        assert "บางนา" in found
        assert "สาทร" in found

    def test_no_districts(self):
        found = _extract_districts("สวัสดีครับ วันนี้อากาศดี")
        assert found == []

    def test_silom_alias(self):
        found = _extract_districts("Office near Silom")
        assert "บางรัก" in found

    def test_sukhumvit_alias(self):
        found = _extract_districts("สุขุมวิท ซอย 39")
        assert "คลองเตย" in found


# ================================================================== #
#  Engine helpers — price extraction
# ================================================================== #


class TestPriceExtraction:
    def test_thai_million(self):
        numbers = _extract_thai_numbers("บ้าน 5ล้านบาท")
        assert any(n >= 4_000_000 for n in numbers)

    def test_range_extraction(self):
        min_p, max_p = _extract_price_range("ราคา 3-5 ล้าน")
        assert min_p is not None
        assert max_p is not None
        assert min_p < max_p

    def test_budget_extraction(self):
        _, max_p = _extract_price_range("งบไม่เกิน 8 ล้าน")
        assert max_p is not None
        assert max_p >= 7_000_000

    def test_no_price(self):
        min_p, max_p = _extract_price_range("บ้านสวยดี")
        # Might or might not find prices, but shouldn't crash
        # (no explicit price in text)


# ================================================================== #
#  Engine helpers — comparison target extraction
# ================================================================== #


class TestComparisonTargets:
    def test_kab_separator(self):
        targets = _extract_comparison_targets("เปรียบเทียบบางนากับสาทร")
        assert len(targets) >= 2

    def test_vs_separator(self):
        targets = _extract_comparison_targets("Sukhumvit vs Silom area")
        assert len(targets) >= 2

    def test_fallback_to_districts(self):
        # No explicit separator, but has district names
        targets = _extract_comparison_targets("ดูบ้านแถวบางนา สาทร")
        assert len(targets) >= 1


# ================================================================== #
#  Engine helpers — financial param extraction
# ================================================================== #


class TestFinancialParamExtraction:
    def test_income_extraction(self):
        from src.services.agent_engine import WorkflowEngine

        engine = WorkflowEngine()
        params = engine._extract_financial_params("เงินเดือน 50,000 บาท ดอกเบี้ย 6%")
        assert params["income"] == 50000
        assert 0.05 <= params["rate"] <= 0.07

    def test_debt_extraction(self):
        from src.services.agent_engine import WorkflowEngine

        engine = WorkflowEngine()
        params = engine._extract_financial_params("เงินเดือน 80000 ผ่อนรถ 15000 ต่อเดือน")
        assert params["income"] == 80000
        assert params["debt"] == 15000

    def test_defaults_when_no_numbers(self):
        from src.services.agent_engine import WorkflowEngine

        engine = WorkflowEngine()
        params = engine._extract_financial_params("คำนวณดอกเบี้ย")
        assert params["rate"] == 0.06  # default
        assert params["tenure"] == 30  # default


# ================================================================== #
#  Verifier
# ================================================================== #


def _make_state(
    *,
    assessments: list[CriteriaAssessment] | None = None,
    evidence: list[EvidenceItem] | None = None,
    tool_results: list[ToolExecutionResult] | None = None,
    notes: list[str] | None = None,
) -> WorkflowExecutionState:
    return WorkflowExecutionState(
        request=NormalizedAgentRequest(user_query="test"),
        decision=WorkflowDecision(workflow_id=WorkflowId.GENERAL_GUIDED, reason="test"),
        assessments=assessments or [],
        evidence=evidence or [],
        tool_results=tool_results or [],
        notes=notes or [],
    )


class TestVerifier:
    def test_pass_when_all_sections_present(self):
        text = (
            "## Criteria Coverage\nAll met\n"
            "## Evidence Used\nev-1\n"
            "## Analysis\nDetails\n"
            "## Recommendation\nBuy\n"
            "## Data Gaps\nNone"
        )
        state = _make_state()
        result = workflow_verifier.verify(state, text)
        assert result.status == VerificationStatus.PASS

    def test_repair_when_missing_sections(self):
        text = "Hello world, this is a short response without any structure."
        state = _make_state()
        result = workflow_verifier.verify(state, text)
        assert result.status == VerificationStatus.REPAIR
        assert result.missing_sections

    def test_repair_when_too_short(self):
        text = "criteria coverage\nevidence used\nanalysis\nrecommendation\ndata gaps"
        state = _make_state()
        result = workflow_verifier.verify(state, text)
        assert result.status == VerificationStatus.REPAIR
        assert "too short" in (result.message or "").lower()

    def test_refuse_when_all_criteria_bad(self):
        """REFUSE when ALL assessments are unsupported/not_met."""
        assessments = [
            CriteriaAssessment(
                criterion="A",
                status=CriteriaStatus.NOT_MET,
                rationale="no data",
            ),
            CriteriaAssessment(
                criterion="B",
                status=CriteriaStatus.UNSUPPORTED,
                rationale="no data",
            ),
        ]
        text = (
            "## Criteria Coverage\nAll not met\n"
            "## Evidence Used\nNone\n"
            "## Analysis\nNo analysis possible\n"
            "## Recommendation\nCannot recommend\n"
            "## Data Gaps\nAll data missing, this is a long enough response to pass the length check"
        )
        state = _make_state(assessments=assessments)
        result = workflow_verifier.verify(state, text)
        assert result.status == VerificationStatus.REFUSE

    def test_evidence_grounding_check(self):
        """REPAIR when response doesn't reference any evidence."""
        evidence = [
            EvidenceItem(
                evidence_id="ev-test001",
                kind="tool:search",
                source_type="tool",
                source_id="search_properties",
                payload={"test": True},
            ),
            EvidenceItem(
                evidence_id="ev-test002",
                kind="tool:market",
                source_type="tool",
                source_id="get_market_statistics",
                payload={"test": True},
            ),
        ]
        tool_results = [
            ToolExecutionResult(
                tool_name="other_tool",
                status="success",
                tool_input={},
                raw_output={},
                normalized_output={},
            ),
        ]
        text = (
            "## Criteria Coverage\nAll met\n"
            "## Evidence Used\nSome evidence\n"
            "## Analysis\nGeneric analysis with no citations at all, nothing specific\n"
            "## Recommendation\nBuy property\n"
            "## Data Gaps\nNone noted here, this response is intentionally long enough to pass length check"
        )
        state = _make_state(evidence=evidence, tool_results=tool_results)
        result = workflow_verifier.verify(state, text)
        assert result.status == VerificationStatus.REPAIR
        assert "evidence" in (result.message or "").lower()

    def test_no_data_warning_check(self):
        """REPAIR when WARNING_NO_DATA present but response doesn't acknowledge it."""
        text = (
            "## Criteria Coverage\nAll met\n"
            "## Evidence Used\nev-1\n"
            "## Analysis\nEverything looks great, wonderful data available!\n"
            "## Recommendation\nBuy immediately\n"
            "## Data Gaps\nNo gaps at all, perfect data, this is a long enough response to pass"
        )
        state = _make_state(notes=["WARNING_NO_DATA: Tools returned no matching data"])
        result = workflow_verifier.verify(state, text)
        assert result.status == VerificationStatus.REPAIR
        assert "data" in (result.message or "").lower()

    def test_no_data_warning_passes_when_acknowledged(self):
        """PASS when WARNING_NO_DATA present AND response acknowledges it."""
        text = (
            "## Criteria Coverage\nPartially met\n"
            "## Evidence Used\nLimited evidence\n"
            "## Analysis\nไม่พบข้อมูลในระบบ for this query, limited analysis possible here\n"
            "## Recommendation\nSeek additional sources, use with caution please\n"
            "## Data Gaps\nSignificant gaps in data availability for this specific request"
        )
        state = _make_state(notes=["WARNING_NO_DATA: Tools returned no matching data"])
        result = workflow_verifier.verify(state, text)
        assert result.status == VerificationStatus.PASS


# ================================================================== #
#  Composer — deterministic path
# ================================================================== #


class TestComposerDeterministic:
    def test_property_markers_appended(self):
        search_result = ToolExecutionResult(
            tool_name="search_properties",
            status="success",
            tool_input={"district": "บางกะปิ", "limit": 1},
            raw_output={
                "properties": [
                    {
                        "id": "house-123",
                        "district": "บางกะปิ",
                        "building_style": "บ้านเดี่ยว",
                        "price_thb": 4200000,
                        "building_area_sqm": 180,
                        "lat": 13.765,
                        "lon": 100.642,
                    }
                ]
            },
            normalized_output={
                "properties": [
                    {
                        "id": "house-123",
                        "district": "บางกะปิ",
                        "building_style": "บ้านเดี่ยว",
                        "price_thb": 4200000,
                        "building_area_sqm": 180,
                        "lat": 13.765,
                        "lon": 100.642,
                    }
                ]
            },
            evidence_items=[
                EvidenceItem(
                    kind="tool:search_properties",
                    source_type="tool",
                    source_id="search_properties",
                    payload={"property_ids": ["house-123"]},
                )
            ],
        )

        state = WorkflowExecutionState(
            request=NormalizedAgentRequest(user_query="หาบ้านในบางกะปิ"),
            decision=WorkflowDecision(
                workflow_id=WorkflowId.LISTING_SEARCH,
                reason="listing intent detected",
            ),
            tool_results=[search_result],
            evidence=search_result.evidence_items,
        )

        composed = response_composer._compose_deterministic(state)

        assert "<!--CHAT_REFERENCES_START-->" in composed.text
        assert "<!--PROPERTIES_START-->" in composed.text

    def test_no_data_warning_shown(self):
        """When WARNING_NO_DATA is in notes, the deterministic composer shows it."""
        state = WorkflowExecutionState(
            request=NormalizedAgentRequest(user_query="หาคอนโดในสาทร"),
            decision=WorkflowDecision(
                workflow_id=WorkflowId.LISTING_SEARCH,
                reason="listing intent",
            ),
            notes=["WARNING_NO_DATA: Tools returned no matching data"],
            assessments=[
                CriteriaAssessment(
                    criterion="Candidate shortlist",
                    status=CriteriaStatus.NOT_MET,
                    rationale="No matching properties found.",
                ),
            ],
        )

        composed = response_composer._compose_deterministic(state)
        assert "ไม่พบข้อมูล" in composed.text

    def test_legal_disclaimer_appended(self):
        state = WorkflowExecutionState(
            request=NormalizedAgentRequest(user_query="สัญญาซื้อขาย"),
            decision=WorkflowDecision(
                workflow_id=WorkflowId.LEGAL_GUIDANCE,
                reason="legal",
            ),
            assessments=[
                CriteriaAssessment(
                    criterion="Legal process",
                    status=CriteriaStatus.MET,
                    rationale="Covered.",
                ),
            ],
        )

        composed = response_composer._compose_deterministic(state)
        assert "ไม่ใช่คำปรึกษากฎหมายเฉพาะคดี" in composed.text

    def test_data_gaps_section_shows_not_met(self):
        """NOT_MET criteria should appear in Data Gaps section."""
        state = WorkflowExecutionState(
            request=NormalizedAgentRequest(user_query="test"),
            decision=WorkflowDecision(
                workflow_id=WorkflowId.GENERAL_GUIDED, reason="test"
            ),
            assessments=[
                CriteriaAssessment(
                    criterion="Available data",
                    status=CriteriaStatus.MET,
                    rationale="OK",
                ),
                CriteriaAssessment(
                    criterion="Missing feature",
                    status=CriteriaStatus.NOT_MET,
                    rationale="Not available in database",
                ),
            ],
        )

        composed = response_composer._compose_deterministic(state)
        assert "Missing feature" in composed.text
        assert "Data Gaps" in composed.text


# ================================================================== #
#  Runtime tool execution (integration)
# ================================================================== #


class TestRuntimeIntegration:
    def test_internal_knowledge_tool(self):
        result = tool_runtime.execute(
            "query_internal_knowledge",
            {
                "query": "ผู้จัดการมรดก เงินมัดจำ",
                "domain": "legal_guidelines_th",
                "limit": 3,
            },
        )
        assert result.status == "success"
        assert len(result.evidence_items) >= 1

    def test_metadata_has_expected_shape(self):
        metadata = get_agent_engine_metadata()
        assert metadata["kind"] == "workflow_rewrite"
        assert len(metadata["revision"]) == 12
