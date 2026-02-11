"""
MLflow Configuration.

Centralized configuration for MLflow experiment tracking.
Uses local filesystem storage by default.
"""

from __future__ import annotations

import os

# MLflow tracking URI
# Default: local MLflow server from docker-compose (http://localhost:5001)
# Can be overridden with MLFLOW_TRACKING_URI environment variable
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5001")

# Optional registry URI override. If unset, it follows tracking URI.
MLFLOW_REGISTRY_URI = os.getenv("MLFLOW_REGISTRY_URI", MLFLOW_TRACKING_URI)

# Default experiment names
EXPERIMENTS = {
    "baseline": "property-valuation-baseline",
    "hgt": "property-valuation-hgt",
    "hex2vec": "spatial-embeddings-hex2vec",
    "graphmae": "graph-pretraining-graphmae",
}

# Artifact paths within runs
ARTIFACT_PATHS = {
    "model": "model",
    "metrics": "metrics",
    "shap": "shap",
    "predictions": "predictions",
    "config": "config",
}

# Default tags to add to all runs
DEFAULT_TAGS = {
    "project": "site-select-core",
    "domain": "property-valuation",
}


def get_experiment_name(model_type: str) -> str:
    """Get experiment name for a given model type."""
    return EXPERIMENTS.get(model_type, f"property-valuation-{model_type}")


def get_artifact_path(artifact_type: str) -> str:
    """Get artifact path for a given artifact type."""
    return ARTIFACT_PATHS.get(artifact_type, artifact_type)
