"""Compose workflow answers from assessments and evidence."""

from __future__ import annotations

import json
from typing import Any

from src.services.agent_contracts import ComposedAnswer, WorkflowExecutionState

PROPERTY_MARKER_START = "<!--PROPERTIES_START-->"
PROPERTY_MARKER_END = "<!--PROPERTIES_END-->"
REFERENCE_MARKER_START = "<!--CHAT_REFERENCES_START-->"
REFERENCE_MARKER_END = "<!--CHAT_REFERENCES_END-->"


class ResponseComposer:
    async def compose(
        self,
        state: WorkflowExecutionState,
        llm: Any | None = None,
    ) -> ComposedAnswer:
        if llm is not None:
            composed = await self._compose_with_llm(state, llm)
            if composed is not None:
                return composed
        return self._compose_deterministic(state)

    def _compose_deterministic(self, state: WorkflowExecutionState) -> ComposedAnswer:
        lines: list[str] = []
        lines.append("## Criteria Coverage")
        for item in state.assessments:
            lines.append(f"- {item.criterion}: {item.status.value} - {item.rationale}")

        lines.append("\n## Evidence Used")
        for ev in state.evidence[:8]:
            lines.append(f"- {ev.kind} ({ev.source_id}, confidence={ev.confidence})")

        lines.append("\n## Analysis / Calculations")
        for note in state.notes[:8]:
            lines.append(f"- {note}")

        lines.append("\n## Recommendation")
        lines.append(
            "- Based on the available evidence, use the strongest candidates and explicitly treat unsupported items as open risks."
        )

        lines.append("\n## Data Gaps / Assumptions")
        unsupported = [
            a
            for a in state.assessments
            if a.status.value in {"unsupported", "partially_met"}
        ]
        if unsupported:
            for item in unsupported:
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
    ) -> ComposedAnswer | None:
        evidence_payload = [
            {
                "id": ev.evidence_id,
                "kind": ev.kind,
                "source_id": ev.source_id,
                "confidence": ev.confidence,
                "payload": ev.payload,
            }
            for ev in state.evidence[:12]
        ]
        assessments_payload = [
            assessment.model_dump() for assessment in state.assessments
        ]
        prompt = (
            "You are composing the final answer for a Bangkok real-estate workflow engine. "
            "Use only the supplied evidence and assessments. Do not invent unsupported facts. "
            "If a criterion is partial or unsupported, say so explicitly. "
            "Respond in the user's language. Use these exact sections:\n"
            "1. Criteria Coverage\n2. Evidence Used\n3. Analysis / Calculations\n4. Recommendation\n5. Data Gaps / Assumptions\n"
            "For legal questions, add a note that this is general information, not formal legal advice.\n\n"
            f"Workflow: {state.decision.workflow_id.value}\n"
            f"User query: {state.request.user_query}\n"
            f"Assessments JSON: {json.dumps(assessments_payload, ensure_ascii=False)}\n"
            f"Evidence JSON: {json.dumps(evidence_payload, ensure_ascii=False)}\n"
            f"Notes: {json.dumps(state.notes, ensure_ascii=False)}\n"
        )
        try:
            response = await llm.ainvoke(prompt)
            content = (
                response.content if hasattr(response, "content") else str(response)
            )
            if isinstance(content, str) and content.strip():
                return ComposedAnswer(
                    text=content.strip(),
                    assessments=state.assessments,
                    evidence_ids=[ev.evidence_id for ev in state.evidence],
                )
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
                        final_text,
                        property_results,
                        references,
                    )
                    return ComposedAnswer(
                        text=final_text,
                        assessments=state.assessments,
                        evidence_ids=[ev.evidence_id for ev in state.evidence],
                    )
        except Exception:
            return None
        return None

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
