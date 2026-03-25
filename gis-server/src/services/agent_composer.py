"""Compose workflow answers from assessments and evidence.

Improvements over v1:
- repair_feedback parameter for iterative repair loop
- Evidence is presented as numbered, structured items for better LLM grounding
- Hallucination guard: explicit "no data found" messaging when evidence is empty
- NOT_MET criteria are surfaced in Data Gaps (not silently ignored)
- Property markers appended consistently on both string and list LLM paths
"""

from __future__ import annotations

import json
from typing import Any

from src.services.agent_contracts import ComposedAnswer, WorkflowExecutionState

PROPERTY_MARKER_START = "<!--PROPERTIES_START-->"
PROPERTY_MARKER_END = "<!--PROPERTIES_END-->"
REFERENCE_MARKER_START = "<!--CHAT_REFERENCES_START-->"
REFERENCE_MARKER_END = "<!--CHAT_REFERENCES_END-->"

# ── System prompt for the composer LLM ─────────────────────────────────
_COMPOSER_SYSTEM_PROMPT = """\
You are composing the final answer for a Bangkok real-estate workflow engine.

## Hard rules
1. Use ONLY the supplied evidence and assessments. Do NOT invent project names that are not in the evidence. You MAY derive reasonable estimates and calculations from available data (see rule 17).
2. If evidence is completely empty for a criterion, say "ไม่พบข้อมูลในระบบ" — but if you have partial evidence, USE it and provide analysis.
3. Respond in the **user's language** (Thai if the query is in Thai).
4. Use these exact section headings:
   - สรุปผลการวิเคราะห์ (Summary / Analysis)
   - รายละเอียด (Details) — this is the main body with calculations, comparisons, recommendations
   - ข้อจำกัดของข้อมูล (Data Limitations) — keep this SHORT, 2-3 bullet points max
5. For legal questions, add a brief Thai-language disclaimer.
6. When citing evidence, reference it by its evidence ID, e.g. [ev-abc123].
7. Be CONCISE and DIRECT. No filler text, no lengthy preambles.
8. If the system notes contain WARNING_NO_DATA, inform the user briefly but still provide whatever analysis is possible.

## Result relevance filtering
9. DISCARD search results that do not match the user's request (wrong property type, wrong area). State the mismatch briefly; don't present irrelevant results.
10. When presenting results, note which user criteria each candidate satisfies vs doesn't — use ✅/❌ symbols for clarity.

## Calculations and estimates — CRITICAL
11. When price and area data are available, ALWAYS compute price per square meter.
12. When the user asks about travel time/distance, ESTIMATE it: use straight-line distance × 1.4 for driving distance, then assume 30 km/h average in Bangkok peak hours. Show the calculation.
13. For financial analysis:
    - ALWAYS build a simple revenue-expense model when the user asks about ROI/yield/break-even.
    - If exact data is missing, use reasonable Bangkok market assumptions and LABEL them as estimates. Example: "สมมติค่าเช่ารายวัน AirBnB ≈ 1,500-2,500 บาท/คืน (ประมาณการจากทำเลใกล้เคียง)"
    - Calculate: gross yield, net yield (after common fees ~40-60 บาท/ตรม./เดือน, management 15-20%), break-even period.
    - For loan analysis: monthly payment = P × [r(1+r)^n] / [(1+r)^n - 1], show the formula with numbers.
14. When the user asks for a specific number of options (e.g., "3 โครงการ"), try your best to provide that many. If you only have fewer fully-matching candidates, present them and then add partially-matching alternatives clearly marked as "ตรงเกณฑ์บางส่วน" rather than saying "ไม่พบข้อมูลครบ 3 โครงการ".
15. When the user mentions a budget, ALWAYS address it: state which options fall within budget and which don't.
16. For comparisons, use a structured comparison TABLE (markdown table) contrasting candidates on EACH criterion the user mentioned.

## Proactive estimation
17. When exact data points are missing but you have enough context to make a reasonable estimate, DO IT:
    - State it's an estimate (ประมาณการ)
    - Show your reasoning/formula
    - Use Bangkok real-estate norms: common fees 40-80 บาท/ตร.ม./เดือน, land tax 0.02-0.1% of appraised value, rental yield 3-6% gross for condos, 4-8% for shophouses, occupancy 85-95% near universities
    - This is MUCH more helpful than just saying "ไม่มีข้อมูล"
18. When the user asks about specific features (underground cables, closed kitchen, pet policy, number of bedrooms) that aren't in your evidence, say "ไม่พบข้อมูลในระบบ — แนะนำให้สอบถามโครงการโดยตรง" but DON'T let the missing feature dominate the response.

## Data limitations
19. The property listing database contains ONLY houses (บ้านเดี่ยว, ทาวน์เฮ้าส์, บ้านแฝด, ตึกแถว). Condo project data comes from knowledge base only. State this ONCE, briefly.
20. Keep the "ข้อจำกัดของข้อมูล" section to 2-3 short bullet points. The user cares about the ANALYSIS, not an exhaustive list of what's missing.
"""


