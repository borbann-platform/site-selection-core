"""Deterministic routing for rewritten workflows."""

from __future__ import annotations

import re

from src.services.agent_contracts import (
    NormalizedAgentRequest,
    WorkflowDecision,
    WorkflowId,
)
from src.services.agent_subagents import has_explicit_compare_targets


class RoutingEngine:
    def route(self, request: NormalizedAgentRequest) -> WorkflowDecision:
        text = request.user_query.lower()

        if any(
            token in text
            for token in ["กฎหมาย", "สัญญา", "มรดก", "inheritance", "legal"]
        ):
            return WorkflowDecision(
                workflow_id=WorkflowId.LEGAL_GUIDANCE,
                reason="legal intent detected",
            )

        if any(
            token in text
            for token in [
                "dsr",
                "วงเงินกู้",
                "ดอกเบี้ย",
                "break-even",
                "roi",
                "yield",
                "ผ่อน",
            ]
        ):
            return WorkflowDecision(
                workflow_id=WorkflowId.FINANCIAL_ANALYSIS,
                reason="financial intent detected",
            )

        wants_compare = any(
            token in text for token in ["compare", "เปรียบเทียบ", "versus", "vs", "กับ"]
        )
        if wants_compare or has_explicit_compare_targets(text):
            return WorkflowDecision(
                workflow_id=WorkflowId.COMPARATIVE_SCORECARD,
                reason="comparison intent detected",
            )

        if any(
            token in text
            for token in ["walkability", "catchment", "ทำเล", "location", "site"]
        ):
            return WorkflowDecision(
                workflow_id=WorkflowId.LOCATION_ANALYSIS,
                reason="location analysis intent detected",
            )

        if any(
            token in text
            for token in ["หา", "find", "คอนโด", "บ้าน", "โครงการ", "property"]
        ):
            return WorkflowDecision(
                workflow_id=WorkflowId.LISTING_SEARCH,
                reason="listing intent detected",
            )

        return WorkflowDecision(
            workflow_id=WorkflowId.GENERAL_GUIDED,
            reason="fallback guided route",
        )


routing_engine = RoutingEngine()
