"""Curated internal knowledge fixtures and deterministic lookup helpers."""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parents[2] / "data" / "internal_knowledge"
_TOKEN_RE = re.compile(r"[\w\u0E00-\u0E7F]+", re.UNICODE)


def _normalize_tokens(text: str) -> set[str]:
    tokens = {token.lower() for token in _TOKEN_RE.findall(text) if token.strip()}
    expanded = set(tokens)
    for token in list(tokens):
        for size in range(2, min(len(token), 12) + 1):
            expanded.add(token[:size])
    return expanded


def _record_text(record: dict[str, Any]) -> str:
    parts: list[str] = []
    for value in record.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, (int, float)):
            parts.append(str(value))
        elif isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif isinstance(value, dict):
            parts.append(json.dumps(value, ensure_ascii=False))
    return " ".join(parts)


@lru_cache(maxsize=1)
def load_internal_knowledge() -> dict[str, list[dict[str, Any]]]:
    datasets: dict[str, list[dict[str, Any]]] = {}
    if not _BASE_DIR.exists():
        logger.warning("Internal knowledge directory missing: %s", _BASE_DIR)
        return datasets

    for path in sorted(_BASE_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                datasets[path.stem] = payload
        except Exception as exc:
            logger.warning("Failed to load internal knowledge file %s: %s", path, exc)
    return datasets


class InternalKnowledgeService:
    def query(
        self,
        query: str,
        domain: str | None = None,
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        datasets = load_internal_knowledge()
        query_tokens = _normalize_tokens(query)
        filters = filters or {}
        domains = [domain] if domain else list(datasets.keys())

        matches: list[dict[str, Any]] = []
        for current_domain in domains:
            records = datasets.get(current_domain, [])
            for record in records:
                if not self._passes_filters(record, filters):
                    continue
                record_tokens = _normalize_tokens(_record_text(record))
                overlap = len(query_tokens & record_tokens)
                if overlap == 0 and query_tokens:
                    continue
                matches.append(
                    {
                        "domain": current_domain,
                        "score": overlap,
                        "record": record,
                    }
                )

        matches.sort(
            key=lambda item: (
                int(item["score"]),
                len(_record_text(item["record"])),
            ),
            reverse=True,
        )
        limited = matches[: max(1, min(limit, 20))]
        return {
            "query": query,
            "domain": domain or "all",
            "count": len(limited),
            "results": limited,
        }

    def _passes_filters(self, record: dict[str, Any], filters: dict[str, Any]) -> bool:
        for key, expected in filters.items():
            value = record.get(key)
            if isinstance(expected, str):
                if isinstance(value, str):
                    if expected.lower() not in value.lower():
                        return False
                elif value != expected:
                    return False
            elif value != expected:
                return False
        return True


internal_knowledge_service = InternalKnowledgeService()
