"""Compatibility facade exposing the rewritten deterministic workflow agent."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any, cast

from src.config.settings import settings
from src.services.agent_engine import workflow_engine
from src.services.model_provider import RuntimeModelConfig
from src.services.observability import agent_orchestration_metrics

logger = logging.getLogger(__name__)


class AgentService:
    """Compatibility service that keeps the old API while using the new engine."""

    def __init__(self) -> None:
        self._cache_max_entries = settings.AGENT_RUNTIME_CACHE_MAX_ENTRIES

    def get_cache_stats(self) -> dict[str, int | float]:
        return {
            "entries": 0,
            "max_entries": self._cache_max_entries,
            "hits": 0,
            "misses": 0,
            "hit_rate": 0.0,
        }

    def invoke(
        self,
        messages: list[dict[str, Any]],
        config: dict[str, Any] | None = None,
        runtime_config: RuntimeModelConfig | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "Synchronous invoke is not used by the rewritten agent"
        )

    async def astream(
        self,
        messages: list[dict[str, Any]],
        config: dict[str, Any] | None = None,
        runtime_config: RuntimeModelConfig | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        stream_status = "completed"
        try:
            async for event in workflow_engine.astream(
                messages,
                runtime_config=runtime_config,
            ):
                event_type = event.get("type", "")
                if event_type == "tool_call":
                    content = cast(dict[str, Any], event.get("content", {}))
                    agent_orchestration_metrics.observe_tool_call(
                        str(content.get("name", "unknown")),
                        "success",
                        0.0,
                    )
                elif event_type == "clarification":
                    stream_status = "clarification"
                    agent_orchestration_metrics.observe_clarification("workflow")
                yield event
        except Exception as exc:
            stream_status = "error"
            logger.error("Workflow engine error: %s", exc, exc_info=True)
            yield {"type": "error", "content": str(exc)}
        finally:
            agent_orchestration_metrics.observe_stream_completion(stream_status)

    async def astream_text(
        self,
        messages: list[dict[str, Any]],
        include_tool_info: bool = False,
        runtime_config: RuntimeModelConfig | None = None,
    ) -> AsyncIterator[str]:
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
