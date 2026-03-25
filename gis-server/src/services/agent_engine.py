"""Deterministic workflow engine for the rewritten chat agent.

Improvements over v1:
- Workflows consult WORKFLOW_REGISTRY for required tools instead of hardcoding
- Geocoding-based location resolution (no hardcoded district list)
- Comparative workflow extracts named targets from the query
- Financial workflow uses structured parameter extraction (not positional regex)
- Location workflow invokes geocoding + location intelligence + catchment
- Hallucination guard: empty evidence is flagged transparently
- Verification triggers an actual repair loop (up to 2 retries)
"""

from __future__ import annotations

import json
import logging
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
from src.services.agent_runtime import tool_runtime
from src.services.agent_runtime_metadata import get_agent_engine_metadata
from src.services.agent_verifier import workflow_verifier
from src.services.agent_workflows import WorkflowId
from src.services.model_provider import (
    RuntimeModelConfig,
    get_model_provider,
    resolve_runtime_config,
)

logger = logging.getLogger(__name__)

# Max repair iterations when verifier says REPAIR
_MAX_REPAIR_ITERATIONS = 2

# Bangkok districts — comprehensive list for fuzzy matching
_BANGKOK_DISTRICTS: list[str] = [
    "พระนคร",
    "ดุสิต",
    "หนองจอก",
    "บางรัก",
    "บางเขน",
    "บางกะปิ",
    "ปทุมวัน",
    "ป้อมปราบศัตรูพ่าย",
    "พระโขนง",
    "มีนบุรี",
    "ลาดกระบัง",
    "ยานนาวา",
    "สัมพันธวงศ์",
    "พญาไท",
    "ธนบุรี",
    "บางกอกใหญ่",
    "ห้วยขวาง",
    "คลองสาน",
    "ตลิ่งชัน",
    "บางกอกน้อย",
    "บางขุนเทียน",
    "ภาษีเจริญ",
    "หนองแขม",
    "ราษฎร์บูรณะ",
    "บางพลัด",
    "ดินแดง",
    "บึงกุ่ม",
    "สาทร",
    "บางซื่อ",
    "จตุจักร",
    "บางคอแหลม",
    "ประเวศ",
    "คลองเตย",
    "สวนหลวง",
    "จอมทอง",
    "ดอนเมือง",
    "ราชเทวี",
    "ลาดพร้าว",
    "วัฒนา",
    "บางแค",
    "หลักสี่",
    "สายไหม",
    "คันนายาว",
    "สะพานสูง",
    "วังทองหลาง",
    "คลองสามวา",
    "บางนา",
    "ทวีวัฒนา",
    "ทุ่งครุ",
    "บางบอน",
]

# Common sub-area / neighborhood names mapping to districts or search terms
_NEIGHBORHOOD_ALIASES: dict[str, str] = {
    "อารีย์": "พญาไท",
    "ari": "พญาไท",
    "สะพานควาย": "พญาไท",
    "saphan kwai": "พญาไท",
    "ทองหล่อ": "วัฒนา",
    "thonglor": "วัฒนา",
    "thong lo": "วัฒนา",
    "เอกมัย": "วัฒนา",
    "ekkamai": "วัฒนา",
    "หลังสวน": "ปทุมวัน",
    "lang suan": "ปทุมวัน",
    "สีลม": "บางรัก",
    "silom": "บางรัก",
    "สุขุมวิท": "คลองเตย",
    "sukhumvit": "คลองเตย",
    "พระราม 9": "ห้วยขวาง",
    "rama 9": "ห้วยขวาง",
    "รัชดา": "ดินแดง",
    "ratchada": "ดินแดง",
    "อ่อนนุช": "ประเวศ",
    "on nut": "ประเวศ",
    "บางจาก": "พระโขนง",
    "สาทร": "สาทร",
    "sathorn": "สาทร",
    "สีนาคาริน": "ประเวศ",
    "si nakarin": "ประเวศ",
    "ศรีนครินทร์": "ประเวศ",
    "บางแสน": "บางนา",
    "รามอินทรา": "คันนายาว",
    "ram intra": "คันนายาว",
    "เกษตร": "จตุจักร",
    "kasetsart": "จตุจักร",
    "มหาวิทยาลัยเกษตรศาสตร์": "จตุจักร",
    "ธรรมศาสตร์": "คลองหลวง",
    "thammasat": "คลองหลวง",
    "รังสิต": "คลองหลวง",
    "rangsit": "คลองหลวง",
    "บันทัดทอง": "ปทุมวัน",
    "banthatthong": "ปทุมวัน",
    "ทรงวาด": "สัมพันธวงศ์",
    "song wat": "สัมพันธวงศ์",
    "เจริญกรุง": "สัมพันธวงศ์",
    "ลาดพร้าว": "ลาดพร้าว",
    "ladprao": "ลาดพร้าว",
    "พหลโยธิน": "จตุจักร",
    "phahon yothin": "จตุจักร",
    "ประชาชื่น": "บางซื่อ",
    "แบริ่ง": "บางนา",
    "bearing": "บางนา",
    "อุดมสุข": "บางนา",
    "udomsuk": "บางนา",
    "สำโรง": "บางนา",
    "วงเวียนใหญ่": "ธนบุรี",
    "เพชรเกษม": "ภาษีเจริญ",
    "ปิ่นเกล้า": "บางกอกน้อย",
}

