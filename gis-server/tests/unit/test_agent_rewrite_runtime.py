from src.services.agent_contracts import NormalizedAgentRequest, WorkflowId
from src.services.agent_contracts import WorkflowDecision, WorkflowExecutionState
from src.services.agent_composer import response_composer
from src.services.agent_router import routing_engine
from src.services.agent_runtime_metadata import get_agent_engine_metadata
from src.services.agent_runtime import tool_runtime


def test_router_financial_route():
    request = NormalizedAgentRequest(user_query="คำนวณ DSR และดอกเบี้ยบ้าน 8 ล้าน")
    decision = routing_engine.route(request)
    assert decision.workflow_id == WorkflowId.FINANCIAL_ANALYSIS


def test_router_legal_route():
    request = NormalizedAgentRequest(user_query="ผู้จัดการมรดกและสัญญาจะซื้อจะขาย")
    decision = routing_engine.route(request)
    assert decision.workflow_id == WorkflowId.LEGAL_GUIDANCE


def test_runtime_executes_internal_knowledge_tool():
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


def test_runtime_metadata_has_expected_shape():
    metadata = get_agent_engine_metadata()

    assert metadata["kind"] == "workflow_rewrite"
    assert len(metadata["revision"]) == 12


def test_composer_appends_structured_property_references():
    search_result = tool_runtime.execute(
        "search_properties",
        {
            "district": "บางกะปิ",
            "limit": 1,
        },
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
