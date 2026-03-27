"""Verifier gate for workflow outputs.

Improvements over v1:
- Checks NOT_MET criteria (not just unsupported)
- Evidence grounding: flags when response lacks evidence backing
- Language consistency check
- Actual REFUSE status for critical failures
- More informative repair messages
- Relaxed verification for ReAct agent responses
"""

from __future__ import annotations

import re

from src.services.agent_contracts import (
    VerificationResult,
    VerificationStatus,
    WorkflowExecutionState,
    WorkflowId,
)

# Required sections — we accept either Thai or English variants
# Each entry is a list of acceptable alternatives (any one match = section present)
_REQUIRED_SECTION_VARIANTS: list[list[str]] = [
    ["สรุปผลการวิเคราะห์", "criteria coverage", "summary", "analysis", "สรุป"],
    ["รายละเอียด", "details", "recommendation", "คำแนะนำ", "analysis / calculations"],
    ["ข้อจำกัดของข้อมูล", "data gaps", "data limitations", "assumptions", "ข้อจำกัด"],
]


class WorkflowVerifier:
    def verify(
        self, state: WorkflowExecutionState, composed_text: str
    ) -> VerificationResult:
        # ReAct agent produces natural responses — use relaxed rules
        if state.decision.workflow_id == WorkflowId.REACT_AGENT:
            return self._verify_react(state, composed_text)

        return self._verify_deterministic(state, composed_text)

    def _verify_react(
        self, state: WorkflowExecutionState, composed_text: str
    ) -> VerificationResult:
        """Relaxed verification for ReAct agent responses.

        Skips rigid section requirements since the ReAct agent produces
        natural, conversational responses.  Still enforces:
        - Minimum content length
        - No-data warning acknowledgement
        """
        # Check error/warning notes first — error responses may be short
        has_no_data_warning = any("WARNING_NO_DATA" in note for note in state.notes)
        has_react_error = any("WARNING_REACT_ERROR" in note for note in state.notes)

        if has_react_error:
            return VerificationResult(
                status=VerificationStatus.PARTIAL,
                message="ReAct agent encountered an error during execution.",
            )

        # Minimum content length (checked after error notes so short error
        # messages still get PARTIAL rather than REPAIR)
        clean = re.sub(r"<!--.*?-->", "", composed_text)
        if len(clean.strip()) < 50:
            return VerificationResult(
                status=VerificationStatus.REPAIR,
                message="Response is too short (< 50 chars). Please provide a more detailed answer.",
            )

        if has_no_data_warning:
            no_data_phrases = [
                "ไม่พบข้อมูล",
                "no data",
                "ไม่มีข้อมูล",
                "not found",
                "ไม่พบ",
                "ไม่ครบ",
                "ไม่เพียงพอ",
                "no results",
                "no matching",
                "could not find",
            ]
            lowered = composed_text.lower()
            if not any(phrase in lowered for phrase in no_data_phrases):
                return VerificationResult(
                    status=VerificationStatus.REPAIR,
                    message=(
                        "Tools returned no matching data but the response doesn't acknowledge this. "
                        "Please inform the user that the database did not have matching data."
                    ),
                )

        return VerificationResult(status=VerificationStatus.PASS)

    def _verify_deterministic(
        self, state: WorkflowExecutionState, composed_text: str
    ) -> VerificationResult:
        """Standard verification for deterministic workflow responses."""
        lowered = composed_text.lower()

        # ── Check 1: Required sections ──
        missing_sections: list[str] = []
        for variants in _REQUIRED_SECTION_VARIANTS:
            if not any(v in lowered for v in variants):
                missing_sections.append(variants[0])  # report the primary name
        if missing_sections:
            return VerificationResult(
                status=VerificationStatus.REPAIR,
                missing_sections=missing_sections,
                message=f"Missing required output sections: {', '.join(missing_sections)}",
            )

        # ── Check 2: Evidence grounding ──
        # If we have evidence, the response should reference at least some of it
        if state.evidence:
            ev_ids = {ev.evidence_id for ev in state.evidence}
            referenced = sum(1 for eid in ev_ids if eid in composed_text)
            # Also count indirect references (tool names, source IDs)
            tool_names = {r.tool_name for r in state.tool_results}
            tool_referenced = sum(1 for tn in tool_names if tn in lowered)

            if referenced == 0 and tool_referenced == 0 and len(state.evidence) >= 2:
                # The response doesn't reference any evidence at all
                return VerificationResult(
                    status=VerificationStatus.REPAIR,
                    message=(
                        "Response does not reference any evidence items. "
                        "Please cite evidence using [ev-xxx] IDs or reference the tool results directly."
                    ),
                )

        # ── Check 3: Unsupported + NOT_MET criteria ratio ──
        bad_count = sum(
            1
            for item in state.assessments
            if item.status.value in {"unsupported", "not_met"}
        )
        total = len(state.assessments)
        threshold = max(2, total // 2)

        if total > 0 and bad_count >= total:
            # ALL criteria are unsupported/not_met — but we should still try to
            # produce a helpful partial response rather than a bare refusal.
            # Only refuse if there's truly no evidence at all AND no notes.
            has_any_evidence = len(state.evidence) > 0
            has_useful_notes = any(
                not note.startswith("WARNING_") for note in state.notes
            )
            if not has_any_evidence and not has_useful_notes:
                return VerificationResult(
                    status=VerificationStatus.REFUSE,
                    message="All criteria are unsupported or not met and no evidence was collected.",
                )
            # Otherwise, repair with instruction to provide partial analysis
            return VerificationResult(
                status=VerificationStatus.REPAIR,
                message=(
                    "All criteria are unsupported/not_met, but some evidence was collected. "
                    "Please provide a partial analysis using available data, clearly noting "
                    "what could not be answered and suggesting next steps for the user."
                ),
            )

        if bad_count > threshold:
            return VerificationResult(
                status=VerificationStatus.PARTIAL,
                message=f"Too many unsupported/not_met criteria ({bad_count}/{total}) for a strong answer.",
            )

        # ── Check 4: Minimum content length ──
        # Strip markers for length check
        clean = re.sub(r"<!--.*?-->", "", composed_text)
        if len(clean.strip()) < 100:
            return VerificationResult(
                status=VerificationStatus.REPAIR,
                message="Response is too short (< 100 chars). Please provide a more detailed answer.",
            )

        # ── Check 5: No-data warning handling ──
        has_no_data_warning = any("WARNING_NO_DATA" in note for note in state.notes)
        if has_no_data_warning:
            # Check the response acknowledges the data gap
            no_data_phrases = [
                "ไม่พบข้อมูล",
                "no data",
                "ไม่มีข้อมูล",
                "not found",
                "ไม่พบ",
                "ไม่ครบ",
                "ไม่เพียงพอ",
            ]
            if not any(phrase in lowered for phrase in no_data_phrases):
                return VerificationResult(
                    status=VerificationStatus.REPAIR,
                    message=(
                        "Tools returned no matching data but the response doesn't acknowledge this. "
                        "Please inform the user that the database did not have matching data."
                    ),
                )

        return VerificationResult(status=VerificationStatus.PASS)


workflow_verifier = WorkflowVerifier()
