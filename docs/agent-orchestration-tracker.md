# Agent Orchestration Reliability Tracker

This document tracks implementation progress for orchestration reliability, tool routing, memory quality, and response quality controls.

## Goal

Maximize:

- orchestration reliability
- tool routing quality
- memory quality
- response quality controls

## Rewrite Track

- Rewrite design source of truth: `docs/agent-rewrite-design.md`
- Rewrite mode: in-place replacement, API contract preserved
- Current status: design drafted, awaiting implementation review

## Decision Baseline

- Clarification Policy: strict
- Memory Strategy: hybrid (recent-window + rolling summary)
- RAG/runtime coupling: decouple embedding provider from chat provider
- Tool-call contract: hard enforce tool-first for factual claims
- Frontend stream path: unify to session-aware stream API

## Status Board

### Phase P0 - Risk Mitigation (done)

- [x] Remove duplicate tool registration for `retrieve_knowledge`
- [x] Fix failing tool unit test (`test_search_respects_limit`)
- [x] Unify frontend stream path to `streamAgentChatWithSession`
- [x] Capture/reuse `X-Session-ID` for continuity

### Phase P1 - Core Controls (in progress)

- [x] Improve strict clarification heuristics for comparison targets
- [x] Add hard tool-first enforcement guardrail (initial)
- [x] Add hybrid context loading (`summary + recent window`) using session metadata
- [x] Refresh rolling summary every 4 user turns (async; non-blocking to SSE)
- [x] Add explicit session-end summary finalization hook
- [x] Harden tool-first enforcement beyond heuristic intent detection (v2)

### Phase P2 - Decoupling + Observability + Validation (in progress)

- [x] Add embedding-provider config decoupled from chat provider
- [x] Extend chat provider/status/validate endpoints with embedding metadata
- [x] Add orchestration metrics: tool calls, latency, clarifications, stream completion
- [x] Add quality gate checker script for golden benchmark reports
- [x] Add comprehensive orchestration contract tests (event ordering + violation paths)
- [ ] Add load/soak quality validation for agent flows

## Implemented Changes (file-level)

- Backend
  - `gis-server/src/services/agent_graph.py`
  - `gis-server/src/services/task_planner.py`
  - `gis-server/src/services/chat_service.py`
  - `gis-server/src/services/rag_service.py`
  - `gis-server/src/config/agent_settings.py`
  - `gis-server/src/routes/chat.py`
  - `gis-server/src/routes/observability.py`
  - `gis-server/src/routes/chat_sessions.py`
  - `gis-server/src/services/observability.py`
  - `gis-server/scripts/check_agent_quality_gate.py`
  - `.github/workflows/test.yml`
  - `gis-server/tests/unit/test_agent_tools.py`
  - `gis-server/tests/unit/test_task_planner.py`
  - `gis-server/tests/integration/test_chat_api.py`
- Frontend
  - `frontend/src/lib/chatApi.ts`
  - `frontend/src/stores/chatStore.ts`
  - `frontend/src/hooks/usePropertyExplorer.ts`

## Test Evidence

- Passed: backend unit tests
  - `tests/unit/test_task_planner.py`
  - `tests/unit/test_agent_tools.py`
  - `tests/unit/test_chat_error_payload.py`
- Passed: backend integration tests
  - `tests/integration/test_chat_api.py`
- Golden benchmark executed
  - `gis-server/reports/agent_orchestration_quality.json`
  - Current gate status: failed (median score + tool-first misses)
- Passed: frontend lint
  - `npm run -s lint`

## Golden Test Set (User-provided)

The following 10 prompts are designated as the golden quality benchmark set.

### Coverage Categories

- Complex Multi-Criteria Search
- ROI & Investment Analysis
- Comparative Neighborhood Analysis
- Lifestyle & Amenities Integration
- Legal & Financial Logic (Edge Case)
- Financial Planning

### Source

Use the user-provided JSON benchmark set (IDs 1-10) as canonical test inputs and criteria.

### Evaluation Method

- Run each prompt via `/api/v1/chat/agent` with deterministic runtime config where possible.
- Record:
  - clarification behavior (if any)
  - tool sequence
  - final response
  - tool-first compliance
- Evaluate quality using an LLM-as-judge rubric against each prompt's `evaluation_criteria`.
- Persist results in a report artifact for regression tracking.

## Open Items Requiring Design/Implementation

- Improve tool-first detector precision for compare/analytics vs legal/financial-formula intents.
- Add load-test/soak-test scenario runner and baseline thresholds.

## Next Sprint Tasks

1. Improve tool routing for compare and ROI prompts (reduce unnecessary clarification).
2. Add dedicated financial/legal tools for non-listing analytic intents.
3. Re-run golden benchmark and compare against baseline report.
4. Enable mandatory CI gate after benchmark score recovery.
5. Add load/soak reliability validation.