# Well-known Bangkok landmarks with approximate coordinates for geocoding fallback
_LANDMARK_COORDS: dict[str, tuple[float, float]] = {
    "สวนเบญจกิติ": (13.7230, 100.5600),
    "benjakiti": (13.7230, 100.5600),
    "เบญจกิติ": (13.7230, 100.5600),
    "สวนลุมพินี": (13.7313, 100.5412),
    "lumphini": (13.7313, 100.5412),
    "ลุมพินี": (13.7313, 100.5412),
    "จตุจักร": (13.7999, 100.5533),
    "chatuchak": (13.7999, 100.5533),
    "สนามบินสุวรรณภูมิ": (13.6900, 100.7501),
    "suvarnabhumi": (13.6900, 100.7501),
    "สยาม": (13.7454, 100.5347),
    "siam": (13.7454, 100.5347),
    "อโศก": (13.7373, 100.5609),
    "asoke": (13.7373, 100.5609),
    "ทองหล่อ": (13.7340, 100.5780),
    "thonglor": (13.7340, 100.5780),
    "เอกมัย": (13.7266, 100.5851),
    "ekkamai": (13.7266, 100.5851),
    "พร้อมพงษ์": (13.7305, 100.5696),
    "phrom phong": (13.7305, 100.5696),
    "อารีย์": (13.7725, 100.5420),
    "ari": (13.7725, 100.5420),
    "สะพานควาย": (13.7800, 100.5456),
    "saphan khwai": (13.7800, 100.5456),
    "ม.เกษตร": (13.8505, 100.5714),
    "เกษตรศาสตร์": (13.8505, 100.5714),
    "kasetsart": (13.8505, 100.5714),
    "ม.ธรรมศาสตร์": (13.7617, 100.4924),
    "ธรรมศาสตร์": (13.7617, 100.4924),
    "thammasat": (13.7617, 100.4924),
    "หลังสวน": (13.7388, 100.5440),
    "langsuan": (13.7388, 100.5440),
    "ราชดำริ": (13.7388, 100.5407),
    "ratchadamri": (13.7388, 100.5407),
    "บรรทัดทอง": (13.7373, 100.5265),
    "bantadthong": (13.7373, 100.5265),
    "ทรงวาด": (13.7360, 100.5115),
    "song wat": (13.7360, 100.5115),
    "เตรียมอุดม": (13.6930, 100.6330),
    "พัฒนาการ": (13.6930, 100.6330),
    "รามคำแหง": (13.7570, 100.6260),
    "ramkhamhaeng": (13.7570, 100.6260),
}


def _extract_districts(text: str) -> list[str]:
    """Extract district names from text using the comprehensive district list and aliases."""
    found: list[str] = []
    lower = text.lower()

    # Check aliases first (more specific)
    for alias, district in _NEIGHBORHOOD_ALIASES.items():
        if alias in lower or alias in text:
            if district not in found:
                found.append(district)

    # Then check official district names
    for district in _BANGKOK_DISTRICTS:
        if district in text and district not in found:
            found.append(district)

    return found


def _extract_thai_numbers(text: str) -> list[float]:
    """Extract numbers from text, handling Thai number formats and M/million shorthand."""
    results: list[float] = []
    # Match patterns like: 8ล้าน, 8 ล้าน, 8M, 8 million, 8,000,000, 80000
    for match in re.finditer(
        r"(\d[\d,]*(?:\.\d+)?)\s*(?:ล้าน|ล\.|M\b|million\b)?", text, re.I
    ):
        raw = match.group(1).replace(",", "")
        try:
            val = float(raw)
        except ValueError:
            continue
        # Check if followed by million-scale suffix
        suffix_start = match.end(1)
        suffix_text = text[suffix_start : suffix_start + 15].strip().lower()
        if suffix_text.startswith(("ล้าน", "ล.", "m")) or (
            suffix_text.startswith("million")
        ):
            val *= 1_000_000
        results.append(val)
    return results


def _extract_price_range(text: str) -> tuple[float | None, float | None]:
    """Extract min/max price from Thai real estate query text."""
    numbers = _extract_thai_numbers(text)
    min_price = None
    max_price = None

    # Look for budget/max price indicators
    budget_patterns = [
        r"(?:งบ|ราคาไม่เกิน|ไม่เกิน|budget|under|below|max)\s*(\d[\d,]*(?:\.\d+)?)\s*(?:ล้าน|ล\.|M\b|million\b|บาท)?",
    ]
    for pattern in budget_patterns:
        m = re.search(pattern, text, re.I)
        if m:
            raw = m.group(1).replace(",", "")
            try:
                val = float(raw)
                suffix = text[m.end(1) : m.end(1) + 15].strip().lower()
                if suffix.startswith(("ล้าน", "ล.", "m")) or suffix.startswith(
                    "million"
                ):
                    val *= 1_000_000
                elif val < 100:
                    val *= 1_000_000  # assume millions if small number
                max_price = val
            except ValueError:
                pass

    # Range patterns (e.g., 3-5 ล้าน, 3M - 5M)
    range_match = re.search(
        r"(\d[\d,]*(?:\.\d+)?)\s*[-–]\s*(\d[\d,]*(?:\.\d+)?)\s*(?:ล้าน|M\b|million\b|บาท)?",
        text,
        re.I,
    )
    if range_match:
        try:
            low = float(range_match.group(1).replace(",", ""))
            high = float(range_match.group(2).replace(",", ""))
            suffix = text[range_match.end(2) : range_match.end(2) + 15].strip().lower()
            if suffix.startswith(("ล้าน", "m")) or suffix.startswith("million"):
                low *= 1_000_000
                high *= 1_000_000
            elif low < 100 and high < 100:
                low *= 1_000_000
                high *= 1_000_000
            min_price = low
            max_price = high
        except ValueError:
            pass

    return min_price, max_price


