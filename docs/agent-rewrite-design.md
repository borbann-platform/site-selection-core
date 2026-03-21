# Agent Rewrite Design

This document defines the in-place rewrite of the conversation agent while preserving the current external API contract.

## Goal

Rewrite the internal agent architecture so it is production-ready, evidence-first, workflow-driven, and benchmarkable, while keeping the existing client-facing API stable.

## Preserve As-Is

- `POST /api/v1/chat/agent`
- SSE event contract:
  - `thinking`
  - `step`
  - `token`
  - `error`
  - `done`
- `X-Session-ID`
- request payload shape:
  - `messages`
  - `session_id`
  - `attachments`
  - `runtime`
- database session/message persistence model
- frontend stream consumption contract

## Replace Internally

- prompt-centric ReAct orchestration as the primary execution model
- heuristic-first clarification as the main gatekeeper
- loose tool-success inference
- string-only tool outputs as the main evidence layer
- weak internal knowledge lookup
- post-hoc answer checking without hard repair gates

## Design Principles

- Evidence first
- Workflow driven
- Deterministic where correctness matters
- Agentic where judgment helps
- Fail closed on unsupported factual claims
- Explicitly mark partial/unknown criteria instead of guessing
- Separate memory from evidence
- Preserve API compatibility during the rewrite

## What "Agentic" Means In This Rewrite

This system still uses agentic AI, but in a bounded production-safe form.

Use model-driven behavior for:

- intent understanding
- ambiguity handling
- answer composition
- answer repair

Use deterministic logic for:

- workflow routing
- required tool execution
- calculations
- evidence validation
- final-answer gating

This is not a free-form autonomous ReAct agent. It is a controlled multi-stage reasoning system.

## Canonical Internal Pipeline

1. Normalize request
2. Route to workflow
3. Validate required inputs
4. Execute workflow steps
5. Collect typed evidence
6. Compose response from evidence
7. Verify criteria coverage and evidence support
8. Repair if needed
9. Stream final output through existing SSE contract

## Core Components

### 1. Request Normalizer

Responsibility:

- convert request payload into canonical internal request state
- combine user message, attachments, and session memory
- sanitize spatial context deterministically

Input:

- chat request payload
- persisted session state

Output:

- `NormalizedAgentRequest`

Acceptance criteria:

- identical input produces identical normalized state
- invalid coordinates and malformed attachments are sanitized or rejected consistently

### 2. Routing Engine

Responsibility:

- map normalized request to one workflow
- use deterministic rules first
- use LLM classification only as bounded fallback

Supported workflow ids:

- `listing_search`
- `comparative_scorecard`
- `financial_analysis`
- `legal_guidance`
- `location_analysis`
- `general_guided`

Acceptance criteria:

- explicit compare targets never trigger redundant compare clarification
- finance prompts with enough numbers route directly to financial workflow
- legal prompts route to legal workflow without property-comparison confusion

### 3. Workflow Registry

Responsibility:

- define supported workflows
- define required inputs
- define allowed assumptions
- define required evidence
- define step order
- define final output contract

Each workflow includes:

- id
- description
- required inputs
- optional assumptions
- required tools
- stop conditions
- refusal conditions
- response contract

### 4. Tool Runtime

Responsibility:

- execute tools through typed adapters
- normalize outputs
- attach provenance and confidence
- classify failures consistently

Tool runtime requirements:

- timeout policy
- retry policy where safe
- structured result object
- tool step event mapping back to SSE

### 5. Evidence Ledger

Responsibility:

- convert tool outputs into typed evidence objects
- track provenance and confidence
- provide evidence references to composer and verifier

Evidence object minimum fields:

- `evidence_id`
- `kind`
- `source_type`
- `source_id`
- `retrieved_at`
- `confidence`
- `geo_scope`
- `payload`
- `supports_claims`

Rule:

- factual claims in final response must be backed by evidence items

### 6. Knowledge Service

Responsibility:

- serve curated internal domain data
- support deterministic lookup with aliases and filters
- return typed records with provenance

Initial knowledge packs:

- `project_metadata`
- `neighborhood_facts`
- `legal_guidelines_th`

Later additions:

- benchmark coverage manifest
- market proxy assumptions
- policy/reference notes

### 7. Response Composer

Responsibility:

- build final answer from workflow state and evidence
- never compose directly from raw tool output without normalization

Complex workflow output sections:

1. Criteria Coverage
2. Evidence Used
3. Analysis / Calculations
4. Recommendation
5. Data Gaps / Assumptions

Legal workflow must also include:

- general information only / not formal legal advice notice

### 8. Verifier Gate

Responsibility:

- validate criterion coverage
- validate evidence support
- validate required sections
- trigger repair or partial-completion path

Verifier outcomes:

- `pass`
- `repair`
- `partial`
- `refuse`

Rule:

- no final response leaves the workflow without verifier decision

### 9. Memory Service

Responsibility:

- preserve rolling summary and recent context
- track persistent user preferences
- keep memory separate from evidentiary truth

