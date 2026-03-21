"""Deterministic workflow registry for the rewritten agent."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.services.agent_contracts import WorkflowId


@dataclass(frozen=True)
class WorkflowDefinition:
    workflow_id: WorkflowId
    description: str
    required_inputs: list[str] = field(default_factory=list)
    allowed_assumptions: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    response_contract: str = "concise"


WORKFLOW_REGISTRY: dict[WorkflowId, WorkflowDefinition] = {
    WorkflowId.LISTING_SEARCH: WorkflowDefinition(
        workflow_id=WorkflowId.LISTING_SEARCH,
        description="Find and rank matching property candidates",
        required_inputs=["user_query"],
        allowed_assumptions=["partial unsupported criteria allowed"],
        required_tools=[
            "search_properties",
            "query_internal_knowledge",
            "compare_candidates_by_criteria",
        ],
        response_contract="shortlist",
    ),
    WorkflowId.COMPARATIVE_SCORECARD: WorkflowDefinition(
        workflow_id=WorkflowId.COMPARATIVE_SCORECARD,
        description="Compare named areas or projects against explicit criteria",
        required_inputs=["user_query"],
        allowed_assumptions=["proxy-based comparison allowed if labeled"],
        required_tools=[
            "get_market_statistics",
            "query_internal_knowledge",
            "compare_candidates_by_criteria",
        ],
        response_contract="comparative_scorecard",
    ),
    WorkflowId.FINANCIAL_ANALYSIS: WorkflowDefinition(
        workflow_id=WorkflowId.FINANCIAL_ANALYSIS,
        description="Run affordability, DSR, ROI, or break-even analysis",
        required_inputs=["user_query"],
        allowed_assumptions=["bounded financial assumptions allowed"],
        required_tools=[
            "compute_dsr_and_affordability",
            "compute_financial_projection",
            "query_internal_knowledge",
        ],
        response_contract="financial_table",
    ),
    WorkflowId.LEGAL_GUIDANCE: WorkflowDefinition(
        workflow_id=WorkflowId.LEGAL_GUIDANCE,
        description="Provide structured Thai property legal guidance",
        required_inputs=["user_query"],
        allowed_assumptions=["general info only"],
        required_tools=[
            "legal_estate_sale_checklist_th",
            "query_internal_knowledge",
        ],
        response_contract="legal_checklist",
    ),
    WorkflowId.LOCATION_ANALYSIS: WorkflowDefinition(
        workflow_id=WorkflowId.LOCATION_ANALYSIS,
        description="Analyze location quality, accessibility, and catchment",
        required_inputs=["user_query"],
        allowed_assumptions=["geocode named place if coordinates absent"],
        required_tools=[
            "geocode_place_nominatim",
            "get_location_intelligence",
            "analyze_catchment",
            "analyze_site",
        ],
        response_contract="comparative_scorecard",
    ),
    WorkflowId.GENERAL_GUIDED: WorkflowDefinition(
        workflow_id=WorkflowId.GENERAL_GUIDED,
        description="Fallback guided response with minimal claims",
        required_inputs=["user_query"],
        required_tools=["retrieve_knowledge"],
        response_contract="concise",
    ),
}
