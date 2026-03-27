"""LLM-driven intent routing for the agent workflow engine.

The router uses the same LLM the user configured (BYOK) to classify the
user's intent into one of the supported workflows.  A lightweight keyword
heuristic serves as an emergency fallback *only* when the LLM call fails.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.config.agent_settings import agent_settings
from src.services.agent_contracts import (
    NormalizedAgentRequest,
    WorkflowDecision,
    WorkflowId,
)

logger = logging.getLogger(__name__)

# ── LLM routing prompt ────────────────────────────────────────────────
_ROUTER_SYSTEM_PROMPT = """\
You are an intent classifier for a Bangkok real-estate AI assistant.

Given a user query, classify it into exactly ONE workflow and extract key entities.

## Available workflows

| workflow_id           | When to choose                                                                 |
|-----------------------|-------------------------------------------------------------------------------|
| listing_search        | User wants to find, search, or get recommendations for specific properties     |
| comparative_scorecard | User wants to compare two or more areas, districts, projects, or transit lines |
| financial_analysis    | User asks about DSR, loan, mortgage, affordability, ROI, yield, break-even, monthly payments, interest |
| legal_guidance        | User asks about Thai property law, contracts, inheritance, estate admin, title deeds |
| location_analysis     | User asks about a location's quality, walkability, catchment, neighborhood character, amenities |
| react_agent           | Complex queries that span multiple domains, require multi-step reasoning, or don't fit neatly into one workflow above |
| general_guided        | Simple general questions that don't fit any other category and don't need multi-step reasoning |

## Rules
- A query about buying property AND comparing locations → comparative_scorecard
- A query about buying property AND calculating loan/DSR → financial_analysis
- A query mentioning "กับ" (with) comparing two places → comparative_scorecard
- A query asking to find/search a property matching criteria → listing_search
- Financial keywords (ดอกเบี้ย, ผ่อน, กู้, วงเงิน, DSR, ROI, yield, break-even) → financial_analysis
- Legal keywords (กฎหมาย, สัญญา, มรดก, โฉนด, จดทะเบียน) → legal_guidance
- If the user asks about the quality/character/amenities of ONE area → location_analysis
- A query that combines aspects of multiple workflows (e.g. "find a condo near Ari, compare ROI, and check legal requirements") → react_agent
- An open-ended exploration query (e.g. "best area to invest in Bangkok" or "help me plan buying my first home") → react_agent
- A query that requires gathering info, then reasoning over it, then acting on conclusions → react_agent
- When unsure between a specific workflow and react_agent, prefer the specific workflow for higher confidence
- When unsure between general_guided and react_agent, prefer react_agent if the query seems to need tool usage

