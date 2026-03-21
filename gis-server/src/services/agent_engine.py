"""Deterministic workflow engine for the rewritten chat agent."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

from src.services.agent_composer import response_composer
from src.services.agent_contracts import (
    CriteriaAssessment,
    CriteriaStatus,
    WorkflowExecutionState,
)
from src.services.agent_normalizer import normalize_agent_request
from src.services.agent_router import routing_engine
from src.services.agent_runtime_metadata import get_agent_engine_metadata
from src.services.agent_runtime import tool_runtime
from src.services.agent_verifier import workflow_verifier
from src.services.agent_workflows import WorkflowId
from src.services.model_provider import (
    RuntimeModelConfig,
    get_model_provider,
    resolve_runtime_config,
)


class WorkflowEngine:
    async def astream(
        self,
        messages: list[dict[str, Any]],
        attachments: list[dict[str, Any]] | None = None,
        runtime_config: RuntimeModelConfig | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        request = normalize_agent_request(messages, attachments)
        decision = routing_engine.route(request)
        state = WorkflowExecutionState(request=request, decision=decision)
        composer_llm = self._build_composer_llm(runtime_config)
        engine_metadata = get_agent_engine_metadata()

        yield {
            "type": "decomposition",
            "content": {
                "workflow_id": decision.workflow_id.value,
                "reason": decision.reason,
                "clarification_needed": decision.clarification_needed,
                "engine": engine_metadata,
            },
        }

        if decision.clarification_needed:
            yield {
                "type": "clarification",
                "content": {
                    "questions": decision.missing_inputs,
                    "missing_constraints": decision.missing_inputs,
                    "message": decision.clarification_message
                    or "More information is required.",
                },
            }
            return

        async for event in self._run_workflow(state, composer_llm):
            yield event

    async def _run_workflow(
        self, state: WorkflowExecutionState, composer_llm: Any | None
    ) -> AsyncIterator[dict[str, Any]]:
        workflow_id = state.decision.workflow_id

        if workflow_id == WorkflowId.FINANCIAL_ANALYSIS:
            self._run_financial_workflow(state)
        elif workflow_id == WorkflowId.LEGAL_GUIDANCE:
            self._run_legal_workflow(state)
        elif workflow_id == WorkflowId.COMPARATIVE_SCORECARD:
            self._run_comparative_workflow(state)
        elif workflow_id == WorkflowId.LISTING_SEARCH:
            self._run_listing_workflow(state)
        elif workflow_id == WorkflowId.LOCATION_ANALYSIS:
            self._run_location_workflow(state)
        else:
            self._run_general_workflow(state)

        for result in state.tool_results:
            yield {
                "type": "tool_call",
                "content": {
                    "name": result.tool_name,
                    "input": result.tool_input,
                },
            }
            yield {
                "type": "tool_result",
                "content": json.dumps(result.normalized_output, ensure_ascii=False),
            }

        composed = await response_composer.compose(
            state=state,
            llm=composer_llm,
        )
        verification = workflow_verifier.verify(state, composed.text)
        final_text = composed.text
        if verification.status.value == "partial" and verification.message:
            final_text += f"\n\n[Partial Coverage] {verification.message}"
        elif verification.status.value == "repair" and verification.message:
            final_text += f"\n\n[Repair Needed] {verification.message}"

        yield {
            "type": "final",
            "content": final_text,
        }

    def _build_composer_llm(
        self, runtime_config: RuntimeModelConfig | None
    ) -> Any | None:
        try:
            resolved = resolve_runtime_config(runtime_config)
            if not resolved.is_configured:
                return None
            provider = get_model_provider(resolved.provider)
            return provider.create_chat_model(
                resolved,
                temperature=0.1,
                max_tokens=min(2200, resolved.max_tokens),
            )
        except Exception:
            return None

    def _append_result(self, state: WorkflowExecutionState, result) -> None:
        state.tool_results.append(result)
        state.evidence.extend(result.evidence_items)

    def _run_financial_workflow(self, state: WorkflowExecutionState) -> None:
        text = state.request.user_query
        numbers = [
            float(n.replace(",", ""))
            for n in re.findall(r"\d[\d,]*", text)
            if n.replace(",", "").isdigit()
        ]
        income = numbers[1] if len(numbers) > 1 else 80000.0
        debt = numbers[2] if len(numbers) > 2 else 12000.0
        dsr_result = tool_runtime.execute(
            "compute_dsr_and_affordability",
            {
                "monthly_income_thb": income,
                "existing_monthly_debt_thb": debt,
                "annual_interest_rate": 0.06,
                "tenure_years": 30,
            },
        )
        self._append_result(state, dsr_result)
        state.notes.append("Ran deterministic DSR and affordability calculation.")
        state.assessments.extend(
            [
                CriteriaAssessment(
                    criterion="DSR calculation",
                    status=CriteriaStatus.MET,
                    rationale="Computed via calculator workflow.",
                    evidence_ids=[ev.evidence_id for ev in dsr_result.evidence_items],
                ),
                CriteriaAssessment(
                    criterion="Loan affordability estimate",
                    status=CriteriaStatus.MET,
                    rationale="Estimated from income, debt, and interest assumptions.",
                    evidence_ids=[ev.evidence_id for ev in dsr_result.evidence_items],
                ),
                CriteriaAssessment(
                    criterion="Interest comparison with prepayment",
                    status=CriteriaStatus.MET,
                    rationale="Compared standard and prepayment interest totals.",
                    evidence_ids=[ev.evidence_id for ev in dsr_result.evidence_items],
                ),
            ]
        )

    def _run_legal_workflow(self, state: WorkflowExecutionState) -> None:
        checklist = tool_runtime.execute("legal_estate_sale_checklist_th", {})
        knowledge = tool_runtime.execute(
            "query_internal_knowledge",
            {
                "query": state.request.user_query,
                "domain": "legal_guidelines_th",
                "limit": 5,
            },
        )
        self._append_result(state, checklist)
        self._append_result(state, knowledge)
        state.notes.append("Used legal checklist plus curated Thai legal guidance.")
        state.assessments.extend(
            [
                CriteriaAssessment(
                    criterion="Estate administrator legal process",
                    status=CriteriaStatus.MET,
                    rationale="Covered by checklist and curated guidance.",
                    evidence_ids=[
                        ev.evidence_id
                        for ev in checklist.evidence_items + knowledge.evidence_items
                    ],
                ),
                CriteriaAssessment(
                    criterion="Conditions precedent in sale contract",
                    status=CriteriaStatus.MET,
                    rationale="Checklist includes mandatory conditions before transfer.",
                    evidence_ids=[ev.evidence_id for ev in checklist.evidence_items],
                ),
                CriteriaAssessment(
                    criterion="Deposit risk warning",
                    status=CriteriaStatus.MET,
                    rationale="Escrow/milestone caution included.",
                    evidence_ids=[ev.evidence_id for ev in checklist.evidence_items],
                ),
            ]
        )

    def _run_comparative_workflow(self, state: WorkflowExecutionState) -> None:
        text = state.request.user_query
        knowledge = tool_runtime.execute(
            "query_internal_knowledge",
            {
                "query": text,
                "domain": "neighborhood_facts",
                "limit": 6,
            },
        )
        market = tool_runtime.execute("get_market_statistics", {})
        self._append_result(state, knowledge)
        self._append_result(state, market)
        state.notes.append(
            "Compared areas using market stats and curated neighborhood proxies."
        )
        state.assessments.extend(
            [
                CriteriaAssessment(
                    criterion="Comparison targets identified",
                    status=CriteriaStatus.MET,
                    rationale="Workflow proceeded without redundant clarification.",
                    evidence_ids=[ev.evidence_id for ev in knowledge.evidence_items],
                ),
                CriteriaAssessment(
                    criterion="Market/neighborhood evidence",
                    status=CriteriaStatus.PARTIAL,
                    rationale="Used market stats and curated proxies; direct live metrics may still be unavailable.",
                    evidence_ids=[
                        ev.evidence_id
                        for ev in knowledge.evidence_items + market.evidence_items
                    ],
                ),
            ]
        )

    def _run_listing_workflow(self, state: WorkflowExecutionState) -> None:
        text = state.request.user_query
        district = None
        for candidate in ["อารีย์", "สะพานควาย", "ทองหล่อ", "หลังสวน", "พระราม 9"]:
            if candidate in text:
                district = candidate
                break
        search = tool_runtime.execute(
            "search_properties",
            {
                "district": district,
                "limit": 5,
            },
        )
        knowledge = tool_runtime.execute(
            "query_internal_knowledge",
            {
                "query": text,
                "domain": "project_metadata",
                "limit": 5,
            },
        )
        self._append_result(state, search)
        self._append_result(state, knowledge)
        state.notes.append("Combined property DB search with curated project metadata.")
        state.assessments.extend(
            [
                CriteriaAssessment(
                    criterion="Candidate shortlist",
                    status=CriteriaStatus.MET,
                    rationale="Retrieved candidates from DB and internal metadata.",
                    evidence_ids=[
                        ev.evidence_id
                        for ev in search.evidence_items + knowledge.evidence_items
                    ],
                ),
                CriteriaAssessment(
                    criterion="Project-specific special constraints",
                    status=CriteriaStatus.PARTIAL,
                    rationale="Some project metadata is curated, but not every requested field is fully covered.",
                    evidence_ids=[ev.evidence_id for ev in knowledge.evidence_items],
                ),
            ]
        )

    def _run_location_workflow(self, state: WorkflowExecutionState) -> None:
        geocoded = tool_runtime.execute(
            "query_internal_knowledge",
            {
                "query": state.request.user_query,
                "domain": "neighborhood_facts",
                "limit": 5,
            },
        )
        self._append_result(state, geocoded)
        state.notes.append(
            "Used curated location/neighborhood facts due missing direct coordinates."
        )
        state.assessments.append(
            CriteriaAssessment(
                criterion="Location analysis",
                status=CriteriaStatus.PARTIAL,
                rationale="Curated neighborhood evidence used; direct spatial tool invocation depends on explicit coordinates.",
                evidence_ids=[ev.evidence_id for ev in geocoded.evidence_items],
            )
        )

    def _run_general_workflow(self, state: WorkflowExecutionState) -> None:
        result = tool_runtime.execute(
            "retrieve_knowledge",
            {"query": state.request.user_query},
        )
        self._append_result(state, result)
        state.notes.append("Fallback guided workflow used knowledge retrieval.")
        state.assessments.append(
            CriteriaAssessment(
                criterion="General guidance",
                status=CriteriaStatus.MET,
                rationale="Returned knowledge-backed fallback guidance.",
                evidence_ids=[ev.evidence_id for ev in result.evidence_items],
            )
        )


workflow_engine = WorkflowEngine()
