"""Tests for the ReAct agent integration.

Covers:
- Router classification of cross-domain / multi-step queries → react_agent
- Router feature flag gating (REACT_AGENT_ENABLED)
- Verifier relaxed rules for ReAct responses
- ReAct system prompt construction
- ReAct agent helper functions (normalise_tool_output, evidence creation)
- Workflow registry includes REACT_AGENT
- Engine metadata includes agent_react.py
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

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
from src.services.agent_react import (
    _build_context_message,
    _build_react_system_prompt,
    _normalise_tool_output,
    _to_evidence,
)
from src.services.agent_router import RoutingEngine, routing_engine
from src.services.agent_verifier import WorkflowVerifier, workflow_verifier
from src.services.agent_workflows import WORKFLOW_REGISTRY


# ── Helpers ────────────────────────────────────────────────────────────


def _make_state(
    *,
    workflow_id: WorkflowId = WorkflowId.REACT_AGENT,
    assessments: list[CriteriaAssessment] | None = None,
    evidence: list[EvidenceItem] | None = None,
    tool_results: list[ToolExecutionResult] | None = None,
    notes: list[str] | None = None,
) -> WorkflowExecutionState:
    return WorkflowExecutionState(
        request=NormalizedAgentRequest(user_query="test"),
        decision=WorkflowDecision(workflow_id=workflow_id, reason="test"),
        assessments=assessments or [],
        evidence=evidence or [],
        tool_results=tool_results or [],
        notes=notes or [],
    )


# ================================================================== #
#  Workflow Registry
# ================================================================== #


class TestWorkflowRegistry:
    def test_react_agent_in_registry(self):
        assert WorkflowId.REACT_AGENT in WORKFLOW_REGISTRY

    def test_react_agent_has_empty_required_tools(self):
        defn = WORKFLOW_REGISTRY[WorkflowId.REACT_AGENT]
        assert defn.required_tools == []

    def test_react_agent_description(self):
        defn = WORKFLOW_REGISTRY[WorkflowId.REACT_AGENT]
        assert (
            "cross-domain" in defn.description.lower()
            or "react" in defn.description.lower()
        )


# ================================================================== #
#  Router — react_agent keyword fallback
# ================================================================== #


class TestRouterReactKeywordFallback:
    """Test that multi-domain / complex queries route to react_agent via keyword fallback."""

    def test_multi_domain_financial_plus_listing(self):
        """Query spanning financial + location domains → react_agent."""
        request = NormalizedAgentRequest(user_query="คำนวณ ROI แล้วดูทำเลแถวบางนาให้ด้วย")
        decision = routing_engine.route(request)
        # Should match financial keywords + location keywords → multi-domain → react_agent
        assert decision.workflow_id == WorkflowId.REACT_AGENT

    def test_multi_domain_legal_plus_location(self):
        """Query spanning legal + location domains → react_agent."""
        request = NormalizedAgentRequest(
            user_query="ดูทำเลแถวอารีย์ แล้วช่วยเช็คกฎหมายซื้อขายที่ดินด้วย"
        )
        decision = routing_engine.route(request)
        assert decision.workflow_id == WorkflowId.REACT_AGENT

    def test_multi_domain_compare_plus_financial(self):
        """Query spanning comparison + financial domains → react_agent."""
        request = NormalizedAgentRequest(
            user_query="compare ROI of investing in Silom versus Ari area"
        )
        decision = routing_engine.route(request)
        assert decision.workflow_id == WorkflowId.REACT_AGENT

    def test_open_ended_exploration(self):
        """Open-ended investment exploration query → react_agent."""
        request = NormalizedAgentRequest(
            user_query="best area to invest in Bangkok for rental yield"
        )
        decision = routing_engine.route(request)
        assert decision.workflow_id == WorkflowId.REACT_AGENT

    def test_single_domain_stays_specific(self):
        """Single-domain query should NOT route to react_agent."""
        request = NormalizedAgentRequest(user_query="คำนวณ DSR เงินเดือน 50000 ดอกเบี้ย 6%")
        decision = routing_engine.route(request)
        assert decision.workflow_id == WorkflowId.FINANCIAL_ANALYSIS

    def test_simple_query_stays_general(self):
        """Simple greeting should NOT route to react_agent."""
        request = NormalizedAgentRequest(user_query="สวัสดีครับ")
        decision = routing_engine.route(request)
        assert decision.workflow_id == WorkflowId.GENERAL_GUIDED


class TestRouterReactFeatureFlag:
    """Test that REACT_AGENT_ENABLED feature flag gates the ReAct path."""

    def test_llm_route_react_disabled_falls_back(self):
        """When feature flag is off, LLM-routed react_agent → general_guided."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = (
            '{"workflow_id": "react_agent", "confidence": 0.9, '
            '"reason": "Complex cross-domain query"}'
        )
        mock_llm.invoke.return_value = mock_response

        request = NormalizedAgentRequest(user_query="complex query")
        engine = RoutingEngine()

        with patch("src.services.agent_router.agent_settings") as mock_settings:
            mock_settings.REACT_AGENT_ENABLED = False
            decision = engine.route(request, router_llm=mock_llm)

        assert decision.workflow_id == WorkflowId.GENERAL_GUIDED
        assert "react_agent disabled" in decision.reason

    def test_llm_route_react_enabled_passes_through(self):
        """When feature flag is on, LLM-routed react_agent passes through."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = (
            '{"workflow_id": "react_agent", "confidence": 0.9, '
            '"reason": "Complex cross-domain query"}'
        )
        mock_llm.invoke.return_value = mock_response

        request = NormalizedAgentRequest(user_query="complex query")
        engine = RoutingEngine()

        with patch("src.services.agent_router.agent_settings") as mock_settings:
            mock_settings.REACT_AGENT_ENABLED = True
            decision = engine.route(request, router_llm=mock_llm)

        assert decision.workflow_id == WorkflowId.REACT_AGENT

    def test_keyword_fallback_react_disabled(self):
        """When feature flag is off, keyword fallback never returns react_agent."""
        request = NormalizedAgentRequest(
            user_query="หาคอนโดงบ 5 ล้าน แล้วคำนวณ ROI ให้ด้วย"
        )

        with patch("src.services.agent_router.agent_settings") as mock_settings:
            mock_settings.REACT_AGENT_ENABLED = False
            engine = RoutingEngine()
            decision = engine.route(request)

        assert decision.workflow_id != WorkflowId.REACT_AGENT


# ================================================================== #
#  Verifier — relaxed rules for ReAct
# ================================================================== #


class TestVerifierReact:
    """Test that the verifier uses relaxed rules for react_agent responses."""

    def test_react_passes_without_sections(self):
        """ReAct response should pass even without required section headings."""
        state = _make_state(workflow_id=WorkflowId.REACT_AGENT)
        text = (
            "Based on my analysis, here are the results:\n\n"
            "1. Property A costs 5M THB with 4% yield\n"
            "2. Property B costs 3M THB with 5% yield\n\n"
            "I recommend Property B for better ROI."
        )
        result = workflow_verifier.verify(state, text)
        assert result.status == VerificationStatus.PASS

    def test_react_repair_when_too_short(self):
        """ReAct response should still fail if way too short."""
        state = _make_state(workflow_id=WorkflowId.REACT_AGENT)
        text = "OK."
        result = workflow_verifier.verify(state, text)
        assert result.status == VerificationStatus.REPAIR
        assert "too short" in (result.message or "").lower()

    def test_react_partial_on_error(self):
        """ReAct response gets PARTIAL when agent had an error."""
        state = _make_state(
            workflow_id=WorkflowId.REACT_AGENT,
            notes=["WARNING_REACT_ERROR: Timeout"],
        )
        text = "Something went wrong, please try again." + " " * 50
        result = workflow_verifier.verify(state, text)
        assert result.status == VerificationStatus.PARTIAL

    def test_react_repair_when_no_data_not_acknowledged(self):
        """ReAct response should REPAIR if no-data warning exists but not acknowledged."""
        state = _make_state(
            workflow_id=WorkflowId.REACT_AGENT,
            notes=["WARNING_NO_DATA: Tools returned no matching data for this query"],
        )
        text = (
            "Here are the best properties in your area with excellent ROI "
            "and wonderful amenities nearby. I recommend buying immediately."
        )
        result = workflow_verifier.verify(state, text)
        assert result.status == VerificationStatus.REPAIR

    def test_react_passes_when_no_data_acknowledged(self):
        """ReAct response passes if no-data warning exists and is acknowledged."""
        state = _make_state(
            workflow_id=WorkflowId.REACT_AGENT,
            notes=["WARNING_NO_DATA: Tools returned no matching data for this query"],
        )
        text = "ไม่พบข้อมูลที่ตรงกับเงื่อนไขที่ระบุ กรุณาลองปรับคำค้นหา หรือขยายพื้นที่ในการค้นหา"
        result = workflow_verifier.verify(state, text)
        assert result.status == VerificationStatus.PASS

    def test_deterministic_still_requires_sections(self):
        """Non-ReAct workflows should still require section headings."""
        state = _make_state(workflow_id=WorkflowId.GENERAL_GUIDED)
        text = (
            "Based on my analysis, here are the results:\n\n"
            "1. Property A costs 5M THB\n"
            "2. Property B costs 3M THB\n\n"
            "I recommend Property B. This is a long enough response to pass length check easily."
        )
        result = workflow_verifier.verify(state, text)
        assert result.status == VerificationStatus.REPAIR
        assert result.missing_sections


# ================================================================== #
#  ReAct system prompt
# ================================================================== #


class TestReactSystemPrompt:
    def test_system_prompt_includes_max_iterations(self):
        prompt = _build_react_system_prompt()
        # Should contain the actual number, not the placeholder
        assert "{max_iterations}" not in prompt
        assert "tool calls" in prompt.lower()

    def test_system_prompt_includes_guardrails(self):
        prompt = _build_react_system_prompt()
        assert "Always use tools" in prompt
        assert "fabricate" in prompt.lower()
        assert "ไม่ใช่คำปรึกษากฎหมาย" in prompt


# ================================================================== #
#  ReAct helper functions
# ================================================================== #


class TestNormaliseToolOutput:
    def test_dict_passthrough(self):
        result = _normalise_tool_output({"key": "value"})
        assert result == {"key": "value"}

    def test_json_string(self):
        result = _normalise_tool_output('{"key": "value"}')
        assert result == {"key": "value"}

    def test_plain_string(self):
        result = _normalise_tool_output("some text output")
        assert result == {"text": "some text output"}

    def test_non_dict_json(self):
        result = _normalise_tool_output("[1, 2, 3]")
        assert result == {"data": [1, 2, 3]}

    def test_object_with_content_attr(self):
        msg = MagicMock()
        msg.content = '{"result": true}'
        result = _normalise_tool_output(msg)
        assert result == {"result": True}

    def test_arbitrary_object(self):
        result = _normalise_tool_output(42)
        assert result == {"data": "42"}


class TestToEvidence:
    def test_creates_evidence_for_success(self):
        items = _to_evidence("search_properties", {"properties": [{"id": 1}]})
        assert len(items) == 1
        assert items[0].kind == "tool:search_properties"
        assert items[0].source_id == "search_properties"

    def test_no_evidence_for_error(self):
        items = _to_evidence("search_properties", {"error": "Not found"})
        assert items == []


class TestBuildContextMessage:
    def test_empty_context(self):
        request = NormalizedAgentRequest(user_query="test")
        result = _build_context_message(request)
        assert result == ""

    def test_spatial_context(self):
        request = NormalizedAgentRequest(
            user_query="test",
            spatial_context="PIN LOCATION: lat=13.7, lon=100.5",
        )
        result = _build_context_message(request)
        assert "Spatial context" in result
        assert "lat=13.7" in result

    def test_session_summary(self):
        request = NormalizedAgentRequest(
            user_query="test",
            session_summary="User is interested in Sukhumvit condos.",
        )
        result = _build_context_message(request)
        assert "Conversation summary" in result
        assert "Sukhumvit" in result

    def test_both_context(self):
        request = NormalizedAgentRequest(
            user_query="test",
            spatial_context="PIN LOCATION: lat=13.7, lon=100.5",
            session_summary="User interested in condos.",
        )
        result = _build_context_message(request)
        assert "Spatial context" in result
        assert "Conversation summary" in result


# ================================================================== #
#  Engine metadata
# ================================================================== #


class TestEngineMetadata:
    def test_metadata_includes_agent_react(self):
        """The agent_react.py file should be in the metadata source list."""
        from src.services.agent_runtime_metadata import _metadata_source_files

        file_names = [p.name for p in _metadata_source_files()]
        assert "agent_react.py" in file_names