## Output format
Return ONLY a JSON object (no markdown fences), with these exact keys:
{
  "workflow_id": "<one of the workflow_id values above>",
  "confidence": <float 0.0-1.0>,
  "reason": "<one short sentence explaining why>",
  "extracted_entities": {
    "locations": ["<place names mentioned>"],
    "budget": "<budget if mentioned, e.g. '8M THB'>",
    "property_type": "<condo/house/townhouse/land/shophouse if mentioned>"
  }
}
"""


def _parse_llm_json(raw: str) -> dict[str, Any] | None:
    """Best-effort extraction of a JSON object from LLM text."""
    text = raw.strip()
    # Try raw parse first
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.M)
    text = re.sub(r"```\s*$", "", text, flags=re.M).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    # Find first { … last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return None


_VALID_WORKFLOW_IDS = {wf.value for wf in WorkflowId}


class RoutingEngine:
    """Route user queries to workflows using an LLM classifier."""

    def route(
        self,
        request: NormalizedAgentRequest,
        router_llm: BaseChatModel | None = None,
    ) -> WorkflowDecision:
        # ── Primary path: LLM classification ──
        if router_llm is not None:
            decision = self._route_with_llm(request, router_llm)
            if decision is not None:
                # Gate react_agent behind feature flag
                if (
                    decision.workflow_id == WorkflowId.REACT_AGENT
                    and not agent_settings.REACT_AGENT_ENABLED
                ):
                    decision = WorkflowDecision(
                        workflow_id=WorkflowId.GENERAL_GUIDED,
                        confidence=decision.confidence,
                        reason=f"{decision.reason} [react_agent disabled, falling back to general_guided]",
                    )
                return decision
            logger.warning("LLM routing failed; falling back to keyword heuristic")

        # ── Fallback: lightweight keyword heuristic ──
        return self._route_keyword_fallback(request)

    # ------------------------------------------------------------------ #
    #  LLM routing
    # ------------------------------------------------------------------ #

    def _route_with_llm(
        self,
        request: NormalizedAgentRequest,
        llm: BaseChatModel,
    ) -> WorkflowDecision | None:
        try:
            messages = [
                SystemMessage(content=_ROUTER_SYSTEM_PROMPT),
                HumanMessage(content=request.user_query),
            ]
            response = llm.invoke(messages)
            raw = response.content if hasattr(response, "content") else str(response)
            if isinstance(raw, list):
                parts = []
                for item in raw:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict):
                        t = item.get("text")
                        if isinstance(t, str):
                            parts.append(t)
                raw = "".join(parts)

            parsed = _parse_llm_json(str(raw))
            if parsed is None:
                logger.warning(
                    "Router LLM returned unparseable response: %s", raw[:200]
                )
                return None

            wf_value = str(parsed.get("workflow_id", "general_guided"))
            if wf_value not in _VALID_WORKFLOW_IDS:
                logger.warning("Router LLM returned unknown workflow_id: %s", wf_value)
                wf_value = "general_guided"

            confidence = float(parsed.get("confidence", 0.8))
            reason = str(parsed.get("reason", "LLM classification"))

            return WorkflowDecision(
                workflow_id=WorkflowId(wf_value),
                confidence=min(1.0, max(0.0, confidence)),
                reason=f"[LLM router] {reason}",
            )

        except Exception as exc:
            logger.warning("LLM routing exception: %s", exc)
            return None

    # ------------------------------------------------------------------ #
    #  Keyword fallback (emergency only — used when LLM is unavailable)
    # ------------------------------------------------------------------ #

    def _route_keyword_fallback(
        self, request: NormalizedAgentRequest
    ) -> WorkflowDecision:
        text = request.user_query.lower()

        # ── React agent — multi-domain or complex query (check FIRST) ──
        if agent_settings.REACT_AGENT_ENABLED:
            # Count how many *distinct workflow* domain signals are present.
            # NOTE: Property-type words (บ้าน, คอนโด, ที่ดิน) are NOT counted
            # because nearly every real-estate query mentions a property type;
            # they are contextual, not a separate analytical domain.
            domain_signals = 0
            if re.search(r"roi|yield|ดอกเบี้ย|ผ่อน|\bdsr\b|สินเชื่อ|วงเงินกู้", text):
                domain_signals += 1
            if re.search(r"กฎหมาย|สัญญา|มรดก|legal|\binheritance\b", text):
                domain_signals += 1
            if re.search(r"ทำเล|walkability|catchment|amenities|\blocation\b", text):
                domain_signals += 1
            if re.search(r"เปรียบเทียบ|\bcompare\b|\bversus\b|\bvs\b", text):
                domain_signals += 1

            # Multi-domain → react_agent (before single-domain checks)
            if domain_signals >= 2:
                return WorkflowDecision(
                    workflow_id=WorkflowId.REACT_AGENT,
                    confidence=0.5,
                    reason=f"[keyword fallback] multi-domain query detected ({domain_signals} domains)",
                )

            # Open-ended exploration patterns
            if re.search(
                r"\bbest\b.*\b(?:area|invest|buy)\b|วางแผน|plan.*buy|ช่วย.*(?:เลือก|แนะนำ).*(?:ซื้อ|ลงทุน)",
                text,
            ):
                return WorkflowDecision(
                    workflow_id=WorkflowId.REACT_AGENT,
                    confidence=0.4,
                    reason="[keyword fallback] open-ended exploration query detected",
                )

        # ── Single-domain checks ──

        # Legal
        if re.search(
            r"กฎหมาย|สัญญา|มรดก|ผู้จัดการมรดก|โฉนด|จดทะเบียน|\blegal\b|\binheritance\b", text
        ):
            return WorkflowDecision(
                workflow_id=WorkflowId.LEGAL_GUIDANCE,
                confidence=0.6,
                reason="[keyword fallback] legal keywords detected",
            )

        # Financial
        if re.search(
            r"\bdsr\b|วงเงินกู้|ดอกเบี้ย|ผ่อน|สินเชื่อ|\broi\b|\byield\b|\bbreak-?even\b", text
        ):
            return WorkflowDecision(
                workflow_id=WorkflowId.FINANCIAL_ANALYSIS,
                confidence=0.6,
                reason="[keyword fallback] financial keywords detected",
            )

        # Comparative
        if re.search(r"เปรียบเทียบ|\bcompare\b|\bversus\b|\bvs\b", text):
            return WorkflowDecision(
                workflow_id=WorkflowId.COMPARATIVE_SCORECARD,
                confidence=0.6,
                reason="[keyword fallback] comparison keywords detected",
            )

        # Location
        if re.search(r"\bwalkability\b|\bcatchment\b|ทำเล(?:ดี|ไหม|ที่|ของ|ใน)", text):
            return WorkflowDecision(
                workflow_id=WorkflowId.LOCATION_ANALYSIS,
                confidence=0.5,
                reason="[keyword fallback] location analysis keywords detected",
            )

        # Listing search
        if re.search(
            r"(?:หา|ค้น|แนะนำ).*(?:คอนโด|บ้าน|ทาวน์|โครงการ|ที่ดิน)|คอนโด|บ้าน(?:เดี่ยว)?|ทาวน์เฮ้าส์|\bfind\b.*\bproperty\b",
            text,
        ):
            return WorkflowDecision(
                workflow_id=WorkflowId.LISTING_SEARCH,
                confidence=0.5,
                reason="[keyword fallback] listing search keywords detected",
            )

        return WorkflowDecision(
            workflow_id=WorkflowId.GENERAL_GUIDED,
            confidence=0.3,
            reason="[keyword fallback] no strong match",
        )


routing_engine = RoutingEngine()
