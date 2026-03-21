"""Validate golden-set quality report against minimum gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Check agent quality gate")
    parser.add_argument(
        "--report",
        default="gis-server/reports/agent_orchestration_quality.json",
    )
    parser.add_argument("--min-median-score", type=float, default=7.0)
    parser.add_argument("--require-tool-first", action="store_true")
    parser.add_argument("--require-engine-kind")
    args = parser.parse_args()

    report_path = Path(args.report)
    if not report_path.exists():
        raise SystemExit(f"Report not found: {report_path}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    cases = report.get("cases", [])
    if not cases:
        raise SystemExit("No cases found in quality report")

    failed: list[str] = []
    scores: list[float] = []

    for case in cases:
        status_code = int(case.get("status_code", 0))
        if status_code != 200:
            failed.append(f"case {case.get('id')}: status_code={status_code}")

        judge = case.get("judge") or {}
        score = judge.get("score")
        if isinstance(score, (int, float)):
            scores.append(float(score))

        if args.require_tool_first and case.get("has_tool_call") is False:
            failed.append(f"case {case.get('id')}: missing tool call")

        if args.require_engine_kind:
            engine = case.get("engine") or {}
            if engine.get("kind") != args.require_engine_kind:
                failed.append(
                    f"case {case.get('id')}: engine.kind={engine.get('kind')}"
                )

    if scores:
        scores_sorted = sorted(scores)
        mid = len(scores_sorted) // 2
        if len(scores_sorted) % 2 == 0:
            median_score = (scores_sorted[mid - 1] + scores_sorted[mid]) / 2
        else:
            median_score = scores_sorted[mid]
        if median_score < args.min_median_score:
            failed.append(
                f"median score {median_score:.2f} < {args.min_median_score:.2f}"
            )

    if failed:
        details = "\n".join(failed)
        raise SystemExit(f"Quality gate failed:\n{details}")

    print("Quality gate passed")


if __name__ == "__main__":
    main()
