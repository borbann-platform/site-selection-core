#!/usr/bin/env python3
"""
Train Baseline Model with MLflow Tracking.

Wrapper around train_baseline.py that adds MLflow experiment tracking.
Original training logic remains unchanged.

Usage:
    python -m scripts.train_baseline_mlflow --output models/baseline --use-hex2vec
    python -m scripts.train_baseline_mlflow --experiment my-experiment --run-name lgbm-v2
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

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

# Import original training functions
from scripts.train_baseline import (
    DEFAULT_PARAMS,
    fetch_house_prices,
    get_feature_columns,
    load_flood_risk,
    load_h3_features,
    load_hex2vec_embeddings,
    load_transit_stops,
    prepare_features,
    train_spatial_cv,
    train_linear_cv,
    train_rf_cv,
    train_holdout,
    analyze_shap,
    save_residuals,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Train spatial baseline model with MLflow tracking"
    )
    parser.add_argument(
        "--output", type=str, default="models/baseline", help="Output directory"
    )
    parser.add_argument("--cv-folds", type=int, default=5, help="Number of CV folds")
    parser.add_argument(
        "--use-hex2vec", action="store_true", help="Include Hex2Vec embeddings"
    )
    parser.add_argument(
        "--holdout-only", action="store_true", help="Skip CV, only holdout"
    )
    parser.add_argument(
        "--compare-all",
        action="store_true",
        help="Train and compare all baseline models (Linear, RF, LightGBM, Mean)",
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

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine experiment name
    experiment_name = args.experiment or get_experiment_name("baseline")

    # Prepare run tags
    tags = DEFAULT_TAGS.copy()
    tags["model_type"] = "lightgbm"
    tags["use_hex2vec"] = str(args.use_hex2vec)

    logger.info("=== Spatial Baseline Model Training (with MLflow) ===")
    logger.info(f"Experiment: {experiment_name}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Use Hex2Vec: {args.use_hex2vec}")

    # Start MLflow run
    with mlflow_run(
        experiment_name=experiment_name,
        run_name=args.run_name,
        tracking_uri=args.tracking_uri,
        tags=tags,
    ):
        # Log parameters
        log_params_safe(
            {
                "cv_folds": args.cv_folds,
                "use_hex2vec": args.use_hex2vec,
                "holdout_only": args.holdout_only,
                **DEFAULT_PARAMS,
            }
        )

        # Load data
        logger.info("Loading data...")
        df = fetch_house_prices()
        h3_features = load_h3_features()
        hex2vec = load_hex2vec_embeddings() if args.use_hex2vec else None
        flood_risk = load_flood_risk()
        transit_stops = load_transit_stops()

        # Log dataset info
        set_tag_safe("num_properties", str(len(df)))
        set_tag_safe("num_districts", str(df["district"].nunique()))

        # Prepare features
        df = prepare_features(df, h3_features, hex2vec, flood_risk, transit_stops)
        feature_cols = get_feature_columns(df, use_hex2vec=args.use_hex2vec)

        log_params_safe(
            {
                "num_features": len(feature_cols),
                "num_samples": len(df),
            }
        )

        logger.info(f"\nDataset: {len(df)} properties, {len(feature_cols)} features")
        logger.info(f"Districts: {df['district'].nunique()}")
        logger.info(
            f"Price range: {df['total_price'].min():,.0f} - {df['total_price'].max():,.0f} THB"
        )

        # Train model(s)
        if args.compare_all:
            # Train all 4 baseline models and log each to MLflow
            logger.info("\n" + "=" * 50)
            logger.info("COMPARING ALL BASELINE MODELS")
            logger.info("=" * 50)

            all_metrics = {}

            # 1. Mean Baseline (simple average by district)
            logger.info("\n--- Training Mean Baseline ---")
            import numpy as np
            from sklearn.model_selection import GroupKFold

            X = df[feature_cols].fillna(0).values
            y = df["log_price"].values
            groups = df["district"].values

            gkf = GroupKFold(n_splits=args.cv_folds)
            mean_oof = np.zeros(len(df))
            fold_metrics = []

            for fold, (train_idx, val_idx) in enumerate(gkf.split(X, y, groups)):
                y_train, y_val = y[train_idx], y[val_idx]
                mean_pred = np.mean(y_train)
                mean_oof[val_idx] = mean_pred

                # Compute metrics
                from scripts.train_baseline import compute_metrics

                metrics = compute_metrics(
                    y_val, np.full(len(val_idx), mean_pred), is_log=True
                )
                fold_metrics.append(metrics)

            mean_metrics = {
                "avg": {
                    k: np.mean([m[k] for m in fold_metrics]) for k in fold_metrics[0]
                },
                "std": {
                    k: np.std([m[k] for m in fold_metrics]) for k in fold_metrics[0]
                },
                "folds": fold_metrics,
            }
            all_metrics["mean_baseline"] = mean_metrics

            # Log mean baseline to MLflow
            with mlflow_run(
                experiment_name=experiment_name,
                run_name=f"{args.run_name or 'baseline'}_mean",
                tracking_uri=args.tracking_uri,
                tags={**tags, "model_type": "mean_baseline"},
            ):
                log_params_safe({"model": "mean_baseline", "cv_folds": args.cv_folds})
                log_metrics_safe(
                    {
                        "cv_mape_mean": mean_metrics["avg"]["mape"],
                        "cv_r2_mean": mean_metrics["avg"]["r2"],
                        "cv_mae_mean": mean_metrics["avg"]["mae"],
                    }
                )

            # 2. Linear Regression (Ridge)
            logger.info("\n--- Training Linear Regression (Ridge) ---")
            _, linear_metrics = train_linear_cv(df, feature_cols, n_folds=args.cv_folds)
            all_metrics["linear"] = linear_metrics

            # Log linear to MLflow
            with mlflow_run(
                experiment_name=experiment_name,
                run_name=f"{args.run_name or 'baseline'}_linear",
                tracking_uri=args.tracking_uri,
                tags={**tags, "model_type": "ridge_regression"},
            ):
                log_params_safe(
                    {"model": "ridge", "alpha": 1.0, "cv_folds": args.cv_folds}
                )
                log_metrics_safe(
                    {
                        "cv_mape_mean": linear_metrics["avg"]["mape"],
                        "cv_mape_std": linear_metrics["std"]["mape"],
                        "cv_r2_mean": linear_metrics["avg"]["r2"],
                        "cv_r2_std": linear_metrics["std"]["r2"],
                        "cv_mae_mean": linear_metrics["avg"]["mae"],
                    }
                )

            # 3. Random Forest
            logger.info("\n--- Training Random Forest ---")
            rf_models, _, rf_metrics = train_rf_cv(
                df, feature_cols, n_folds=args.cv_folds
            )
            all_metrics["random_forest"] = rf_metrics

            # Log RF to MLflow
            with mlflow_run(
                experiment_name=experiment_name,
                run_name=f"{args.run_name or 'baseline'}_random_forest",
                tracking_uri=args.tracking_uri,
                tags={**tags, "model_type": "random_forest"},
            ):
                log_params_safe(
                    {
                        "model": "random_forest",
                        "n_estimators": 200,
                        "max_depth": 15,
                        "cv_folds": args.cv_folds,
                    }
                )
                log_metrics_safe(
                    {
                        "cv_mape_mean": rf_metrics["avg"]["mape"],
                        "cv_mape_std": rf_metrics["std"]["mape"],
                        "cv_r2_mean": rf_metrics["avg"]["r2"],
                        "cv_r2_std": rf_metrics["std"]["r2"],
                        "cv_mae_mean": rf_metrics["avg"]["mae"],
                    }
                )
                log_model_safe(
                    rf_models[0], artifact_path="rf_model", model_type="sklearn"
                )

            # 4. LightGBM (main model)
            logger.info("\n--- Training LightGBM ---")
            lgb_models, oof_preds, lgb_metrics = train_spatial_cv(
                df, feature_cols, n_folds=args.cv_folds
            )
            all_metrics["lightgbm"] = lgb_metrics

            # Log LightGBM to MLflow
            with mlflow_run(
                experiment_name=experiment_name,
                run_name=f"{args.run_name or 'baseline'}_lightgbm",
                tracking_uri=args.tracking_uri,
                tags={**tags, "model_type": "lightgbm"},
            ):
                log_params_safe(
                    {
                        "model": "lightgbm",
                        "cv_folds": args.cv_folds,
                        **DEFAULT_PARAMS,
                    }
                )
                log_metrics_safe(
                    {
                        "cv_mape_mean": lgb_metrics["avg"]["mape"],
                        "cv_mape_std": lgb_metrics["std"]["mape"],
                        "cv_r2_mean": lgb_metrics["avg"]["r2"],
                        "cv_r2_std": lgb_metrics["std"]["r2"],
                        "cv_mae_mean": lgb_metrics["avg"]["mae"],
                    }
                )

                # SHAP for LightGBM only
                X = df[feature_cols].fillna(0).values
                analyze_shap(lgb_models[0], X, feature_cols, output_dir)
                log_artifact_safe(
                    output_dir / "shap_importance.csv", get_artifact_path("shap")
                )

                log_model_safe(
                    lgb_models[0], artifact_path="lgbm_model", model_type="sklearn"
                )

            # Save comparison results
            comparison_path = output_dir / "all_models_comparison.json"
            with open(comparison_path, "w") as f:
                json.dump(all_metrics, f, indent=2)

            # Print comparison table
            logger.info("\n" + "=" * 60)
            logger.info("MODEL COMPARISON SUMMARY (Spatial CV)")
            logger.info("=" * 60)
            logger.info(f"{'Model':<20} {'R²':>10} {'MAPE':>10} {'MAE':>12}")
            logger.info("-" * 60)
            for model_name, metrics in all_metrics.items():
                avg = metrics["avg"]
                std = metrics["std"]
                logger.info(
                    f"{model_name:<20} "
                    f"{avg['r2']:.4f}±{std['r2']:.3f} "
                    f"{avg['mape']:.1f}%±{std['mape']:.1f}% "
                    f"{avg['mae']:>10,.0f}"
                )
            logger.info("-" * 60)

            best_model = lgb_models[0]
            save_residuals(df, oof_preds, output_dir)

        elif not args.holdout_only:
            models, oof_preds, cv_metrics = train_spatial_cv(
                df, feature_cols, n_folds=args.cv_folds
            )

            # Log CV metrics
            log_metrics_safe(
                {
                    "cv_mape_mean": cv_metrics["avg"]["mape"],
                    "cv_mape_std": cv_metrics["std"]["mape"],
                    "cv_mae_mean": cv_metrics["avg"]["mae"],
                    "cv_mae_std": cv_metrics["std"]["mae"],
                    "cv_rmse_mean": cv_metrics["avg"]["rmse"],
                    "cv_rmse_std": cv_metrics["std"]["rmse"],
                    "cv_r2_mean": cv_metrics["avg"]["r2"],
                    "cv_r2_std": cv_metrics["std"]["r2"],
                }
            )

            # Save CV results
            cv_metrics_path = output_dir / "cv_metrics.json"
            with open(cv_metrics_path, "w") as f:
                json.dump(cv_metrics, f, indent=2)
            log_artifact_safe(cv_metrics_path, get_artifact_path("metrics"))

            best_model = models[0]
            save_residuals(df, oof_preds, output_dir)
        else:
            best_model, holdout_metrics = train_holdout(df, feature_cols)

            # Log holdout metrics
            log_metrics_safe(
                {
                    "holdout_mape": holdout_metrics["mape"],
                    "holdout_mae": holdout_metrics["mae"],
                    "holdout_rmse": holdout_metrics["rmse"],
                    "holdout_r2": holdout_metrics["r2"],
                }
            )

            holdout_path = output_dir / "holdout_metrics.json"
            with open(holdout_path, "w") as f:
                json.dump(holdout_metrics, f, indent=2)
            log_artifact_safe(holdout_path, get_artifact_path("metrics"))

        # SHAP analysis
        X = df[feature_cols].fillna(0).values
        analyze_shap(best_model, X, feature_cols, output_dir)
        log_artifact_safe(output_dir / "shap_importance.csv", get_artifact_path("shap"))

        # Save and log model
        model_path = output_dir / "lgbm_model.txt"
        best_model.booster_.save_model(str(model_path))
        log_artifact_safe(model_path, get_artifact_path("model"))

        # Also log model using MLflow's model logging
        log_model_safe(
            best_model,
            artifact_path="lgbm_model",
            model_type="sklearn",
        )

        # Save feature list
        features_path = output_dir / "features.json"
        with open(features_path, "w") as f:
            json.dump(feature_cols, f, indent=2)
        log_artifact_safe(features_path, get_artifact_path("config"))

        # Log predictions if available
        predictions_path = output_dir / "predictions.parquet"
        if predictions_path.exists():
            log_artifact_safe(predictions_path, get_artifact_path("predictions"))

        logger.info("\n=== Training Complete ===")
        logger.info(f"Model and artifacts saved to: {output_dir}")
        logger.info("Run logged to MLflow experiment")


if __name__ == "__main__":
    main()
