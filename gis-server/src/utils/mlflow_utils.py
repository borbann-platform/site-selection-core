"""
MLflow Utilities with Graceful Degradation.

Provides wrapper functions for MLflow that work even if MLflow
is not installed or not configured. This allows training scripts
to use MLflow when available without breaking when it's not.

Usage:
    from src.utils.mlflow_utils import mlflow_run, log_params_safe, log_metrics_safe

    with mlflow_run(experiment_name="baseline", run_name="lgbm_v1"):
        log_params_safe({"n_estimators": 1000, "learning_rate": 0.05})
        # ... training code ...
        log_metrics_safe({"mape": 15.5, "r2": 0.85})
"""

from __future__ import annotations

import logging
import os
import subprocess
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Check if MLflow is available
try:
    import mlflow
    from mlflow.models import infer_signature

    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False
    mlflow = None
    infer_signature = None
    logger.info("MLflow not installed. Experiment tracking disabled.")


def is_mlflow_enabled() -> bool:
    """Check if MLflow is available and enabled."""
    return HAS_MLFLOW


def _git_output(args: list[str]) -> str | None:
    """Get git command output, returning None when unavailable."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def build_standard_run_context(
    *,
    model_family: str,
    model_variant: str,
    feature_set: str,
    target: str,
    split_seed: int | None = None,
    dataset_version: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, str]:
    """
    Build a consistent metadata contract for MLflow runs.

    This keeps multi-model experiments queryable and comparable.
    """
    git_sha = _git_output(["rev-parse", "HEAD"]) or "unknown"
    git_branch = _git_output(["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    git_dirty = "false"
    dirty_check = subprocess.run(
        ["git", "diff", "--quiet"],
        capture_output=True,
        check=False,
    )
    if dirty_check.returncode == 1:
        git_dirty = "true"

    context: dict[str, str] = {
        "tracking_schema_version": "1",
        "model_family": model_family,
        "model_variant": model_variant,
        "feature_set": feature_set,
        "target": target,
        "dataset_version": dataset_version or os.getenv("DATASET_VERSION", "unknown"),
        "split_seed": str(split_seed) if split_seed is not None else "unknown",
        "git_sha": git_sha,
        "git_branch": git_branch,
        "git_dirty": git_dirty,
        "train_timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }
    if extra:
        for key, value in extra.items():
            context[key] = str(value)
    return context


def log_standard_run_context(context: dict[str, str]) -> None:
    """Log standardized run context as tags and selected params."""
    for key, value in context.items():
        set_tag_safe(key, value)

    # Keep frequently-filtered metadata in params too.
    param_subset = {
        "meta_model_family": context.get("model_family"),
        "meta_model_variant": context.get("model_variant"),
        "meta_feature_set": context.get("feature_set"),
        "meta_target": context.get("target"),
        "meta_dataset_version": context.get("dataset_version"),
        "meta_split_seed": context.get("split_seed"),
    }
    log_params_safe({k: v for k, v in param_subset.items() if v is not None})


@contextmanager
def mlflow_run(
    experiment_name: str = "default",
    run_name: str | None = None,
    tracking_uri: str | None = None,
    tags: dict[str, str] | None = None,
    nested: bool = False,
):
    """
    Context manager for MLflow run with graceful degradation.

    If MLflow is not installed or configured, this is a no-op.

    Args:
        experiment_name: Name of the MLflow experiment
        run_name: Name of this specific run
        tracking_uri: MLflow tracking server URI (defaults to local ./mlruns)
        tags: Optional tags to add to the run

    Yields:
        MLflow run object or None if MLflow is not available

    Example:
        with mlflow_run("my_experiment", "run_v1") as run:
            log_params_safe({"param": "value"})
            # ... training ...
            log_metrics_safe({"metric": 0.95})
    """
    if not HAS_MLFLOW:
        logger.debug("MLflow not available, skipping experiment tracking")
        yield None
        return

    try:
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)
    except Exception as e:
        logger.warning(f"MLflow setup error, continuing without tracking: {e}")
        yield None
        return

    with mlflow.start_run(run_name=run_name, tags=tags, nested=nested) as run:
        logger.info(
            f"Started MLflow run: {run.info.run_id} (experiment: {experiment_name})"
        )
        yield run


def log_params_safe(params: dict[str, Any]) -> None:
    """
    Log parameters to MLflow with graceful degradation.

    Handles nested dicts by flattening keys and converts non-string
    values to strings as required by MLflow.

    Args:
        params: Dictionary of parameters to log
    """
    if not HAS_MLFLOW or mlflow.active_run() is None:
        return

    try:
        # Flatten nested dicts and convert values to strings
        flat_params = {}
        for key, value in params.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    flat_params[f"{key}.{sub_key}"] = str(sub_value)
            else:
                flat_params[key] = value

        mlflow.log_params(flat_params)
        logger.debug(f"Logged {len(flat_params)} params to MLflow")
    except Exception as e:
        logger.warning(f"Failed to log params to MLflow: {e}")


def log_metrics_safe(
    metrics: dict[str, float],
    step: int | None = None,
) -> None:
    """
    Log metrics to MLflow with graceful degradation.

    Args:
        metrics: Dictionary of metrics to log
        step: Optional step number for time-series metrics
    """
    if not HAS_MLFLOW or mlflow.active_run() is None:
        return

    try:
        # Filter out non-numeric values
        clean_metrics = {}
        for key, value in metrics.items():
            if isinstance(value, (int, float)) and not (
                value != value  # NaN check
            ):
                clean_metrics[key] = float(value)
            else:
                logger.debug(f"Skipping non-numeric metric: {key}={value}")

        mlflow.log_metrics(clean_metrics, step=step)
        logger.debug(f"Logged {len(clean_metrics)} metrics to MLflow")
    except Exception as e:
        logger.warning(f"Failed to log metrics to MLflow: {e}")


def log_artifact_safe(
    local_path: str | Path,
    artifact_path: str | None = None,
) -> None:
    """
    Log an artifact (file or directory) to MLflow with graceful degradation.

    Args:
        local_path: Path to the local file or directory
        artifact_path: Optional subdirectory in the artifact store
    """
    if not HAS_MLFLOW or mlflow.active_run() is None:
        return

    try:
        local_path = Path(local_path)
        if not local_path.exists():
            logger.warning(f"Artifact path does not exist: {local_path}")
            return

        if local_path.is_dir():
            mlflow.log_artifacts(str(local_path), artifact_path)
        else:
            mlflow.log_artifact(str(local_path), artifact_path)

        logger.debug(f"Logged artifact: {local_path}")
    except Exception as e:
        logger.warning(f"Failed to log artifact to MLflow: {e}")


def log_model_safe(
    model: Any,
    artifact_path: str,
    model_type: str = "sklearn",
    signature: Any = None,
    input_example: Any = None,
    registered_model_name: str | None = None,
) -> None:
    """
    Log a model to MLflow with graceful degradation.

    Supports sklearn, lightgbm, and pytorch models.

    Args:
        model: The trained model object
        artifact_path: Path within the run's artifact directory
        model_type: Type of model ("sklearn", "lightgbm", "pytorch")
        signature: Optional model signature for input/output schema
        input_example: Optional example input for the model
        registered_model_name: If provided, register the model in the Model Registry
    """
    if not HAS_MLFLOW or mlflow.active_run() is None:
        return

    try:
        if model_type == "sklearn" or model_type == "lightgbm":
            # LightGBM models work with sklearn flavor
            mlflow.sklearn.log_model(
                model,
                artifact_path,
                signature=signature,
                input_example=input_example,
                registered_model_name=registered_model_name,
            )
        elif model_type == "pytorch":
            mlflow.pytorch.log_model(
                model,
                artifact_path,
                signature=signature,
                input_example=input_example,
                registered_model_name=registered_model_name,
            )
        else:
            logger.warning(f"Unknown model type: {model_type}")
            return

        logger.info(f"Logged {model_type} model to MLflow: {artifact_path}")
    except Exception as e:
        logger.warning(f"Failed to log model to MLflow: {e}")


def set_tag_safe(key: str, value: str) -> None:
    """Set a tag on the current run with graceful degradation."""
    if not HAS_MLFLOW or mlflow.active_run() is None:
        return

    try:
        mlflow.set_tag(key, value)
    except Exception as e:
        logger.warning(f"Failed to set tag: {e}")


def get_or_create_experiment(
    experiment_name: str,
    artifact_location: str | None = None,
) -> str | None:
    """
    Get or create an MLflow experiment.

    Args:
        experiment_name: Name of the experiment
        artifact_location: Optional artifact storage location

    Returns:
        Experiment ID or None if MLflow is not available
    """
    if not HAS_MLFLOW:
        return None

    try:
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if experiment is None:
            experiment_id = mlflow.create_experiment(
                experiment_name,
                artifact_location=artifact_location,
            )
            logger.info(f"Created experiment: {experiment_name} (id={experiment_id})")
            return experiment_id
        return experiment.experiment_id
    except Exception as e:
        logger.warning(f"Failed to get/create experiment: {e}")
        return None
