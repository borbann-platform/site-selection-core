"""LangGraph ReAct agent for complex, multi-step, and cross-domain queries.

This module provides a ReAct (Reason + Act) agent that uses LangGraph's
``create_react_agent`` to let the LLM dynamically choose which tools to call,
inspect results, and iterate until it has enough information to answer.

The ReAct agent is invoked by the workflow engine when the router classifies
a query as ``react_agent`` — typically for:
- Cross-workflow queries (e.g. search + financial analysis)
- Open-ended exploration (e.g. "best area to invest in Bangkok")
- Multi-step reasoning (e.g. compare areas → pick best → find properties)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.config.agent_settings import agent_settings
from src.services.agent_contracts import (
    EvidenceItem,
    NormalizedAgentRequest,
    ToolExecutionResult,
    WorkflowExecutionState,
)
from src.services.agent_tools import ALL_TOOLS

logger = logging.getLogger(__name__)

# ── System prompt for the ReAct agent ──────────────────────────────────

_REACT_SYSTEM_PROMPT = """\
You are a Bangkok real-estate AI assistant with access to specialised tools \
for property search, financial analysis, location intelligence, and legal guidance.

## Your capabilities
You can search property databases, compute financial projections (DSR, ROI, \
break-even), analyse locations (walkability, catchment, amenities), retrieve \
legal checklists, and consult a knowledge base.

## Hard rules
1. **Always use tools** to ground your answers in data.  Never fabricate \
   prices, statistics, property names, or legal advice.
2. If a tool returns no results or errors, **acknowledge the data gap** \
   honestly — do not hallucinate alternative data.
3. Do **not** call the same tool with identical parameters more than once.
4. Limit yourself to at most {max_iterations} tool calls per response.
5. When doing financial calculations, **state your assumptions** clearly \
   (interest rate, tenure, occupancy rate, etc.).
6. For legal topics, always caveat: "นี่เป็นข้อมูลทั่วไป ไม่ใช่คำปรึกษา\
กฎหมายเฉพาะคดี" (general guidance, not case-specific legal advice).
7. Respond in the **same language the user used** (Thai → Thai, English → \
   English).  Keep formatting clean with markdown.
8. Be **concise and direct**.  No filler text or lengthy preambles.
9. When presenting property results, include key facts: price, area (sqm), \
   district, and price-per-sqm when computable.
10. For multi-step analyses, explain your reasoning briefly before each \
    tool call so the user can follow your thought process.
