#!/usr/bin/env python3
"""
Train HGT Valuator with MLflow Tracking.

Wrapper around train_hgt.py that adds MLflow experiment tracking.
Original training logic remains unchanged.

Usage:
    python -m scripts.train_hgt_mlflow --graph data/hetero_graph.pt --output models/hgt
    python -m scripts.train_hgt_mlflow --experiment my-experiment --epochs 200
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import torch

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.mlflow_config import (
    DEFAULT_TAGS,
    MLFLOW_TRACKING_URI,
    get_artifact_path,
    get_experiment_name,
)
from src.utils.mlflow_utils import (
    log_artifact_safe,
    log_metrics_safe,
    log_model_safe,
    log_params_safe,
    mlflow_run,
    set_tag_safe,
)

# Import original training functions and constants
from scripts.train_hgt import (
    HIDDEN_DIM,
    NUM_HEADS,
    NUM_LAYERS,
    LEARNING_RATE,
    WEIGHT_DECAY,
    EPOCHS,
    BATCH_SIZE,
    PATIENCE,
    TRAIN_RATIO,
    VAL_RATIO,
    load_graph,
    prepare_data_splits,
    train,
    evaluate,
    evaluate_cold_start,
)
from src.models.hgt_valuator import create_model_from_data, get_model_summary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Train HGT Valuator with MLflow tracking"
    )
    parser.add_argument(
        "--graph",
        type=str,
        default="data/hetero_graph.pt",
        help="Path to heterogeneous graph",
    )
    parser.add_argument(
        "--pretrained",
        type=str,
        default="models/graphmae",
        help="Path to pretrained GraphMAE embeddings (optional)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="models/hgt_valuator",
        help="Output directory for trained model",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=EPOCHS,
        help="Training epochs",
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=LEARNING_RATE,
        help="Learning rate",
    )
    parser.add_argument(
        "--hidden-dim",
        type=int,
        default=HIDDEN_DIM,
        help="Hidden dimension",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="Device to train on",
    )
    # MLflow-specific arguments
    parser.add_argument(
        "--experiment",
        type=str,
        default=None,
        help="MLflow experiment name (default: auto-generated)",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="MLflow run name",
    )
    parser.add_argument(
        "--tracking-uri",
        type=str,
        default=MLFLOW_TRACKING_URI,
        help="MLflow tracking URI",
    )
    args = parser.parse_args()

    graph_path = Path(args.graph)
    pretrained_dir = Path(args.pretrained)
    output_dir = Path(args.output)

    # Determine experiment name
    experiment_name = args.experiment or get_experiment_name("hgt")

    # Prepare run tags
    tags = DEFAULT_TAGS.copy()
    tags["model_type"] = "hgt"
    tags["device"] = args.device

    logger.info("=== HGT Valuator Training (with MLflow) ===")
    logger.info(f"Experiment: {experiment_name}")
    logger.info(f"Graph: {graph_path}")
    logger.info(f"Output: {output_dir}")

    # Start MLflow run
    with mlflow_run(
        experiment_name=experiment_name,
        run_name=args.run_name,
        tracking_uri=args.tracking_uri,
        tags=tags,
    ):
        # Log hyperparameters
        log_params_safe(
            {
                "epochs": args.epochs,
                "learning_rate": args.lr,
                "hidden_dim": args.hidden_dim,
                "num_heads": NUM_HEADS,
                "num_layers": NUM_LAYERS,
                "weight_decay": WEIGHT_DECAY,
                "batch_size": BATCH_SIZE,
                "patience": PATIENCE,
                "train_ratio": TRAIN_RATIO,
                "val_ratio": VAL_RATIO,
                "device": args.device,
            }
        )

        # Load graph
        logger.info("Loading graph...")
        data = load_graph(graph_path)

        # Log graph info
        set_tag_safe("num_node_types", str(len(data.node_types)))
        set_tag_safe("num_edge_types", str(len(data.edge_types)))
        log_params_safe(
            {
                "num_node_types": len(data.node_types),
                "num_edge_types": len(data.edge_types),
                "num_properties": data["property"].x.size(0),
            }
        )

        # Prepare train/val/test splits
        data = prepare_data_splits(data, TRAIN_RATIO, VAL_RATIO)

        # Create model
        logger.info("Creating model...")
        model = create_model_from_data(data, hidden_dim=args.hidden_dim)
        model_summary = get_model_summary(model)
        logger.info(model_summary)
        set_tag_safe("model_summary", model_summary[:250])  # Truncate for MLflow

        # Train
        logger.info(f"Training on {args.device} for {args.epochs} epochs...")
        model, history = train(
            model,
            data,
            epochs=args.epochs,
            lr=args.lr,
            device=args.device,
        )

        # Log training history
        for epoch, (loss, mape, mae, r2) in enumerate(
            zip(
                history["train_loss"],
                history["val_mape"],
                history["val_mae"],
                history["val_r2"],
            )
        ):
            log_metrics_safe(
                {
                    "train_loss": loss,
                    "val_mape": mape,
                    "val_mae": mae,
                    "val_r2": r2,
                },
                step=epoch,
            )

        # Final evaluation
        logger.info("\n=== Final Evaluation ===")
        test_metrics = evaluate(model, data, data["property"].test_mask, args.device)
        logger.info(f"Test MAPE: {test_metrics['mape']:.2f}%")
        logger.info(f"Test MAE: {test_metrics['mae']:,.0f} THB")
        logger.info(f"Test R²: {test_metrics['r2']:.4f}")

        # Log final test metrics
        log_metrics_safe(
            {
                "test_mape": test_metrics["mape"],
                "test_mae": test_metrics["mae"],
                "test_rmse": test_metrics["rmse"],
                "test_r2": test_metrics["r2"],
            }
        )

        # Cold-start analysis
        cold_start_results = evaluate_cold_start(model, data, args.device)
        if cold_start_results.get("warm"):
            log_metrics_safe(
                {
                    "warm_mape": cold_start_results["warm"]["mape"],
                    "warm_r2": cold_start_results["warm"]["r2"],
                }
            )
        if cold_start_results.get("cold"):
            log_metrics_safe(
                {
                    "cold_mape": cold_start_results["cold"]["mape"],
                    "cold_r2": cold_start_results["cold"]["r2"],
                }
            )

        # Save model and artifacts
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save model weights
        model_path = output_dir / "hgt_valuator.pt"
        torch.save(model.state_dict(), model_path)
        logger.info(f"Saved model to {model_path}")
        log_artifact_safe(model_path, get_artifact_path("model"))

        # Log model using MLflow's pytorch logging
        log_model_safe(model, artifact_path="hgt_model", model_type="pytorch")

        # Save training history
        history_path = output_dir / "training_history.json"
        history_clean = {k: [float(v) for v in vals] for k, vals in history.items()}
        with open(history_path, "w") as f:
            json.dump(history_clean, f, indent=2)
        log_artifact_safe(history_path, get_artifact_path("metrics"))

        # Save metadata
        metadata = {
            "hidden_dim": args.hidden_dim,
            "epochs": args.epochs,
            "lr": args.lr,
            "test_mape": test_metrics["mape"],
            "test_r2": test_metrics["r2"],
            "cold_start_results": cold_start_results,
            "trained_at": datetime.now().isoformat(),
        }
        metadata_path = output_dir / "model_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        log_artifact_safe(metadata_path, get_artifact_path("config"))

        logger.info("\n=== Training Complete ===")
        logger.info(f"Model and artifacts saved to: {output_dir}")
        logger.info("Run logged to MLflow experiment")


if __name__ == "__main__":
    main()