Memory classes:

- session summary
- recent transcript window
- stable user preferences
- non-evidentiary context only

## Workflow Definitions

### Listing Search

Use for:

- property finding
- shortlist generation
- strict candidate filtering

Required behavior:

- apply hard filters first
- use curated metadata for unsupported DB fields
- rank candidates with explicit criteria scoring

Required tools:

- `search_properties`
- `query_internal_knowledge`
- `compare_candidates_by_criteria`
- optional location tools when relevant

### Comparative Scorecard

Use for:

- compare area A vs area B
- compare project A vs project B
- compare investment neighborhood options

Required behavior:

- create criterion-by-criterion matrix
- gather evidence for both sides
- clearly label proxy-based conclusions

Required tools:

- `get_market_statistics`
- `query_internal_knowledge`
- `compare_candidates_by_criteria`
- optional location tools

### Financial Analysis

Use for:

- DSR
- affordability
- break-even
- yield / ROI
- leverage scenarios

Required behavior:

- code-driven calculations first
- assumptions explicit
- no irrelevant clarification if enough numeric inputs already exist

Required tools:

- `compute_dsr_and_affordability`
- `compute_financial_projection`
- optional market/knowledge inputs

### Legal Guidance

Use for:

- inheritance sale process
- deposit risk control
- contract conditions precedent
- Thai property process questions

Required behavior:

- use curated legal pack
- use legal checklist tool
- mark as general information, not legal advice

Required tools:

- `legal_estate_sale_checklist_th`
- `query_internal_knowledge`

### Location Analysis

Use for:

- walkability
- catchment
- nearby amenities
- site potential

Required tools:

- `get_location_intelligence`
- `analyze_catchment`
- `analyze_site`
- `geocode_place_nominatim` when needed

## Clarification Policy

Clarification is allowed only when a required workflow input is genuinely missing.

Clarification must not be asked when:

- compare targets are explicitly named
- enough numeric inputs exist for bounded financial assumptions
- internal knowledge or defaults can support a reasonable partial answer

When clarification is not required but evidence is incomplete:

- proceed
- label unsupported criteria explicitly
- return partial status for those criteria

## Supported vs Unsupported Criteria Policy

For each criterion in a user request, the system must classify one of:

- `met`
- `partially_met`
- `not_met`
- `unsupported`

Rules:

- do not silently substitute a proxy for a missing direct fact
- when using a proxy, label it clearly
- when unsupported, say what data is missing

## Typed Schemas To Introduce

Planned internal types:

- `NormalizedAgentRequest`
- `WorkflowDecision`
- `WorkflowExecutionState`
- `ToolExecutionResult`
- `EvidenceItem`
- `CriteriaAssessment`
- `ComposedAnswer`
- `VerificationResult`

## Observability Requirements

Every request should produce enough information to replay the decision path.

Track:

- workflow id
- routing reason
- clarification reason
- tool calls
- evidence ids
- verifier status
- repair attempts
- stream completion status

## Evaluation Strategy

### Existing golden set remains canonical

The 10-case benchmark remains the primary quality harness.

### New required checks

- workflow selected per case
- required tools used per case
- unsupported criteria labeled when needed
- verifier status logged
- no parse-error judge outputs

### CI gate target after recovery

- median score >= 7.0
- no factual-case tool misses
- no runtime failures
- no explicit-target false clarification

## Migration Strategy (In-Place)

This rewrite is in-place, not parallel.

Implementation order:

1. Introduce canonical schemas and workflow registry
2. Replace current route/planner/clarification precedence
3. Replace free-form orchestration with workflow runner
4. Introduce typed tool runtime and evidence ledger
5. Integrate curated knowledge service deeply
6. Add verifier repair gate
7. Re-run benchmark and tighten gates

## Risks

- in-place replacement increases regression risk
- current benchmark may expose data gaps even after architecture improves
- curated knowledge packs require disciplined maintenance
- full rewrite may temporarily destabilize current passing integration behavior

## Non-Goals

- do not change the frontend API contract
- do not depend on external paid APIs
- do not hide unsupported criteria behind generic advice
- do not optimize for token cost at the expense of correctness

## Definition of Done for This PR

- new internal workflow-driven architecture is in place
- external API contract unchanged
- golden benchmark rerun is valid and materially improved
- quality gate passes or has a clearly documented narrow remaining gap with explicit rationale
- docs and tests reflect the rewritten system

## Implementation Tracker

### Planned phases

- [ ] Define canonical schemas and workflow registry
- [ ] Replace route/planner precedence with deterministic workflow selection
- [ ] Introduce typed tool runtime and evidence ledger
- [ ] Integrate curated internal knowledge into workflows
- [ ] Implement response composer + verifier repair gate
- [ ] Re-run golden benchmark and compare against baseline
- [ ] Make CI quality gate mandatory when stable

### Notes

- Use this file as the source of truth during rewrite.
- Update the checkboxes and major findings as implementation progresses.
