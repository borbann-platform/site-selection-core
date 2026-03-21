from typing import cast

from src.services.agent_subagents import IntentRouterSubagent, ResponseVerifierSubagent


class DummyResponse:
    def __init__(self, content):
        self.content = content


class DummyLLM:
    def __init__(self, content):
        self._content = content

    def invoke(self, _prompt):
        return DummyResponse(self._content)


def test_router_uses_llm_json_response():
    router = IntentRouterSubagent()
    llm = DummyLLM(
        '{"intent":"financial_planning","needs_strict_factual_grounding":false,"should_decompose":true,"response_contract":"financial_table"}'
    )

    decision = router.classify("คำนวณ DSR", cast(object, llm))

    assert decision.intent == "financial_planning"
    assert decision.needs_strict_factual_grounding is False
    assert decision.should_decompose is True
    assert decision.response_contract == "financial_table"


def test_router_falls_back_when_llm_missing():
    router = IntentRouterSubagent()
    decision = router.classify("หาโครงการใกล้รถไฟฟ้า", None)
    assert decision.intent == "general"


def test_verifier_requires_missing_sections():
    verifier = ResponseVerifierSubagent()
    result = verifier.verify("Recommendation only", "comparative_scorecard")
    assert result.is_valid is False
    assert result.needs_repair is True
    assert "criteria" in result.missing_sections
