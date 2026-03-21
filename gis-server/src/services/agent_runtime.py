"""Typed runtime for executing agent tools and collecting evidence."""

from __future__ import annotations

import json
from typing import Any

from src.services.agent_contracts import EvidenceItem, ToolExecutionResult
from src.services.agent_tools import ALL_TOOLS


_TOOLS_BY_NAME = {tool.name: tool for tool in ALL_TOOLS}


class ToolRuntime:
    def execute(
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> ToolExecutionResult:
        tool = _TOOLS_BY_NAME[tool_name]
        raw_output = tool.invoke(tool_input)
        normalized = self._normalize_output(raw_output)
        evidence = self._to_evidence(tool_name, normalized)
        return ToolExecutionResult(
            tool_name=tool_name,
            status="success" if "error" not in normalized else "error",
            tool_input=tool_input,
            raw_output=raw_output,
            normalized_output=normalized,
            evidence_items=evidence,
        )

    def _normalize_output(self, raw_output: Any) -> dict[str, Any]:
        if isinstance(raw_output, dict):
            return raw_output
        if isinstance(raw_output, str):
            try:
                parsed = json.loads(raw_output)
                if isinstance(parsed, dict):
                    return parsed
                return {"data": parsed}
            except json.JSONDecodeError:
                return {"text": raw_output}
        return {"data": raw_output}

    def _to_evidence(
        self, tool_name: str, normalized_output: dict[str, Any]
    ) -> list[EvidenceItem]:
        if "error" in normalized_output:
            return []
        return [
            EvidenceItem(
                kind=f"tool:{tool_name}",
                source_type="tool",
                source_id=tool_name,
                payload=normalized_output,
            )
        ]


tool_runtime = ToolRuntime()
