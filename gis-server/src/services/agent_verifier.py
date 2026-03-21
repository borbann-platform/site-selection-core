"""Verifier gate for workflow outputs."""

from __future__ import annotations

from src.services.agent_contracts import (
    VerificationResult,
    VerificationStatus,
    WorkflowExecutionState,
)


class WorkflowVerifier:
    def verify(
        self, state: WorkflowExecutionState, composed_text: str
    ) -> VerificationResult:
        lowered = composed_text.lower()
        required_sections = [
            "criteria coverage",
            "evidence used",
            "analysis",
            "recommendation",
            "data gaps",
        ]
        missing = [section for section in required_sections if section not in lowered]
        if missing:
            return VerificationResult(
                status=VerificationStatus.REPAIR,
                missing_sections=missing,
                message="Missing required output sections",
            )

        unsupported_count = sum(
            1 for item in state.assessments if item.status.value == "unsupported"
        )
        if unsupported_count > max(2, len(state.assessments) // 2):
            return VerificationResult(
                status=VerificationStatus.PARTIAL,
                message="Too many unsupported criteria for a strong final answer",
            )

        return VerificationResult(status=VerificationStatus.PASS)


workflow_verifier = WorkflowVerifier()