"""


def _build_react_system_prompt() -> str:
    """Return the system prompt with runtime config values interpolated."""
    return _REACT_SYSTEM_PROMPT.format(
        max_iterations=agent_settings.REACT_AGENT_MAX_ITERATIONS,
    )


def _build_context_message(request: NormalizedAgentRequest) -> str:
    """Build a context string from spatial attachments and conversation history."""
    parts: list[str] = []

    if request.spatial_context:
        parts.append(f"[Spatial context from map]\n{request.spatial_context}")

    if request.session_summary:
        parts.append(f"[Conversation summary]\n{request.session_summary}")

    return "\n\n".join(parts)


async def run_react_agent(
    state: WorkflowExecutionState,
    llm: BaseChatModel,
) -> AsyncIterator[dict[str, Any]]:
    """Execute the ReAct agent loop and yield streaming events.

    Events emitted (same protocol as the deterministic engine):
        - ``tool_call``   : ``{"name": ..., "input": ...}``
        - ``tool_result`` : serialised tool output
        - ``thinking``    : intermediate reasoning text (optional)
        - ``final``       : the agent's composed answer

    The function also populates ``state.tool_results`` and ``state.evidence``
    so that downstream verification can inspect what happened.
    """
    from langgraph.prebuilt import create_react_agent

    max_iterations = agent_settings.REACT_AGENT_MAX_ITERATIONS
    timeout_seconds = agent_settings.AGENT_TOOL_TIMEOUT_SECONDS * max_iterations

    # Build messages for the agent
    messages: list[Any] = []

    # Add context (spatial, summary) as a leading human message if present
    context_text = _build_context_message(state.request)
    if context_text:
        messages.append(HumanMessage(content=context_text))

    # Add recent conversation history for multi-turn context
    for msg in state.request.recent_messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if not content:
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    # Add the current user query
    messages.append(HumanMessage(content=state.request.user_query))

    # Create the ReAct agent with all available tools
    # LLM must support tool calling (bind_tools); LangChain providers do this.
    react_agent = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=_build_react_system_prompt(),
    )

    # Stream events from the agent with a global timeout
    tool_call_count = 0
    final_text = ""

    try:
        async with asyncio.timeout(timeout_seconds):
            async for event in react_agent.astream_events(
                {"messages": messages},
                version="v2",
            ):
                kind = event.get("event", "")
                data = event.get("data", {})

                # ── Tool invocation started ──
                if kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = data.get("input", {})
                    tool_call_count += 1

                    yield {
                        "type": "tool_call",
                        "content": {
                            "name": tool_name,
                            "input": tool_input
                            if isinstance(tool_input, dict)
                            else {"query": str(tool_input)},
                        },
                    }

                # ── Tool invocation finished ──
                elif kind == "on_tool_end":
                    tool_output = data.get("output", "")
                    tool_name = event.get("name", "unknown")

                    # Normalise output for evidence tracking
                    normalised = _normalise_tool_output(tool_output)

                    # Record in state for verification pipeline
                    evidence = _to_evidence(tool_name, normalised)
                    tool_result = ToolExecutionResult(
                        tool_name=tool_name,
                        status="success" if "error" not in normalised else "error",
                        tool_input=data.get("input", {}),
                        raw_output=tool_output
                        if isinstance(tool_output, (str, dict))
                        else str(tool_output),
                        normalized_output=normalised,
                        evidence_items=evidence,
                    )
                    state.tool_results.append(tool_result)
                    state.evidence.extend(evidence)

                    yield {
                        "type": "tool_result",
                        "content": json.dumps(
                            normalised, ensure_ascii=False, default=str
                        ),
                    }

                # ── LLM streaming tokens (final answer or reasoning) ──
                elif kind == "on_chat_model_stream":
                    chunk = data.get("chunk")
                    if chunk and hasattr(chunk, "content"):
                        content = chunk.content
                        if isinstance(content, str) and content:
                            final_text += content

    except TimeoutError:
        logger.warning(
            "ReAct agent timed out after %ds (%d tool calls)",
            timeout_seconds,
            tool_call_count,
        )
        if not final_text:
            final_text = (
                "ขออภัย การวิเคราะห์ใช้เวลานานเกินไป กรุณาลองถามคำถามที่เจาะจงมากขึ้น\n\n"
                "(The analysis timed out. Please try a more specific question.)"
            )
        state.notes.append(
            f"WARNING_REACT_TIMEOUT: Agent timed out after {timeout_seconds}s"
        )

    except Exception as exc:
        logger.error("ReAct agent error: %s", exc, exc_info=True)
        if not final_text:
            final_text = (
                "เกิดข้อผิดพลาดระหว่างการวิเคราะห์ กรุณาลองใหม่อีกครั้ง\n\n"
                f"(An error occurred during analysis: {exc!s})"
            )
        state.notes.append(f"WARNING_REACT_ERROR: {exc!s}")

    # Ensure we have a final response
    if not final_text.strip():
        final_text = (
            "ไม่สามารถสร้างคำตอบได้ กรุณาลองถามใหม่อีกครั้ง\n\n"
            "(Could not generate a response. Please try again.)"
        )

    yield {"type": "final", "content": final_text}

    logger.info(
        "ReAct agent completed: %d tool calls, %d evidence items, %d chars",
        tool_call_count,
        len(state.evidence),
        len(final_text),
    )


# ── Helper functions ───────────────────────────────────────────────────


def _normalise_tool_output(raw_output: Any) -> dict[str, Any]:
    """Normalise tool output to a dict, matching ToolRuntime behaviour."""
    if isinstance(raw_output, dict):
        return raw_output

    # ToolMessage or similar wrapper
    if hasattr(raw_output, "content"):
        raw_output = raw_output.content

    if isinstance(raw_output, str):
        try:
            parsed = json.loads(raw_output)
            if isinstance(parsed, dict):
                return parsed
            return {"data": parsed}
        except (json.JSONDecodeError, TypeError):
            return {"text": raw_output}

    return {"data": str(raw_output)}


def _to_evidence(
    tool_name: str, normalised_output: dict[str, Any]
) -> list[EvidenceItem]:
    """Create evidence items from normalised tool output."""
    if "error" in normalised_output:
        return []
    return [
        EvidenceItem(
            kind=f"tool:{tool_name}",
            source_type="tool",
            source_id=tool_name,
            payload=normalised_output,
        )
    ]
