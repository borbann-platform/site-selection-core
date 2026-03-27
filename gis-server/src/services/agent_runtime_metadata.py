"""Metadata helpers for identifying the active agent engine revision."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

AGENT_ENGINE_KIND = "workflow_rewrite"


def _metadata_source_files() -> list[Path]:
    src_dir = Path(__file__).resolve().parents[1]
    return [
        src_dir / "services" / "agent_contracts.py",
        src_dir / "services" / "agent_router.py",
        src_dir / "services" / "agent_normalizer.py",
        src_dir / "services" / "agent_workflows.py",
        src_dir / "services" / "agent_composer.py",
        src_dir / "services" / "agent_verifier.py",
        src_dir / "services" / "agent_engine.py",
        src_dir / "services" / "agent_react.py",
        src_dir / "services" / "agent_graph.py",
        src_dir / "routes" / "chat.py",
    ]


@lru_cache(maxsize=1)
def get_agent_engine_metadata() -> dict[str, str]:
    hasher = hashlib.sha1()

    for path in _metadata_source_files():
        if not path.exists():
            continue
        hasher.update(str(path.relative_to(path.parents[2])).encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")

    return {
        "kind": AGENT_ENGINE_KIND,
        "revision": hasher.hexdigest()[:12],
    }
