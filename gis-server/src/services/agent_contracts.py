"""Canonical contracts for the rewritten agent workflow engine."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class WorkflowId(str, Enum):
    LISTING_SEARCH = "listing_search"
    COMPARATIVE_SCORECARD = "comparative_scorecard"
    FINANCIAL_ANALYSIS = "financial_analysis"
    LEGAL_GUIDANCE = "legal_guidance"
    LOCATION_ANALYSIS = "location_analysis"
    GENERAL_GUIDED = "general_guided"
    REACT_AGENT = "react_agent"


class CriteriaStatus(str, Enum):
    MET = "met"
    PARTIAL = "partially_met"
    NOT_MET = "not_met"
    UNSUPPORTED = "unsupported"


class VerificationStatus(str, Enum):
    PASS = "pass"
    REPAIR = "repair"
    PARTIAL = "partial"
    REFUSE = "refuse"


class NormalizedAgentRequest(BaseModel):
    user_query: str
    language: str = "th"
    recent_messages: list[dict[str, str]] = Field(default_factory=list)
    session_summary: str | None = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    spatial_context: str | None = None
    raw_messages: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowDecision(BaseModel):
    workflow_id: WorkflowId
    confidence: float = 1.0
    reason: str
    clarification_needed: bool = False
    missing_inputs: list[str] = Field(default_factory=list)
    clarification_message: str | None = None


class EvidenceItem(BaseModel):
    evidence_id: str = Field(default_factory=lambda: f"ev-{uuid4().hex[:12]}")
    kind: str
    source_type: str
    source_id: str
    retrieved_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    confidence: str = "medium"
    geo_scope: str | None = None
    payload: dict[str, Any]


class ToolExecutionResult(BaseModel):
    tool_name: str
    status: str
    tool_input: dict[str, Any]
    raw_output: Any
    normalized_output: dict[str, Any]
    evidence_items: list[EvidenceItem] = Field(default_factory=list)


class CriteriaAssessment(BaseModel):
    criterion: str
    status: CriteriaStatus
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)


class WorkflowExecutionState(BaseModel):
    request: NormalizedAgentRequest
    decision: WorkflowDecision
    criteria: list[str] = Field(default_factory=list)
    assessments: list[CriteriaAssessment] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    tool_results: list[ToolExecutionResult] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ComposedAnswer(BaseModel):
    text: str
    assessments: list[CriteriaAssessment] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    status: VerificationStatus
    missing_sections: list[str] = Field(default_factory=list)
    message: str | None = None
