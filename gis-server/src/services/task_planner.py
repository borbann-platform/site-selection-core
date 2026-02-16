"""
Task decomposition and clarification loop for complex prompts.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict, deque
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ConfigDict, Field

from src.config.agent_settings import agent_settings

logger = logging.getLogger(__name__)


class TaskNode(BaseModel):
    """A single DAG task node."""

    model_config = ConfigDict(extra="ignore")

    id: str
    action: str
    purpose: str
    tool: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class TaskDAG(BaseModel):
    """Structured decomposition output."""

    model_config = ConfigDict(extra="ignore")

    objective: str
    reasoning_summary: str
    nodes: list[TaskNode] = Field(default_factory=list)
    requires_clarification: bool = False
    missing_constraints: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)


DECOMPOSITION_PROMPT = """
You are a task planner for a real-estate ReAct agent.
Return ONLY valid JSON using this schema:
{
  "objective": "string",
  "reasoning_summary": "short summary",
  "requires_clarification": false,
  "missing_constraints": [],
  "clarification_questions": [],
  "nodes": [
    {
      "id": "n1",
      "action": "string",
      "purpose": "string",
      "tool": "search_properties",
      "parameters": {},
      "depends_on": []
    }
  ]
}

Rules:
- Use a DAG (no cycles), and dependencies must reference earlier or existing ids.
- Max {max_nodes} nodes.
- Prefer tools only when necessary.
- If key constraints are missing, set requires_clarification=true and provide concrete questions.
- Keep reasoning_summary concise (<= 40 words).
""".strip()


class TaskPlanner:
    """Builds a DAG and clarification plan before execution."""

    _COORD_RE = re.compile(
        r"(-?\d{1,3}(?:\.\d+)?)\s*[,/ ]\s*(-?\d{1,3}(?:\.\d+)?)"
    )

    def build_plan(
        self,
        messages: list[Any],
        planner_llm: BaseChatModel | None = None,
    ) -> TaskDAG:
        """Create a DAG plan with a clarification decision gate."""
        user_message = self._extract_last_user_message(messages)
        if not user_message:
            return TaskDAG(
                objective="Respond to user request",
                reasoning_summary="No explicit user request found in context.",
                nodes=[],
            )

        heuristic_questions, missing = self._heuristic_clarifications(user_message)
        if agent_settings.AGENT_ENABLE_CLARIFICATION_LOOP and heuristic_questions:
            return TaskDAG(
                objective="Collect missing constraints before execution",
                reasoning_summary="Execution paused because required constraints are missing.",
                requires_clarification=True,
                missing_constraints=missing,
                clarification_questions=heuristic_questions,
                nodes=[],
            )

        llm_plan = self._build_llm_plan(user_message, planner_llm)
        if llm_plan is not None:
            return llm_plan

        return self._fallback_plan(user_message)

    def _extract_last_user_message(self, messages: list[Any]) -> str:
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                content = msg.content
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    joined = []
                    for part in content:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            joined.append(part["text"])
                    return "\n".join(joined)
        return ""

    def _heuristic_clarifications(self, message: str) -> tuple[list[str], list[str]]:
        lowered = message.lower()
        has_spatial_context = "[spatial context from map]" in lowered
        has_coordinates = bool(self._COORD_RE.search(lowered))

        questions: list[str] = []
        missing: list[str] = []

        wants_nearby = any(token in lowered for token in [" near ", " ใกล้", "around ", "within"])
        if wants_nearby and not has_spatial_context and not has_coordinates:
            missing.append("reference_location")
            questions.append(
                "Which exact location should I anchor this search to (district, coordinates, or a pinned map point)?"
            )

        wants_comparison = any(token in lowered for token in ["compare", "เปรียบเทียบ", "versus", "vs"])
        if wants_comparison and not re.search(r"\b(vs|versus)\b", lowered):
            missing.append("comparison_targets")
            questions.append(
                "Which two or more districts/properties should I compare?"
            )

        price_intent = any(token in lowered for token in ["under", "below", "budget", "งบ", "ราคาไม่เกิน"])
        has_budget_number = bool(re.search(r"\d[\d,_.]*\s*(m|million|บาท|thb)?", lowered))
        if price_intent and not has_budget_number:
            missing.append("budget_range")
            questions.append("What price range should I use for this analysis?")

        this_area_intent = any(token in lowered for token in ["this area", "here", "พื้นที่นี้", "จุดนี้"])
        if this_area_intent and not has_spatial_context and not has_coordinates:
            missing.append("ui_grounding_target")
            questions.append(
                "Please pin a location or draw a bounding box so I can ground actions to the intended area."
            )

        # Keep the loop tight: no more than 3 clarifications in one turn.
        if len(questions) > 3:
            questions = questions[:3]
            missing = missing[:3]

        return questions, missing

    def _build_llm_plan(
        self,
        user_message: str,
        planner_llm: BaseChatModel | None,
    ) -> TaskDAG | None:
        if planner_llm is None:
            return None

        prompt = DECOMPOSITION_PROMPT.format(
            max_nodes=agent_settings.AGENT_DECOMPOSITION_MAX_NODES
        )
        llm_messages = [
            HumanMessage(content=prompt),
            HumanMessage(content=f"User query:\n{user_message}"),
        ]

        try:
            response = planner_llm.invoke(llm_messages)
            content = response.content if hasattr(response, "content") else str(response)
            plan = self._extract_json_plan(content)
            if plan is None:
                return None
            validated = TaskDAG.model_validate(plan)
            if not validated.requires_clarification and validated.nodes:
                self._validate_dag(validated.nodes)
            return validated
        except Exception as exc:
            logger.warning("Planner LLM decomposition failed: %s", exc)
            return None

    def _extract_json_plan(self, raw: str) -> dict[str, Any] | None:
        text = raw.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None

        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    def _validate_dag(self, nodes: list[TaskNode]) -> None:
        node_ids = {node.id for node in nodes}
        graph: dict[str, list[str]] = defaultdict(list)
        indegree: dict[str, int] = {node.id: 0 for node in nodes}

        for node in nodes:
            for dep in node.depends_on:
                if dep not in node_ids:
                    raise ValueError(f"Task node '{node.id}' depends on unknown node '{dep}'")
                graph[dep].append(node.id)
                indegree[node.id] += 1

        queue: deque[str] = deque([nid for nid, d in indegree.items() if d == 0])
        visited = 0
        while queue:
            current = queue.popleft()
            visited += 1
            for nxt in graph[current]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)

        if visited != len(nodes):
            raise ValueError("Decomposition plan contains a cycle")

    def _fallback_plan(self, user_message: str) -> TaskDAG:
        lowered = user_message.lower()
        nodes = [
            TaskNode(
                id="n1",
                action="Interpret user intent",
                purpose="Extract concrete constraints for data retrieval.",
            )
        ]

        if any(token in lowered for token in ["compare", "เปรียบเทียบ"]):
            nodes.append(
                TaskNode(
                    id="n2",
                    action="Collect comparable market data",
                    purpose="Gather objective metrics for each comparison target.",
                    tool="get_market_statistics",
                    parameters={},
                    depends_on=["n1"],
                )
            )
        else:
            nodes.append(
                TaskNode(
                    id="n2",
                    action="Retrieve relevant property/location data",
                    purpose="Ground the answer in live tool outputs.",
                    tool="search_properties",
                    parameters={},
                    depends_on=["n1"],
                )
            )

        nodes.append(
            TaskNode(
                id="n3",
                action="Synthesize final response",
                purpose="Combine tool outputs into a user-facing recommendation.",
                depends_on=["n2"],
            )
        )

        return TaskDAG(
            objective="Answer the user's real-estate request",
            reasoning_summary="Using a compact execution DAG because no structured plan was available.",
            nodes=nodes[: agent_settings.AGENT_DECOMPOSITION_MAX_NODES],
        )


def build_clarification_message(plan: TaskDAG) -> str:
    """Render the clarification message returned to the user."""
    if not plan.clarification_questions:
        return "I need a bit more detail before I can run the analysis."

    lines = [
        "I can run this, but I need a few details first:",
    ]
    for idx, question in enumerate(plan.clarification_questions, start=1):
        lines.append(f"{idx}. {question}")
    lines.append("Once you answer these, I will execute the plan.")
    return "\n".join(lines)