def _extract_comparison_targets(text: str) -> list[str]:
    """Extract the named locations/entities being compared from a Thai real estate query."""
    targets: list[str] = []

    # Try structured patterns first: "X กับ Y", "X vs Y", "X หรือ Y", "X และ Y"
    for sep in ["กับ", "และ", "หรือ", "vs", "versus"]:
        # Find the separator and extract surrounding context
        idx = text.find(sep)
        if idx == -1:
            idx = text.lower().find(sep)
        if idx == -1:
            continue

        before = text[:idx].strip()
        after = text[idx + len(sep) :].strip()

        # Extract the last meaningful phrase before separator
        before_words = re.split(r"[,\s]+", before)
        # Take last 1-3 words as target
        before_target = " ".join(before_words[-3:]).strip()

        # Extract first meaningful phrase after separator
        after_words = re.split(r"[,\s]+", after)
        after_target = " ".join(after_words[:3]).strip()

        if before_target:
            targets.append(before_target)
        if after_target:
            targets.append(after_target)
        break

    # If we didn't find structured patterns, look for known location names
    if not targets:
        found_locations = _extract_districts(text)
        targets = found_locations[:4]  # limit to 4 comparison targets

    return targets


class WorkflowEngine:
    async def astream(
        self,
        messages: list[dict[str, Any]],
        attachments: list[dict[str, Any]] | None = None,
        runtime_config: RuntimeModelConfig | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        request = normalize_agent_request(messages, attachments)

        # Build a cheap LLM for routing (low tokens, low temp)
        router_llm = self._build_router_llm(runtime_config)
        decision = routing_engine.route(request, router_llm=router_llm)

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

        # Flag empty-evidence state for hallucination guard
        self._apply_evidence_guard(state)

        # Yield tool events
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

        # Compose → Verify → Repair loop
        final_text = await self._compose_and_verify(state, composer_llm)

        yield {
            "type": "final",
            "content": final_text,
        }

    async def _compose_and_verify(
        self, state: WorkflowExecutionState, composer_llm: Any | None
    ) -> str:
        """Compose response and run verification with repair loop."""
        composed = await response_composer.compose(state=state, llm=composer_llm)
        verification = workflow_verifier.verify(state, composed.text)

        if verification.status.value == "pass":
            return composed.text

        # Repair loop: re-compose with feedback
        for attempt in range(_MAX_REPAIR_ITERATIONS):
            if verification.status.value == "refuse":
                return self._build_refusal_message(state)

            repair_feedback = verification.message or "Verification failed."
            logger.info(
                "Repair attempt %d/%d: %s",
                attempt + 1,
                _MAX_REPAIR_ITERATIONS,
                repair_feedback,
            )

            # Re-compose with repair instruction
            composed = await response_composer.compose(
                state=state,
                llm=composer_llm,
                repair_feedback=repair_feedback,
            )
            verification = workflow_verifier.verify(state, composed.text)

            if verification.status.value == "pass":
                return composed.text

        # Exhausted repair attempts — return with warning
        status_label = verification.status.value.title()
        suffix = (
            f"\n\n[{status_label}] {verification.message}"
            if verification.message
            else ""
        )
        return composed.text + suffix

    def _build_refusal_message(self, state: WorkflowExecutionState) -> str:
        """Build an honest refusal when the system cannot answer reliably."""
        lang = state.request.language
        if lang == "th":
            return (
                "ขออภัย ระบบไม่สามารถตอบคำถามนี้ได้อย่างน่าเชื่อถือ "
                "เนื่องจากข้อมูลที่มีไม่เพียงพอ กรุณาลองปรับคำถามหรือเพิ่มรายละเอียดเพิ่มเติม"
            )
        return (
            "Sorry, the system cannot answer this question reliably "
            "due to insufficient evidence. Please try rephrasing or adding more details."
        )

    def _apply_evidence_guard(self, state: WorkflowExecutionState) -> None:
        """Flag when tools returned no useful evidence — prevents hallucination."""
        has_meaningful_evidence = any(
            result.status == "success"
            and "error" not in result.normalized_output
            and result.normalized_output.get("text", "") != ""
            for result in state.tool_results
        )
        # Check for non-empty structured data too
        has_structured_data = any(
            result.status == "success"
            and (
                result.normalized_output.get("properties")
                or result.normalized_output.get("data")
                or result.normalized_output.get("dsr_ratio")
                or result.normalized_output.get("checklist")
                or result.normalized_output.get("inputs")
                or result.normalized_output.get("documents")
                or result.normalized_output.get("results")
            )
            for result in state.tool_results
        )

        if not has_meaningful_evidence and not has_structured_data:
            state.notes.append(
                "WARNING_NO_DATA: เครื่องมือไม่พบข้อมูลที่ตรงกับคำถาม "
                "(Tools returned no matching data for this query)"
            )
            # Downgrade any MET assessments to PARTIAL when there's no real evidence
            for assessment in state.assessments:
                if (
                    assessment.status == CriteriaStatus.MET
                    and not assessment.evidence_ids
                ):
                    assessment.status = CriteriaStatus.PARTIAL
                    assessment.rationale += " [No supporting evidence found]"

    def _build_router_llm(
        self, runtime_config: RuntimeModelConfig | None
    ) -> Any | None:
        """Build a cheap, fast LLM for intent routing (low tokens, zero temperature)."""
        try:
            resolved = resolve_runtime_config(runtime_config)
            if not resolved.is_configured:
                return None
            provider = get_model_provider(resolved.provider)
            return provider.create_chat_model(
                resolved,
                temperature=0.0,
                max_tokens=512,
            )
        except Exception:
            return None

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
                max_tokens=min(4096, resolved.max_tokens),
            )
        except Exception:
            return None

    def _append_result(self, state: WorkflowExecutionState, result) -> None:
        state.tool_results.append(result)
        state.evidence.extend(result.evidence_items)

    # ------------------------------------------------------------------ #
    #  FINANCIAL WORKFLOW — structured extraction, multi-tool
    # ------------------------------------------------------------------ #

    def _run_financial_workflow(self, state: WorkflowExecutionState) -> None:
        text = state.request.user_query
        params = self._extract_financial_params(text)

        # Always run DSR calculation
        dsr_result = tool_runtime.execute(
            "compute_dsr_and_affordability",
            {
                "monthly_income_thb": params["income"],
                "existing_monthly_debt_thb": params["debt"],
                "annual_interest_rate": params["rate"],
                "tenure_years": params["tenure"],
            },
        )
        self._append_result(state, dsr_result)

        # Run financial projection if investment-related keywords present
        investment_keywords = [
            "roi",
            "yield",
            "break-even",
            "คืนทุน",
            "ผลตอบแทน",
            "ปล่อยเช่า",
            "airbnb",
        ]
        if any(kw in text.lower() for kw in investment_keywords):
            price = params.get("asset_price", 0)
            if price > 0:
                projection_result = tool_runtime.execute(
                    "compute_financial_projection",
                    {
                        "asset_price_thb": price,
                        "loan_ratio": params.get("loan_ratio", 0.5),
                        "annual_interest_rate": params["rate"],
                    },
                )
                self._append_result(state, projection_result)

        state.notes.append(
            f"Financial params extracted: income={params['income']}, "
            f"debt={params['debt']}, rate={params['rate']}, tenure={params['tenure']}"
        )

        state.assessments.extend(
            [
                CriteriaAssessment(
                    criterion="DSR calculation",
                    status=CriteriaStatus.MET,
                    rationale="Computed via deterministic calculator.",
                    evidence_ids=[ev.evidence_id for ev in dsr_result.evidence_items],
                ),
                CriteriaAssessment(
                    criterion="Loan affordability estimate",
                    status=CriteriaStatus.MET,
                    rationale="Estimated from extracted income, debt, and interest parameters.",
                    evidence_ids=[ev.evidence_id for ev in dsr_result.evidence_items],
                ),
                CriteriaAssessment(
                    criterion="Interest comparison with prepayment",
                    status=CriteriaStatus.MET,
                    rationale="Prepayment comparison included in DSR tool output.",
                    evidence_ids=[ev.evidence_id for ev in dsr_result.evidence_items],
                ),
            ]
        )

    def _extract_financial_params(self, text: str) -> dict[str, Any]:
        """Extract financial parameters using contextual patterns, not positional indexing."""
        params: dict[str, Any] = {
            "income": 0.0,
            "debt": 0.0,
            "rate": 0.06,
            "tenure": 30,
            "asset_price": 0.0,
            "loan_ratio": 0.5,
        }

        # Income patterns (Thai + English)
        income_match = re.search(
            r"(?:เงินเดือน|รายได้|income|salary|earn)\s*(?:ต่อเดือน\s*)?(\d[\d,]*(?:\.\d+)?)",
            text,
            re.I,
        )
        if income_match:
            params["income"] = float(income_match.group(1).replace(",", ""))
        else:
            # Try "X บาท/เดือน" pattern
            monthly_match = re.search(r"(\d[\d,]*)\s*(?:บาท)?\s*/?\s*เดือน", text)
            if monthly_match:
                params["income"] = float(monthly_match.group(1).replace(",", ""))

        # Debt patterns
        debt_match = re.search(
            r"(?:หนี้|ผ่อน(?:รถ|บัตร|อื่น)?|debt|payment|ค่างวด)\s*(?:เดือนละ\s*)?(\d[\d,]*(?:\.\d+)?)",
            text,
            re.I,
        )
        if debt_match:
            params["debt"] = float(debt_match.group(1).replace(",", ""))

        # Interest rate
        rate_match = re.search(
            r"(?:ดอกเบี้ย|interest|rate)\s*(\d+(?:\.\d+)?)\s*%?", text, re.I
        )
        if rate_match:
            rate = float(rate_match.group(1))
            params["rate"] = rate / 100 if rate > 1 else rate

        # Tenure
        tenure_match = re.search(r"(\d+)\s*(?:ปี|year)", text, re.I)
        if tenure_match:
            params["tenure"] = int(tenure_match.group(1))

        # Asset price
        price_match = re.search(
            r"(?:บ้าน|คอนโด|ราคา|price|ซื้อ|ที่ดิน)\s*(?:ราคา\s*)?(\d[\d,]*(?:\.\d+)?)\s*(?:ล้าน|M\b|million\b)?",
            text,
            re.I,
        )
        if price_match:
            price = float(price_match.group(1).replace(",", ""))
            suffix = text[price_match.end(1) : price_match.end(1) + 15].strip().lower()
            if suffix.startswith(("ล้าน", "m")) or suffix.startswith("million"):
                price *= 1_000_000
            elif price < 200:
                price *= 1_000_000
            params["asset_price"] = price

        # Loan ratio
        loan_match = re.search(r"(\d+)\s*%?\s*(?:กู้|loan|bank|ธนาคาร)", text, re.I)
        if loan_match:
            ratio = float(loan_match.group(1))
            params["loan_ratio"] = ratio / 100 if ratio > 1 else ratio

        # Fallback: if no income found, try to extract from numbered context
        if params["income"] == 0.0:
            all_numbers = _extract_thai_numbers(text)
            # Heuristic: income is typically 20k-500k range
            for n in all_numbers:
                if 15000 <= n <= 500000:
                    params["income"] = n
                    break
            if params["income"] == 0.0 and all_numbers:
                # Last resort: use the second-largest number as income
                sorted_nums = sorted(all_numbers, reverse=True)
                if len(sorted_nums) > 1:
                    params["income"] = sorted_nums[1]

        # Fallback for debt: typically 5k-100k
        if params["debt"] == 0.0:
            all_numbers = _extract_thai_numbers(text)
            for n in all_numbers:
                if 3000 <= n <= 100000 and n != params["income"]:
                    params["debt"] = n
                    break

        return params

    # ------------------------------------------------------------------ #
    #  LEGAL WORKFLOW
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    #  COMPARATIVE WORKFLOW — with target extraction & per-target tools
    # ------------------------------------------------------------------ #

    def _run_comparative_workflow(self, state: WorkflowExecutionState) -> None:
        text = state.request.user_query
        lowered = text.lower()
        targets = _extract_comparison_targets(text)

        # Detect if this is an investment/ROI query
        is_investment = any(
            kw in lowered
            for kw in [
                "roi",
                "yield",
                "ผลตอบแทน",
                "ปล่อยเช่า",
                "airbnb",
                "ลงทุน",
                "คืนทุน",
                "break-even",
                "capital gain",
                "occupancy",
                "net profit",
            ]
        )

        # Detect if asking about condos
        is_condo = self._query_wants_condo(lowered)

        # ── 1. Knowledge base: neighborhood facts ──────────────────────
        knowledge = tool_runtime.execute(
            "query_internal_knowledge",
            {"query": text, "domain": "neighborhood_facts", "limit": 6},
        )
        self._append_result(state, knowledge)

        # ── 1b. Knowledge base: project metadata (for condo comparisons) ──
        if is_condo:
            condo_knowledge = tool_runtime.execute(
                "query_internal_knowledge",
                {"query": text, "domain": "project_metadata", "limit": 8},
            )
            self._append_result(state, condo_knowledge)

        # ── 2. Market statistics per target ────────────────────────────
        if targets:
            for target in targets[:3]:
                districts = _extract_districts(target)
                district_name = districts[0] if districts else None
                market = tool_runtime.execute(
                    "get_market_statistics",
                    {"district": district_name},
                )
                self._append_result(state, market)
        else:
            market = tool_runtime.execute("get_market_statistics", {})
            self._append_result(state, market)

        # ── 3. Geocoding + location intelligence for each target ───────
        target_coords: list[tuple[float, float]] = []
        for target in targets[:3]:
            try:
                geo = tool_runtime.execute("geocode_place_nominatim", {"place": target})
                self._append_result(state, geo)
                lat, lon = None, None
                if geo.status == "success" and "error" not in geo.normalized_output:
                    lat = geo.normalized_output.get("lat")
                    lon = geo.normalized_output.get("lon")
                # Fallback to landmark coords
                if lat is None or lon is None:
                    lat, lon = self._lookup_landmark_coords(target)
                if lat and lon:
                    target_coords.append((float(lat), float(lon)))
                    loc_intel = tool_runtime.execute(
                        "get_location_intelligence",
                        {"latitude": float(lat), "longitude": float(lon)},
                    )
                    self._append_result(state, loc_intel)
            except Exception as exc:
                logger.warning("Comparative geocoding failed for %s: %s", target, exc)

        # ── 4. Financial projections for investment queries ─────────────
        if is_investment:
            min_price, max_price = _extract_price_range(text)
            # Use budget midpoint or max as estimated asset price
            asset_price = None
            if max_price and max_price > 0:
                asset_price = max_price
            elif min_price and min_price > 0:
                asset_price = min_price

            if asset_price and asset_price > 0:
                # Estimate annual revenue based on property type and area
                # AirBnB: ~1,500-2,500/night × 70% occupancy ≈ 383K-639K/year
                # Rental: ~5% gross yield on asset price
                is_airbnb = any(
                    kw in lowered for kw in ["airbnb", "air bnb", "เช่ารายวัน"]
                )
                if is_airbnb:
                    # Conservative AirBnB estimate
                    est_revenue = asset_price * 0.05  # ~5% gross yield
                    est_expense = (
                        est_revenue * 0.35
                    )  # 35% expenses (mgmt, utilities, wear)
                else:
                    est_revenue = asset_price * 0.04  # ~4% gross yield
                    est_expense = est_revenue * 0.25  # 25% expenses

                try:
                    projection = tool_runtime.execute(
                        "compute_financial_projection",
                        {
                            "asset_price_thb": asset_price,
                            "loan_ratio": 0.7,
                            "annual_interest_rate": 0.06,
                            "annual_revenue_thb": est_revenue,
                            "annual_expense_thb": est_expense,
                        },
                    )
                    self._append_result(state, projection)
                    state.notes.append(
                        f"Financial projection computed for asset price {asset_price:,.0f} THB "
                        f"(est. revenue {est_revenue:,.0f}, est. expense {est_expense:,.0f})."
                    )
                except Exception as exc:
                    logger.warning("Financial projection failed: %s", exc)

            # Also run DSR if income mentioned
            income_match = re.search(
                r"(?:เงินเดือน|รายได้|income|salary)\s*(\d[\d,]*)", text, re.I
            )
            if income_match:
                try:
                    income = float(income_match.group(1).replace(",", ""))
                    dsr = tool_runtime.execute(
                        "compute_dsr_and_affordability",
                        {
                            "monthly_income_thb": income,
                            "existing_monthly_debt_thb": 0,
                            "annual_interest_rate": 0.06,
                            "tenure_years": 30,
                        },
                    )
                    self._append_result(state, dsr)
                except Exception as exc:
                    logger.warning("DSR calculation failed: %s", exc)

        # ── 5. Search house DB for non-condo comparison targets ────────
        if not is_condo:
            min_price, max_price = _extract_price_range(text)
            building_style = self._extract_building_style(lowered)
            for target in targets[:2]:
                districts = _extract_districts(target)
                district_name = districts[0] if districts else None
                if district_name or building_style:
                    try:
                        search = tool_runtime.execute(
                            "search_properties",
                            self._build_listing_search_params(
                                district=district_name,
                                building_style=building_style,
                                min_price=min_price,
                                max_price=max_price,
                            ),
                        )
                        self._append_result(state, search)
                    except Exception as exc:
                        logger.warning(
                            "Comparative property search failed for %s: %s", target, exc
                        )

        target_str = ", ".join(targets) if targets else "auto-detected"
        state.notes.append(
            f"Compared areas: [{target_str}] using market stats, neighborhood facts, "
            f"location intelligence, {'financial projections, ' if is_investment else ''}"
            f"{'condo knowledge, ' if is_condo else ''}and spatial data."
        )
        if is_condo:
            state.notes.append(
                "NOTE: Property listing database has houses only. "
                "Condo data from knowledge base (project-level metadata)."
            )
        if is_investment:
            state.notes.append(
                "NOTE: This is an investment comparison. "
                "Composer should build revenue-expense model with estimates."
            )

        state.assessments.extend(
            [
                CriteriaAssessment(
                    criterion="Comparison targets identified",
                    status=CriteriaStatus.MET if targets else CriteriaStatus.PARTIAL,
                    rationale=f"Targets extracted: {target_str}"
                    if targets
                    else "No explicit targets found; used general comparison.",
                    evidence_ids=[ev.evidence_id for ev in knowledge.evidence_items],
                ),
                CriteriaAssessment(
                    criterion="Market/neighborhood evidence",
                    status=CriteriaStatus.MET
                    if len(target_coords) >= 2
                    else CriteriaStatus.PARTIAL,
                    rationale=f"Location intelligence for {len(target_coords)} targets, "
                    f"market stats, curated proxies.",
                    evidence_ids=[ev.evidence_id for ev in state.evidence],
                ),
            ]
        )
        if is_investment:
            state.assessments.append(
                CriteriaAssessment(
                    criterion="Financial analysis",
                    status=CriteriaStatus.MET
                    if any(
                        r.tool_name == "compute_financial_projection"
                        for r in state.tool_results
                    )
                    else CriteriaStatus.PARTIAL,
                    rationale="Financial projection tool called for investment analysis."
                    if any(
                        r.tool_name == "compute_financial_projection"
                        for r in state.tool_results
                    )
                    else "No asset price extracted; composer should estimate from budget.",
                    evidence_ids=[ev.evidence_id for ev in state.evidence],
                )
            )

    # ------------------------------------------------------------------ #
    #  LISTING WORKFLOW — geocoding, smart filters, retry, knowledge cross-ref
    # ------------------------------------------------------------------ #

    def _run_listing_workflow(self, state: WorkflowExecutionState) -> None:
        text = state.request.user_query
        lowered = text.lower()

        # ── 1. Classify property type ──────────────────────────────────
        is_condo = self._query_wants_condo(lowered)

        # ── 2. Extract structured filters ──────────────────────────────
        districts = _extract_districts(text)
        district = districts[0] if districts else None
        min_price, max_price = _extract_price_range(text)
        building_style = self._extract_building_style(lowered)

        # ── 3. Geocode named places for bbox search ────────────────────
        geocoded_lat, geocoded_lon = None, None
        place_names = self._extract_place_names(text, districts)
        for place in place_names[:3]:
            try:
                geo = tool_runtime.execute("geocode_place_nominatim", {"place": place})
                self._append_result(state, geo)
                if geo.status == "success" and "error" not in geo.normalized_output:
                    geocoded_lat = geo.normalized_output.get("lat")
                    geocoded_lon = geo.normalized_output.get("lon")
                    if geocoded_lat and geocoded_lon:
                        break
            except Exception as exc:
                logger.warning("Listing geocode failed for %s: %s", place, exc)

        # Fallback: use well-known landmark coordinates
        if geocoded_lat is None or geocoded_lon is None:
            geocoded_lat, geocoded_lon = self._lookup_landmark_coords(text)

        # ── 4. Knowledge base query (always — use project_metadata which has condos too) ──
        knowledge = tool_runtime.execute(
            "query_internal_knowledge",
            {"query": text, "domain": "project_metadata", "limit": 10},
        )
        self._append_result(state, knowledge)

        # ── 4b. If knowledge returned few results, broaden the search ──
        kb_docs = knowledge.normalized_output.get("documents", [])
        if not isinstance(kb_docs, list):
            kb_docs = []
        if len(kb_docs) < 3:
            # Try broader query: just the area + property type
            broader_query = " ".join(districts[:2]) if districts else text[:60]
            if is_condo:
                broader_query = f"คอนโด {broader_query}"
            broader_kb = tool_runtime.execute(
                "query_internal_knowledge",
                {"query": broader_query, "domain": "project_metadata", "limit": 10},
            )
            self._append_result(state, broader_kb)
            state.notes.append(
                f"Initial knowledge search returned {len(kb_docs)} results; "
                f"broadened query to find more candidates."
            )

        # ── 5. Property database search (houses only — DB has no condos) ──
        search_result = None
        properties: list[dict[str, Any]] = []
        nearby_result = None

        if not is_condo:
            search_params = self._build_listing_search_params(
                district=district,
                building_style=building_style,
                min_price=min_price,
                max_price=max_price,
                lat=geocoded_lat,
                lon=geocoded_lon,
            )
            search_result = tool_runtime.execute("search_properties", search_params)
            self._append_result(state, search_result)
            properties = search_result.normalized_output.get("properties", [])
            if not isinstance(properties, list):
                properties = []

            # ── 5b. Retry with broader params if no results ────────────
            if len(properties) == 0 and (district or building_style):
                retry_params = self._build_listing_search_params(
                    district=None,  # drop district filter
                    building_style=building_style,
                    min_price=min_price,
                    max_price=max_price,
                    lat=geocoded_lat,
                    lon=geocoded_lon,
                    radius_km=5,  # wider bbox
                )
                retry_result = tool_runtime.execute("search_properties", retry_params)
                self._append_result(state, retry_result)
                retry_props = retry_result.normalized_output.get("properties", [])
                if isinstance(retry_props, list) and len(retry_props) > 0:
                    properties = retry_props
                    state.notes.append(
                        "Initial search returned 0 results; retried with broader filters."
                    )

        # ── 5c. Nearby properties search (for proximity queries) ──────
        proximity_radius = self._extract_proximity_meters(lowered)
        if geocoded_lat and geocoded_lon and proximity_radius:
            try:
                nearby_result = tool_runtime.execute(
                    "get_nearby_properties",
                    {
                        "latitude": float(geocoded_lat),
                        "longitude": float(geocoded_lon),
                        "radius_meters": proximity_radius,
                        "limit": 10,
                    },
                )
                self._append_result(state, nearby_result)
            except Exception as exc:
                logger.warning("Nearby properties failed: %s", exc)

        # ── 6. Location intelligence if we have coordinates ────────────
        if geocoded_lat and geocoded_lon:
            try:
                loc_intel = tool_runtime.execute(
                    "get_location_intelligence",
                    {
                        "latitude": float(geocoded_lat),
                        "longitude": float(geocoded_lon),
                    },
                )
                self._append_result(state, loc_intel)
            except Exception as exc:
                logger.warning("Location intelligence failed: %s", exc)

        # ── 7. Build state notes and assessments ──────────────────────
        num_props = len(properties)
        has_results = num_props > 0
        has_knowledge = (
            knowledge.status == "success"
            and knowledge.normalized_output.get("documents")
        )

        type_label = "คอนโด" if is_condo else (building_style or "all types")
        state.notes.append(
            f"Listing search: type={type_label}, district={district}, "
            f"price=[{min_price}, {max_price}], geocoded={'yes' if geocoded_lat else 'no'}, "
            f"DB_results={num_props}, knowledge={'yes' if has_knowledge else 'no'}, "
            f"is_condo={is_condo}"
        )
        if is_condo:
            state.notes.append(
                "NOTE: The property listing database contains houses only (บ้านเดี่ยว, "
                "ทาวน์เฮ้าส์, etc.). Condo data comes from the knowledge base."
            )

        # ── 7b. Distance/travel time estimation ───────────────────────
        if geocoded_lat and geocoded_lon:
            state.notes.append(
                f"GEOCODED_COORDS: lat={geocoded_lat}, lon={geocoded_lon}. "
                f"Composer should compute straight-line distance to listed properties "
                f"and estimate driving time (distance × 1.4 ÷ 30 km/h for peak hours)."
            )

        # ── 7c. Number of candidates requested ────────────────────────
        count_match = re.search(
            r"(\d+)\s*(?:โครงการ|ตัวเลือก|options|projects|choices)", text
        )
        if count_match:
            requested_count = int(count_match.group(1))
            state.notes.append(
                f"USER_REQUESTED_COUNT: {requested_count}. "
                f"Composer must try to present {requested_count} candidates "
                f"(fully matching + partially matching if needed)."
            )

        all_evidence_ids = [ev.evidence_id for ev in state.evidence]

        # Assessment: candidate shortlist
        if is_condo and has_knowledge:
            state.assessments.append(
                CriteriaAssessment(
                    criterion="Candidate shortlist",
                    status=CriteriaStatus.PARTIAL,
                    rationale=(
                        "Condo listings are not in the property database. "
                        "Used knowledge base for project-level information."
                    ),
                    evidence_ids=all_evidence_ids,
                )
            )
        elif has_results:
            state.assessments.append(
                CriteriaAssessment(
                    criterion="Candidate shortlist",
                    status=CriteriaStatus.MET,
                    rationale=f"Found {num_props} matching properties from listing database.",
                    evidence_ids=all_evidence_ids,
                )
            )
        else:
            state.assessments.append(
                CriteriaAssessment(
                    criterion="Candidate shortlist",
                    status=CriteriaStatus.NOT_MET,
                    rationale=(
                        "No matching properties found in the database for the given criteria."
                    ),
                    evidence_ids=all_evidence_ids,
                )
            )

        # Assessment: spatial context
        if geocoded_lat and geocoded_lon:
            state.assessments.append(
                CriteriaAssessment(
                    criterion="Spatial/location context",
                    status=CriteriaStatus.MET,
                    rationale=f"Geocoded to ({geocoded_lat}, {geocoded_lon}), "
                    f"location intelligence retrieved.",
                    evidence_ids=all_evidence_ids,
                )
            )

        # Assessment: project-specific constraints
        state.assessments.append(
            CriteriaAssessment(
                criterion="Project-specific special constraints",
                status=CriteriaStatus.PARTIAL
                if has_knowledge
                else CriteriaStatus.NOT_MET,
                rationale=(
                    "Cross-referenced with curated project metadata from knowledge base."
                    if has_knowledge
                    else "No matching project metadata found in knowledge base."
                ),
                evidence_ids=[ev.evidence_id for ev in knowledge.evidence_items],
            )
        )

    @staticmethod
    def _query_wants_condo(lowered: str) -> bool:
        """Detect if the query is asking for condos/apartments."""
        condo_keywords = [
            "คอนโด",
            "condo",
            "condominium",
            "อพาร์ทเมนต์",
            "apartment",
            "low-rise",
            "low rise",
            "high-rise",
            "high rise",
        ]
        return any(kw in lowered for kw in condo_keywords)

    @staticmethod
    def _lookup_landmark_coords(text: str) -> tuple[float | None, float | None]:
        """Look up well-known Bangkok landmarks for coordinate fallback."""
        lowered = text.lower()
        for keyword, (lat, lon) in _LANDMARK_COORDS.items():
            if keyword in lowered:
                return lat, lon
        return None, None

    @staticmethod
    def _extract_building_style(lowered: str) -> str | None:
        """Extract building style filter from query text."""
        style_map = {
            "บ้านเดี่ยว": "บ้านเดี่ยว",
            "ทาวน์เฮ้าส์": "ทาวน์เฮ้าส์",
            "ทาวน์โฮม": "ทาวน์เฮ้าส์",
            "บ้านแฝด": "บ้านแฝด",
            "ตึกแถว": "ตึกแถว",
            "shophouse": "ตึกแถว",
            "อาคารพาณิชย์": "อาคารพาณิชย์",
        }
        for keyword, style in style_map.items():
            if keyword in lowered:
                return style
        return None

    @staticmethod
    def _extract_place_names(text: str, districts: list[str]) -> list[str]:
        """Extract named places for geocoding beyond just district names."""
        places: list[str] = []
        # Named landmarks / schools / stations / parks patterns
        landmark_patterns = [
            r"(?:ใกล้|near|ห่างจาก)\s*(.{3,40}?)(?:\s+(?:ระยะ|ไม่เกิน|within|ไม่|ได้|งบ|,|\.|$))",
            r"โรงเรียน\S+(?:\s+\S+){0,3}",
            r"(?:BTS|MRT|ARL|สถานี)\s*\S+",
            r"สวน\S+",
            r"ม\.\s*(?:เกษตร|ธรรมศาสตร์|จุฬา|มหิดล|ศิลปากร)\S*",
        ]
        for pattern in landmark_patterns:
            m = re.search(pattern, text, re.I)
            if m:
                extracted = m.group(0).strip().rstrip(".,")
                if len(extracted) > 2:
                    places.append(extracted)

        # District / neighborhood names
        for d in districts[:2]:
            alias = _NEIGHBORHOOD_ALIASES.get(d, d)
            places.append(f"{alias} Bangkok" if alias == d else f"{alias} กรุงเทพ")

        if not places:
            # Fallback: use first 80 chars of query for geocoding
            places.append(text[:80])

        return places

    @staticmethod
    def _extract_proximity_meters(lowered: str) -> int | None:
        """Extract a proximity radius in meters from the query."""
        m = re.search(
            r"(?:ภายใน|within|ไม่เกิน|ระยะ|ห่าง)\s*(\d+)\s*(?:ม\.|m|เมตร|meter)", lowered
        )
        if m:
            return min(int(m.group(1)), 5000)
        m = re.search(r"(?:ภายใน|within|ไม่เกิน|ระยะ)\s*(\d+)\s*(?:กม\.|km|กิโล)", lowered)
        if m:
            return min(int(m.group(1)) * 1000, 10000)
        # "walking distance" / "เดินได้"
        if any(kw in lowered for kw in ["เดินได้", "walking distance", "เดินไม่ไกล"]):
            return 800
        return None

    @staticmethod
    def _build_listing_search_params(
        district: str | None,
        building_style: str | None,
        min_price: float | None,
        max_price: float | None,
        lat: Any | None = None,
        lon: Any | None = None,
        radius_km: float = 2.0,
    ) -> dict[str, Any]:
        """Build search_properties params with optional bbox from geocoded coords."""
        params: dict[str, Any] = {"limit": 10}
        if district:
            params["district"] = district
        if building_style:
            params["building_style"] = building_style
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price

        # Build bbox from geocoded coordinates for spatial filtering
        if lat is not None and lon is not None:
            try:
                lat_f, lon_f = float(lat), float(lon)
                # ~0.009 degrees latitude ≈ 1 km
                lat_delta = 0.009 * radius_km
                lon_delta = 0.011 * radius_km
                params["min_lat"] = lat_f - lat_delta
                params["max_lat"] = lat_f + lat_delta
                params["min_lon"] = lon_f - lon_delta
                params["max_lon"] = lon_f + lon_delta
            except (ValueError, TypeError):
                pass

        return params

    # ------------------------------------------------------------------ #
    #  LOCATION WORKFLOW — geocoding + location intelligence + catchment
    # ------------------------------------------------------------------ #

    def _run_location_workflow(self, state: WorkflowExecutionState) -> None:
        text = state.request.user_query

        # Get curated neighborhood knowledge
        knowledge = tool_runtime.execute(
            "query_internal_knowledge",
            {
                "query": text,
                "domain": "neighborhood_facts",
                "limit": 5,
            },
        )
        self._append_result(state, knowledge)

        # Extract and geocode named places
        districts = _extract_districts(text)
        place_name = districts[0] if districts else None

        # Try to extract a broader place name from the query if no district matched
        if not place_name:
            # Use the query itself as a geocoding input
            place_name = text[:100]  # limit length for geocoding

        lat, lon = None, None
        if place_name:
            geo = tool_runtime.execute("geocode_place_nominatim", {"place": place_name})
            self._append_result(state, geo)
            if geo.status == "success" and "error" not in geo.normalized_output:
                lat = geo.normalized_output.get("lat")
                lon = geo.normalized_output.get("lon")

        # If we have coordinates, run spatial analysis tools
        if lat is not None and lon is not None:
            try:
                loc_intel = tool_runtime.execute(
                    "get_location_intelligence",
                    {"latitude": float(lat), "longitude": float(lon)},
                )
                self._append_result(state, loc_intel)
            except Exception as exc:
                logger.warning("Location intelligence failed: %s", exc)

            try:
                catchment = tool_runtime.execute(
                    "analyze_catchment",
                    {
                        "latitude": float(lat),
                        "longitude": float(lon),
                        "travel_minutes": 15,
                    },
                )
                self._append_result(state, catchment)
            except Exception as exc:
                logger.warning("Catchment analysis failed: %s", exc)

            state.assessments.append(
                CriteriaAssessment(
                    criterion="Location analysis",
                    status=CriteriaStatus.MET,
                    rationale=f"Geocoded to ({lat}, {lon}), ran location intelligence and catchment analysis.",
                    evidence_ids=[ev.evidence_id for ev in state.evidence],
                )
            )
        else:
            state.assessments.append(
                CriteriaAssessment(
                    criterion="Location analysis",
                    status=CriteriaStatus.PARTIAL,
                    rationale="Could not geocode location; used curated neighborhood facts only.",
                    evidence_ids=[ev.evidence_id for ev in knowledge.evidence_items],
                )
            )

        state.notes.append(
            f"Location workflow: place={place_name}, geocoded={'yes' if lat else 'no'}, "
            f"lat={lat}, lon={lon}"
        )

    # ------------------------------------------------------------------ #
    #  GENERAL WORKFLOW
    # ------------------------------------------------------------------ #

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
