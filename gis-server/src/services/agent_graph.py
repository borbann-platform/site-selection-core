"""
LangGraph agent orchestration with provider-agnostic model backends.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any, TypedDict, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphRecursionError
from langgraph.prebuilt import create_react_agent

from src.config.agent_settings import agent_settings
from src.services.agent_tools import ALL_TOOLS
from src.services.model_provider import (
    RuntimeModelConfig,
    get_model_provider,
    resolve_runtime_config,
)
from src.services.rag_service import retrieve_knowledge
from src.services.task_planner import TaskPlanner, build_clarification_message

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are Borbann AI, a Bangkok real-estate assistant.

## Core Behavior
- Use tools proactively before giving conclusions.
- If UI map context references a selected house, validate it with `validate_house_reference` before deeper analysis.
- Use ReAct reasoning: think briefly, act with tools, observe outputs, then continue.
- Return concise, data-backed answers with clear numbers.
- Keep output in the user's language (Thai/English).

## Available Tools
- search_properties
- validate_house_reference
- get_nearby_properties
- get_market_statistics
- get_location_intelligence
- analyze_site
- analyze_catchment
- predict_property_price
- retrieve_knowledge

## Spatial Grounding Rules
- If user says "this location", "here", "this area", use coordinates from [SPATIAL CONTEXT FROM MAP].
- For bounding boxes, use min_lat/max_lat/min_lon/max_lon in `search_properties`.
- If no spatial target exists but query requires one, ask a clarification question.

## Reasoning and Output
- For complex requests, follow [TASK DAG] dependencies step by step.
- Use tables/bullets where useful.
- Be explicit about confidence and assumptions.
"""


class AgentState(TypedDict):
    """State for decomposition + execution."""

    messages: list[BaseMessage]
    task_dag: dict[str, Any] | None
    next_step: str


