"""Request normalization for rewritten agent workflows."""

from __future__ import annotations

from typing import Any

from src.services.agent_contracts import NormalizedAgentRequest


def detect_language(text: str) -> str:
    return "th" if any("\u0e00" <= ch <= "\u0e7f" for ch in text) else "en"


def normalize_agent_request(
    messages: list[dict[str, Any]],
    attachments: list[dict[str, Any]] | None = None,
) -> NormalizedAgentRequest:
    recent_messages = [
        {"role": str(m.get("role", "user")), "content": str(m.get("content", ""))}
        for m in messages[-10:]
    ]
    user_query = ""
    for message in reversed(recent_messages):
        if message["role"] == "user":
            user_query = message["content"]
            break

    return NormalizedAgentRequest(
        user_query=user_query,
        language=detect_language(user_query),
        recent_messages=recent_messages,
        attachments=attachments or [],
        raw_messages=messages,
    )
