#!/usr/bin/env python3
"""
Strict auto-gated model promotion for MLflow Model Registry.

Usage:
    python -m scripts.promote_model --run-id <RUN_ID> --model-family baseline
    python -m scripts.promote_model --run-id <RUN_ID> --model-family hgt --alias champion
"""

from __future__ import annotations

import argparse
import json
import operator
import sys
import time
from pathlib import Path

import mlflow
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

# Add project root to import path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.mlflow_config import MLFLOW_REGISTRY_URI, MLFLOW_TRACKING_URI


OPERATOR_MAP = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
}

DEFAULT_THRESHOLDS_PATH = (
    Path(__file__).parent.parent / "config" / "mlops_thresholds.json"
)


def load_thresholds(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Threshold config not found: {path}")
    with open(path) as f:
        return json.load(f)


def evaluate_gate(metrics: dict, rules: dict) -> tuple[bool, list[str]]:
    failures: list[str] = []

    for metric_name, condition in rules.items():
        op = condition["op"]
        threshold = float(condition["value"])
        metric_value = metrics.get(metric_name)

        if metric_value is None:
            failures.append(
                f"missing metric '{metric_name}' (required {op} {threshold})"
            )
            continue

        comparator = OPERATOR_MAP.get(op)
        if comparator is None:
            failures.append(f"unsupported operator '{op}' for metric '{metric_name}'")
            continue

        if not comparator(float(metric_value), threshold):
            failures.append(
                f"{metric_name}={metric_value:.6f} failed gate ({metric_name} {op} {threshold})"
            )

    return len(failures) == 0, failures


def ensure_registered_model(client: MlflowClient, model_name: str) -> None:
    try:
        client.get_registered_model(model_name)
    except MlflowException:
        client.create_registered_model(model_name)


def wait_until_ready(
    client: MlflowClient, model_name: str, version: str, timeout_seconds: int
) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        model_version = client.get_model_version(model_name, version)
        status = model_version.status
        if status == "READY":
            return
        if status == "FAILED_REGISTRATION":
            raise RuntimeError(
                f"Model registration failed for {model_name} v{version}: "
                f"{model_version.status_message}"
            )
        time.sleep(2)

    raise TimeoutError(
        f"Timed out waiting for model {model_name} v{version} to become READY"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote a model run to MLflow registry with strict metric gates"
    )
    parser.add_argument("--run-id", required=True, help="MLflow run ID to evaluate")
    parser.add_argument(
        "--model-family",
        required=True,
        choices=["baseline", "hgt"],
        help="Model family gate profile",
    )
    parser.add_argument(
        "--alias",
        default="champion",
        help="Registry alias to update when gate passes",
    )
    parser.add_argument(
        "--thresholds-path",
        default=str(DEFAULT_THRESHOLDS_PATH),
        help="Path to threshold JSON config",
    )
    parser.add_argument(
        "--tracking-uri",
        default=MLFLOW_TRACKING_URI,
        help="MLflow tracking URI",
    )
    parser.add_argument(
        "--registry-uri",
        default=MLFLOW_REGISTRY_URI,
        help="MLflow registry URI",
    )
    parser.add_argument(
        "--wait-timeout-seconds",
        type=int,
        default=120,
        help="Timeout waiting for model version registration",
    )
    args = parser.parse_args()

    thresholds = load_thresholds(Path(args.thresholds_path))
    family_config = thresholds.get(args.model_family)
    if not family_config:
        raise ValueError(
            f"No threshold profile for model family '{args.model_family}' in {args.thresholds_path}"
        )

    mlflow.set_tracking_uri(args.tracking_uri)
    mlflow.set_registry_uri(args.registry_uri)
    client = MlflowClient(
        tracking_uri=args.tracking_uri, registry_uri=args.registry_uri
    )

    run = client.get_run(args.run_id)
    metrics = run.data.metrics
    required_metrics = family_config["required_metrics"]
    passed, failures = evaluate_gate(metrics, required_metrics)

    if not passed:
        print("Gate result: FAILED")
        for item in failures:
            print(f"- {item}")
        client.set_tag(args.run_id, "gate_status", "failed")
        client.set_tag(args.run_id, "gate_model_family", args.model_family)
        return 2

    model_name = family_config["registered_model_name"]
    artifact_path = family_config["artifact_path"]
    source_uri = f"runs:/{args.run_id}/{artifact_path}"

    ensure_registered_model(client, model_name)

    model_version = mlflow.register_model(model_uri=source_uri, name=model_name)
    version = str(model_version.version)
    wait_until_ready(client, model_name, version, args.wait_timeout_seconds)

    client.set_registered_model_alias(model_name, "candidate", version)
    client.set_registered_model_alias(model_name, args.alias, version)
    client.set_model_version_tag(model_name, version, "gate_status", "passed")
    client.set_model_version_tag(model_name, version, "run_id", args.run_id)

    client.set_tag(args.run_id, "gate_status", "passed")
    client.set_tag(args.run_id, "gate_model_family", args.model_family)
    client.set_tag(args.run_id, "registered_model_name", model_name)
    client.set_tag(args.run_id, "registered_model_version", version)

    print("Gate result: PASSED")
    print(f"- registered_model: {model_name}")
    print(f"- version: {version}")
    print(f"- alias_updated: candidate, {args.alias}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