class AgentService:
    """Service for running the Plan-and-Execute LangGraph agent."""

    def __init__(self):
        self._agents: dict[str, Any] = {}
        self._planner_llms: dict[str, Any] = {}
        self._planner = TaskPlanner()

    def _ensure_initialized(
        self,
        runtime_config: RuntimeModelConfig | None = None,
    ) -> tuple[str, RuntimeModelConfig]:
        """Lazy initialization of provider-specific models and agent graph."""
        effective_runtime = runtime_config or RuntimeModelConfig(
            provider=agent_settings.AGENT_PROVIDER
        )
        resolved = resolve_runtime_config(effective_runtime)

        if not resolved.is_configured:
            raise ValueError(
                "Agent not configured for selected provider. "
                "Provide BYOK runtime credentials or configure environment defaults."
            )

        cache_key = resolved.cache_key()
        if cache_key in self._agents and cache_key in self._planner_llms:
            return cache_key, effective_runtime

        provider = get_model_provider(resolved.provider)

        execution_llm = provider.create_chat_model(
            resolved,
            temperature=resolved.temperature,
            max_tokens=resolved.max_tokens,
        )
        planner_llm = provider.create_chat_model(
            resolved,
            temperature=min(1.0, resolved.temperature + 0.15),
            max_tokens=min(2048, resolved.max_tokens),
        )

        tools = [*ALL_TOOLS, retrieve_knowledge]
        agent = create_react_agent(
            model=execution_llm,
            tools=tools,
            prompt=SYSTEM_PROMPT,
        )

        self._agents[cache_key] = agent
        self._planner_llms[cache_key] = planner_llm

        logger.info(
            "Agent initialized provider=%s model=%s reasoning=%s",
            resolved.provider,
            resolved.model,
            resolved.reasoning_mode,
        )

        return cache_key, effective_runtime

    def invoke(
        self,
        messages: list[dict[str, Any]],
        config: dict[str, Any] | None = None,
        runtime_config: RuntimeModelConfig | None = None,
    ) -> dict[str, Any]:
        """Run the agent synchronously."""
        cache_key, _ = self._ensure_initialized(runtime_config)
        agent = self._agents.get(cache_key)
        if agent is None:
            raise RuntimeError("Agent not initialized")

        lc_messages = self._convert_to_lc_messages(messages)

        run_config: RunnableConfig = {
            "recursion_limit": agent_settings.AGENT_MAX_ITERATIONS * 2 + 1,
            **(config or {}),
        }

        return agent.invoke({"messages": lc_messages}, config=run_config)

    def _convert_to_lc_messages(
        self, messages: list[dict[str, Any]]
    ) -> list[BaseMessage]:
        """Convert dict messages to LangChain message objects."""
        lc_messages: list[BaseMessage] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            elif role == "system":
                lc_messages.append(SystemMessage(content=content))
        return lc_messages

    def _should_decompose(self, messages: list[BaseMessage]) -> bool:
        """Detect complex prompts that benefit from DAG planning."""
        user_message = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_message = str(msg.content).lower()
                break

        if not user_message:
            return False

        simple_keywords = ["hello", "hi", "สวัสดี", "help", "what can you do"]
        if any(keyword in user_message for keyword in simple_keywords):
            return False

        complexity_markers = [
            "compare",
            "vs",
            "versus",
            "undervalued",
            "portfolio",
            "recommend",
            "optimize",
            "tradeoff",
            "analysis",
            "เปรียบเทียบ",
            "วิเคราะห์",
        ]
        return any(marker in user_message for marker in complexity_markers)

    def _extract_chunk_content(self, chunk: Any) -> str:
        """Normalize streamed chunk content across providers."""
        content = getattr(chunk, "content", "")
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            texts: list[str] = []
            for part in content:
                if isinstance(part, str):
                    texts.append(part)
                elif isinstance(part, dict):
                    maybe_text = part.get("text")
                    if isinstance(maybe_text, str):
                        texts.append(maybe_text)
            return "".join(texts)

        return str(content) if content else ""

    def _compute_recursion_limit(self) -> int:
        """
        Compute a robust LangGraph recursion budget.

        A single tool iteration often includes multiple internal graph hops
        (model planning, tool routing, tool execution, post-tool synthesis),
        so a low multiple can trip false-positive recursion failures on
        legitimate complex tasks.
        """
        max_iterations = max(1, agent_settings.AGENT_MAX_ITERATIONS)
        return max(25, max_iterations * 6 + 5)

    async def astream(
        self,
        messages: list[dict[str, Any]],
        config: dict[str, Any] | None = None,
        runtime_config: RuntimeModelConfig | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Stream agent execution events with decomposition + clarification loop.

        Event types:
        - decomposition: Structured DAG for complex tasks
        - clarification: Missing constraints/questions to ask user
        - tool_call: Tool invocation metadata
        - tool_result: Tool output (truncated)
        - token: Streaming output token
        - final: Final fallback text
        - error: Execution error
        """
        cache_key, _ = self._ensure_initialized(runtime_config)
        agent = self._agents.get(cache_key)
        planner_llm = self._planner_llms.get(cache_key)
        if agent is None:
            raise RuntimeError("Agent not initialized")

        lc_messages = self._convert_to_lc_messages(messages)

        if self._should_decompose(lc_messages):
            plan = self._planner.build_plan(lc_messages, planner_llm)
            plan_data = plan.model_dump()

            yield {
                "type": "decomposition",
                "content": plan_data,
            }

            if plan.requires_clarification:
                yield {
                    "type": "clarification",
                    "content": {
                        "questions": plan.clarification_questions,
                        "missing_constraints": plan.missing_constraints,
                        "message": build_clarification_message(plan),
                    },
                }
                return

            if plan.nodes and lc_messages:
                dag_context = HumanMessage(
                    content=(
                        "[TASK DAG]\n"
                        f"{json.dumps(plan_data, ensure_ascii=False)}\n\n"
                        "[USER QUERY]\n"
                        f"{lc_messages[-1].content}"
                    )
                )
                lc_messages = lc_messages[:-1] + [dag_context]

        run_config: RunnableConfig = {
            "recursion_limit": self._compute_recursion_limit(),
            **(config or {}),
        }

        iteration = 0
        max_iterations = max(1, agent_settings.AGENT_MAX_ITERATIONS)
        tool_call_budget = max_iterations * 3

        try:
            async for event in agent.astream_events(
                {"messages": lc_messages},
                config=run_config,
                version="v2",
            ):
                event_type = event.get("event", "")
                event_name = event.get("name", "")
                data = event.get("data", {})

                if event_type == "on_chain_start" and event_name == "tools":
                    iteration += 1
                    if iteration > tool_call_budget:
                        yield {
                            "type": "error",
                            "content": (
                                f"Tool-call safety budget reached ({tool_call_budget}). "
                                "Stopping to avoid a potential loop."
                            ),
                        }
                        break

                if event_type == "on_tool_start":
                    tool_name = event_name
                    tool_input = data.get("input", {})
                    if isinstance(tool_input, str):
                        try:
                            tool_input = json.loads(tool_input)
                        except json.JSONDecodeError:
                            tool_input = {"raw_input": tool_input}

                    yield {
                        "type": "tool_call",
                        "content": {
                            "name": tool_name,
                            "input": tool_input,
                        },
                    }

                elif event_type == "on_tool_end":
                    tool_output = data.get("output", "")
                    output_str = str(tool_output)
                    if len(output_str) > 2000:
                        output_str = output_str[:2000] + "... (truncated)"

                    yield {
                        "type": "tool_result",
                        "content": output_str,
                    }

                elif event_type == "on_chat_model_stream":
                    chunk = data.get("chunk")
                    if chunk:
                        token_content = self._extract_chunk_content(chunk)
                        if token_content:
                            yield {
                                "type": "token",
                                "content": token_content,
                            }

                elif event_type == "on_chain_end" and event_name == "LangGraph":
                    output = data.get("output", {})
                    if isinstance(output, dict):
                        output_messages = output.get("messages", [])
                        if output_messages:
                            last_message = output_messages[-1]
                            if hasattr(last_message, "content") and last_message.content:
                                yield {
                                    "type": "final",
                                    "content": str(last_message.content),
                                }

        except GraphRecursionError:
            recursion_limit = run_config.get("recursion_limit")
            logger.error(
                "Agent streaming hit GraphRecursionError (limit=%s).",
                recursion_limit,
                exc_info=True,
            )
            yield {
                "type": "error",
                "content": (
                    "Execution exceeded the graph recursion budget before completion. "
                    f"Current limit: {recursion_limit}. "
                    "Try simplifying the request or increase AGENT_MAX_ITERATIONS."
                ),
            }
        except Exception as e:
            logger.error("Agent streaming error: %s", e, exc_info=True)
            yield {
                "type": "error",
                "content": str(e),
            }

    async def astream_text(
        self,
        messages: list[dict[str, Any]],
        include_tool_info: bool = False,
        runtime_config: RuntimeModelConfig | None = None,
    ) -> AsyncIterator[str]:
        """Stream text-only output for simple SSE consumers."""
        final_content = ""
        tokens_streamed = False

        async for event in self.astream(messages, runtime_config=runtime_config):
            event_type = event.get("type", "")
            content = event.get("content", "")

            if event_type == "token":
                tokens_streamed = True
                yield str(content)
            elif event_type == "tool_call" and include_tool_info:
                tool_info = cast(dict[str, Any], content)
                name = tool_info.get("name", "unknown")
                yield f"\n[Calling tool: {name}...]\n"
            elif event_type == "tool_result" and include_tool_info:
                yield "\n[Tool completed]\n"
            elif event_type == "final":
                final_content = str(content)
            elif event_type == "clarification":
                details = cast(dict[str, Any], content)
                yield str(details.get("message", "Please provide clarification."))
            elif event_type == "error":
                yield f"\n[Error: {content}]\n"

        if not tokens_streamed and final_content:
            yield final_content


agent_service = AgentService()