class ResponseComposer:
    async def compose(
        self,
        state: WorkflowExecutionState,
        llm: Any | None = None,
        repair_feedback: str | None = None,
    ) -> ComposedAnswer:
        if llm is not None:
            composed = await self._compose_with_llm(state, llm, repair_feedback)
            if composed is not None:
                return composed
        return self._compose_deterministic(state)

    def _compose_deterministic(self, state: WorkflowExecutionState) -> ComposedAnswer:
        lines: list[str] = []

        # Hallucination guard: check for no-data warning
        has_no_data_warning = any("WARNING_NO_DATA" in note for note in state.notes)

        if has_no_data_warning:
            lines.append(
                "**หมายเหตุ**: ระบบไม่พบข้อมูลที่ตรงกับคำถามของคุณในฐานข้อมูล "
                "คำตอบด้านล่างอาจไม่ครบถ้วน\n"
            )

        lines.append("## Criteria Coverage")
        for item in state.assessments:
            lines.append(
                f"- {item.criterion}: **{item.status.value}** - {item.rationale}"
            )

        lines.append("\n## Evidence Used")
        if state.evidence:
            for i, ev in enumerate(state.evidence[:8], 1):
                lines.append(
                    f"- [{ev.evidence_id}] {ev.kind} (source: {ev.source_id}, confidence: {ev.confidence})"
                )
        else:
            lines.append("- ไม่พบข้อมูลจากเครื่องมือ (No tool evidence collected)")

        lines.append("\n## Analysis / Calculations")
        if state.notes:
            for note in state.notes[:8]:
                if not note.startswith("WARNING_"):
                    lines.append(f"- {note}")
        else:
            lines.append("- No analysis notes available.")

        lines.append("\n## Recommendation")
        if has_no_data_warning:
            lines.append("- ข้อมูลในระบบยังไม่ครบถ้วน กรุณาใช้ข้อมูลประกอบการตัดสินใจจากแหล่งอื่นด้วย")
        else:
            lines.append(
                "- Based on the available evidence, use the strongest candidates and "
                "explicitly treat unsupported items as open risks."
            )

        lines.append("\n## Data Gaps / Assumptions")
        gaps = [
            a
            for a in state.assessments
            if a.status.value in {"unsupported", "partially_met", "not_met"}
        ]
        if gaps:
            for item in gaps:
                lines.append(f"- {item.criterion}: {item.rationale}")
        else:
            lines.append("- No major gaps flagged by the workflow.")

        if state.decision.workflow_id.value == "legal_guidance":
            lines.append("\nหมายเหตุ: ข้อมูลนี้เป็นข้อมูลทั่วไป ไม่ใช่คำปรึกษากฎหมายเฉพาะคดี")

        property_results = self._extract_property_results(state)
        references = self._build_chat_references(property_results)
        self._append_reference_markers(lines, property_results, references)

        return ComposedAnswer(
            text="\n".join(lines),
            assessments=state.assessments,
            evidence_ids=[ev.evidence_id for ev in state.evidence],
        )

    async def _compose_with_llm(
        self,
        state: WorkflowExecutionState,
        llm: Any,
        repair_feedback: str | None = None,
    ) -> ComposedAnswer | None:
        # Build structured evidence for the LLM
        evidence_payload = []
        for i, ev in enumerate(state.evidence[:12], 1):
            evidence_payload.append(
                {
                    "index": i,
                    "id": ev.evidence_id,
                    "kind": ev.kind,
                    "source_id": ev.source_id,
                    "confidence": ev.confidence,
                    "payload": ev.payload,
                }
            )

        assessments_payload = [
            assessment.model_dump() for assessment in state.assessments
        ]

        # Build the user message
        user_parts = [
            f"Workflow: {state.decision.workflow_id.value}",
            f"User query: {state.request.user_query}",
            f"Assessments: {json.dumps(assessments_payload, ensure_ascii=False)}",
            f"Evidence ({len(evidence_payload)} items): {json.dumps(evidence_payload, ensure_ascii=False)}",
            f"Notes: {json.dumps(state.notes, ensure_ascii=False)}",
        ]

        if repair_feedback:
            user_parts.append(
                f"\n## REPAIR INSTRUCTION\n"
                f"The previous response failed verification: {repair_feedback}\n"
                f"Please fix the issues and regenerate the response."
            )

        prompt = _COMPOSER_SYSTEM_PROMPT + "\n\n" + "\n".join(user_parts)

        try:
            response = await llm.ainvoke(prompt)
            content = (
                response.content if hasattr(response, "content") else str(response)
            )

            # Handle string response
            if isinstance(content, str) and content.strip():
                final_text = content.strip()
                property_results = self._extract_property_results(state)
                references = self._build_chat_references(property_results)
                final_text = self._append_reference_markers_to_text(
                    final_text, property_results, references
                )
                return ComposedAnswer(
                    text=final_text,
                    assessments=state.assessments,
                    evidence_ids=[ev.evidence_id for ev in state.evidence],
                )

            # Handle list response (some models return list of content blocks)
            if isinstance(content, list):
                joined: list[str] = []
                for item in content:
                    if isinstance(item, str):
                        joined.append(item)
                    elif isinstance(item, dict):
                        text = item.get("text")
                        if isinstance(text, str):
                            joined.append(text)
                final_text = "".join(joined).strip()
                if final_text:
                    property_results = self._extract_property_results(state)
                    references = self._build_chat_references(property_results)
                    final_text = self._append_reference_markers_to_text(
                        final_text, property_results, references
                    )
                    return ComposedAnswer(
                        text=final_text,
                        assessments=state.assessments,
                        evidence_ids=[ev.evidence_id for ev in state.evidence],
                    )
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("LLM composition failed: %s", exc)
            return None
        return None

    # ── Property / reference extraction (unchanged) ────────────────────

    def _extract_property_results(
        self, state: WorkflowExecutionState
    ) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []

        for result in state.tool_results:
            properties = result.normalized_output.get("properties")
            if not isinstance(properties, list):
                continue

            for item in properties[:6]:
                if not isinstance(item, dict):
                    continue

                property_id = item.get("id")
                if property_id is None:
                    continue

                district = item.get("district")
                building_style = item.get("building_style")
                price = item.get("price_thb")
                building_area = item.get("building_area_sqm")
                listing_key = item.get("listing_key")
                house_ref = item.get("house_ref")
                locator = item.get("locator")

                collected.append(
                    {
                        "id": property_id,
                        "listing_key": listing_key,
                        "source_type": item.get("source_type", "house_price"),
                        "house_ref": house_ref,
                        "locator": locator,
                        "price": price,
                        "total_price": price,
                        "district": district,
                        "amphur": district,
                        "subdistrict": item.get("subdistrict"),
                        "style": building_style,
                        "building_style_desc": building_style,
                        "area": building_area,
                        "building_area": building_area,
                        "lat": item.get("lat"),
                        "lon": item.get("lon"),
                    }
                )

        return collected

    def _build_chat_references(
        self, property_results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        references: list[dict[str, Any]] = []

        for item in property_results:
            property_id = item.get("id")
            listing_key = item.get("listing_key")
            style = item.get("building_style_desc") or item.get("style") or "Property"
            district = item.get("district") or item.get("amphur")
            label = (
                f"{style} - house ID {property_id}"
                if property_id is not None
                else str(style)
            )

            if (
                listing_key
                and isinstance(listing_key, str)
                and not listing_key.startswith("house:")
            ):
                references.append(
                    {
                        "key": f"listing:{listing_key}",
                        "label": label,
                        "kind": "listing",
                        "listing_key": listing_key,
                        "note": district,
                    }
                )
                continue

            if property_id is None:
                continue

            references.append(
                {
                    "key": f"property:{property_id}",
                    "label": label,
                    "kind": "property",
                    "property_id": str(property_id),
                    "note": district,
                }
            )

        return references

    def _append_reference_markers(
        self,
        lines: list[str],
        property_results: list[dict[str, Any]],
        references: list[dict[str, Any]],
    ) -> None:
        marked = self._append_reference_markers_to_text(
            "\n".join(lines), property_results, references
        )
        lines.clear()
        lines.extend(marked.split("\n"))

    def _append_reference_markers_to_text(
        self,
        text: str,
        property_results: list[dict[str, Any]],
        references: list[dict[str, Any]],
    ) -> str:
        parts = [text.rstrip()]

        if property_results:
            parts.append(
                f"{PROPERTY_MARKER_START}{json.dumps(property_results, ensure_ascii=False)}{PROPERTY_MARKER_END}"
            )

        if references:
            parts.append(
                f"{REFERENCE_MARKER_START}{json.dumps(references, ensure_ascii=False)}{REFERENCE_MARKER_END}"
            )

        return "\n\n".join(part for part in parts if part)


response_composer = ResponseComposer()
