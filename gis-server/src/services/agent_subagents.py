"""Lightweight router/verifier subagents for agent orchestration."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class RouteDecision:
    intent: str
    needs_strict_factual_grounding: bool
    should_decompose: bool
    response_contract: str


@dataclass
class VerificationResult:
    is_valid: bool
    missing_sections: list[str]
    needs_repair: bool


class IntentRouterSubagent:
    """LLM intent router for reliable tool planning."""

    def classify(self, text: str, classifier_llm: Any | None = None) -> RouteDecision:
        if classifier_llm is None:
            return RouteDecision(
                intent="general",
                needs_strict_factual_grounding=False,
                should_decompose=False,
                response_contract="concise",
            )

        prompt = (
            "Classify the user request into one intent for a Bangkok real-estate agent. "
            "Return JSON only with keys: intent, needs_strict_factual_grounding, should_decompose, response_contract. "
            "Allowed intents: listing_search, comparative_location, roi_investment, financial_planning, legal_process, hybrid, general. "
            "Allowed response_contract: shortlist, comparative_scorecard, financial_table, legal_checklist, concise. "
            "Rules: legal_process and financial_planning should usually set needs_strict_factual_grounding=false; "
            "comparative_location and listing_search should usually set needs_strict_factual_grounding=true. "
            "User query:\n"
            f"{text}"
        )

        try:
            response = classifier_llm.invoke(prompt)
            raw = response.content if hasattr(response, "content") else str(response)
            if isinstance(raw, list):
                parts: list[str] = []
                for item in raw:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict):
                        txt = item.get("text")
                        if isinstance(txt, str):
                            parts.append(txt)
                raw_text = "".join(parts)
            else:
                raw_text = str(raw)

            parsed = self._extract_json(raw_text)
            if not isinstance(parsed, dict):
                raise ValueError("Classifier did not return valid JSON object")

            intent = str(parsed.get("intent") or "general")
            response_contract = str(parsed.get("response_contract") or "concise")
            return RouteDecision(
                intent=intent,
                needs_strict_factual_grounding=bool(
                    parsed.get("needs_strict_factual_grounding", False)
                ),
                should_decompose=bool(parsed.get("should_decompose", False)),
                response_contract=response_contract,
            )
        except Exception:
            return RouteDecision(
                intent="general",
                needs_strict_factual_grounding=False,
                should_decompose=False,
                response_contract="concise",
            )

    def _extract_json(self, raw: str) -> dict | None:
        text = raw.strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            return None
        return None


class ResponseVerifierSubagent:
    """Checks for minimum structural quality in final responses."""

    REQUIRED_SECTIONS_BY_CONTRACT = {
        "comparative_scorecard": ["criteria", "evidence", "recommend"],
        "financial_table": ["assumption", "calculation", "summary"],
        "shortlist": ["criteria", "evidence", "recommend"],
        "legal_checklist": ["ขั้นตอน", "เงื่อนไข", "ข้อควรระวัง"],
    }

    def verify(self, response_text: str, contract: str) -> VerificationResult:
        if contract not in self.REQUIRED_SECTIONS_BY_CONTRACT:
            return VerificationResult(True, [], False)

        lowered = response_text.lower()
        missing: list[str] = []
        for keyword in self.REQUIRED_SECTIONS_BY_CONTRACT[contract]:
            if keyword not in lowered:
                missing.append(keyword)
        return VerificationResult(len(missing) == 0, missing, len(missing) > 0)

    def render_repair_instruction(self, missing: list[str]) -> str:
        missing_str = ", ".join(missing)
        return (
            "Please revise the answer with explicit sections for: "
            f"{missing_str}. Keep it evidence-backed and criterion-by-criterion."
        )


def has_explicit_compare_targets(text: str) -> bool:
    lowered = text.lower()
    if re.search(r"\bcompare\b\s+.+\s+\b(and|with|vs|versus)\b\s+.+", lowered):
        return True
    if "เปรียบเทียบ" in lowered and any(
        sep in lowered for sep in ["กับ", "และ", "หรือ", "vs"]
    ):
        return True
    return False
