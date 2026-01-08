"""
Evaluate HGT Property Valuation Model.

Comprehensive evaluation including:
- Overall metrics (MAPE, MAE, RMSE, R²)
- Cold-start vs warm node performance
- Per-district analysis
- Price bracket analysis
- Comparison with baseline models
- Visualization outputs

Usage:
    python -m scripts.evaluate_hgt --model models/hgt_valuator --graph data/hetero_graph.pt
"""

import argparse
import json
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from torch_geometric.data import HeteroData

    HAS_PYG = True
except ImportError:
    HAS_PYG = False

from src.models.hgt_valuator import create_model_from_data


def load_model_and_graph(model_dir: Path, graph_path: Path, device: str = "cpu"):
    """Load trained model and graph data."""
    # Load graph
    data = torch.load(graph_path, map_location=device)
    logger.info(f"Loaded graph: {len(data.node_types)} node types")

    # Load model
    model = create_model_from_data(data)
    model_path = model_dir / "hgt_valuator.pt"
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()
    model.to(device)

    # Load metadata
    metadata = {}
    metadata_path = model_dir / "model_metadata.json"
    if metadata_path.exists():
        with open(metadata_path) as f:
            metadata = json.load(f)

    return model, data, metadata


def get_predictions(model, data, device: str = "cpu"):
    """Get predictions for all properties."""
    model.eval()

    with torch.no_grad():
        x_dict = {
            k: data[k].x.to(device) for k in data.node_types if hasattr(data[k], "x")
        }
        edge_index_dict = {
            k: data[k].edge_index.to(device)
            for k in data.edge_types
            if hasattr(data[k], "edge_index")
        }
        cold_start_mask = (
            data["property"].cold_start_mask.to(device)
            if hasattr(data["property"], "cold_start_mask")
            else None
        )

        predictions = model(x_dict, edge_index_dict, cold_start_mask=cold_start_mask)

    return predictions.cpu().numpy(), data["property"].y.numpy()


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Compute comprehensive evaluation metrics."""
    # Avoid division by zero
    y_true_safe = np.maximum(y_true, 1.0)

    mape = np.mean(np.abs((y_true - y_pred) / y_true_safe)) * 100
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)

    # Median absolute percentage error (more robust to outliers)
    medape = np.median(np.abs((y_true - y_pred) / y_true_safe)) * 100

    # Within X% accuracy
    pct_errors = np.abs((y_true - y_pred) / y_true_safe) * 100
    within_10pct = (pct_errors <= 10).mean() * 100
    within_20pct = (pct_errors <= 20).mean() * 100
    within_30pct = (pct_errors <= 30).mean() * 100

    return {
        "mape": mape,
        "medape": medape,
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "within_10pct": within_10pct,
        "within_20pct": within_20pct,
        "within_30pct": within_30pct,
        "n_samples": len(y_true),
    }


def evaluate_by_split(predictions, targets, data) -> dict:
    """Evaluate on train/val/test splits."""
    results = {}

    for split_name in ["train", "val", "test"]:
        mask_attr = f"{split_name}_mask"
        if hasattr(data["property"], mask_attr):
            mask = getattr(data["property"], mask_attr).numpy()
            if mask.any():
                results[split_name] = compute_metrics(targets[mask], predictions[mask])
                logger.info(
                    f"{split_name.upper()}: MAPE={results[split_name]['mape']:.2f}%, R²={results[split_name]['r2']:.4f}"
                )

    return results


def evaluate_cold_start(predictions, targets, data) -> dict:
    """Compare cold-start vs warm node performance."""
    if not hasattr(data["property"], "cold_start_mask"):
        return {}

    cold_start = data["property"].cold_start_mask.numpy()
    test_mask = (
        data["property"].test_mask.numpy()
        if hasattr(data["property"], "test_mask")
        else np.ones(len(targets), dtype=bool)
    )

    warm_mask = test_mask & ~cold_start
    cold_mask = test_mask & cold_start

    results = {}

    if warm_mask.any():
        results["warm"] = compute_metrics(targets[warm_mask], predictions[warm_mask])
        logger.info(
            f"WARM nodes (n={warm_mask.sum()}): MAPE={results['warm']['mape']:.2f}%"
        )

    if cold_mask.any():
        results["cold"] = compute_metrics(targets[cold_mask], predictions[cold_mask])
        logger.info(
            f"COLD-START nodes (n={cold_mask.sum()}): MAPE={results['cold']['mape']:.2f}%"
        )

    return results


def evaluate_by_price_bracket(predictions, targets, data) -> dict:
    """Evaluate performance across price ranges."""
    test_mask = (
        data["property"].test_mask.numpy()
        if hasattr(data["property"], "test_mask")
        else np.ones(len(targets), dtype=bool)
    )

    test_targets = targets[test_mask]
    test_preds = predictions[test_mask]

    # Define price brackets (in THB)
    brackets = [
        ("< 2M", 0, 2_000_000),
        ("2M - 5M", 2_000_000, 5_000_000),
        ("5M - 10M", 5_000_000, 10_000_000),
        ("10M - 20M", 10_000_000, 20_000_000),
        ("> 20M", 20_000_000, float("inf")),
    ]

    results = {}
    for name, low, high in brackets:
        mask = (test_targets >= low) & (test_targets < high)
        if mask.any():
            results[name] = compute_metrics(test_targets[mask], test_preds[mask])
            logger.info(
                f"Price {name} (n={mask.sum()}): MAPE={results[name]['mape']:.2f}%"
            )

    return results


def compare_with_baseline(predictions, targets, data) -> dict:
    """Compare HGT with simple baselines."""
    test_mask = (
        data["property"].test_mask.numpy()
        if hasattr(data["property"], "test_mask")
        else np.ones(len(targets), dtype=bool)
    )
    train_mask = (
        data["property"].train_mask.numpy()
        if hasattr(data["property"], "train_mask")
        else ~test_mask
    )

    test_targets = targets[test_mask]
    test_preds = predictions[test_mask]

    results = {"hgt": compute_metrics(test_targets, test_preds)}

    # Baseline 1: Global mean
    global_mean = targets[train_mask].mean()
    baseline_global = np.full_like(test_targets, global_mean)
    results["global_mean"] = compute_metrics(test_targets, baseline_global)

    # Baseline 2: Median
    global_median = np.median(targets[train_mask])
    baseline_median = np.full_like(test_targets, global_median)
    results["global_median"] = compute_metrics(test_targets, baseline_median)

    logger.info("\n=== Baseline Comparison ===")
    logger.info(
        f"HGT:           MAPE={results['hgt']['mape']:.2f}%, R²={results['hgt']['r2']:.4f}"
    )
    logger.info(
        f"Global Mean:   MAPE={results['global_mean']['mape']:.2f}%, R²={results['global_mean']['r2']:.4f}"
    )
    logger.info(
        f"Global Median: MAPE={results['global_median']['mape']:.2f}%, R²={results['global_median']['r2']:.4f}"
    )

    return results


def plot_predictions(predictions, targets, data, output_dir: Path):
    """Generate evaluation plots."""
    output_dir.mkdir(parents=True, exist_ok=True)

    test_mask = (
        data["property"].test_mask.numpy()
        if hasattr(data["property"], "test_mask")
        else np.ones(len(targets), dtype=bool)
    )
    test_targets = targets[test_mask]
    test_preds = predictions[test_mask]

    # 1. Predicted vs Actual scatter plot
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.scatter(test_targets / 1e6, test_preds / 1e6, alpha=0.5, s=10)
    max_val = max(test_targets.max(), test_preds.max()) / 1e6
    ax.plot([0, max_val], [0, max_val], "r--", label="Perfect prediction")
    ax.set_xlabel("Actual Price (Million THB)")
    ax.set_ylabel("Predicted Price (Million THB)")
    ax.set_title("HGT: Predicted vs Actual Property Prices")
    ax.legend()
    ax.set_xlim(0, max_val * 1.1)
    ax.set_ylim(0, max_val * 1.1)
    plt.savefig(output_dir / "predicted_vs_actual.png", dpi=150, bbox_inches="tight")
    plt.close()

    # 2. Error distribution
    fig, ax = plt.subplots(figsize=(10, 6))
    errors = (test_preds - test_targets) / test_targets * 100
    ax.hist(errors, bins=50, edgecolor="black", alpha=0.7)
    ax.axvline(0, color="red", linestyle="--", label="Zero error")
    ax.set_xlabel("Prediction Error (%)")
    ax.set_ylabel("Frequency")
    ax.set_title("Distribution of Prediction Errors")
    ax.set_xlim(-100, 100)
    plt.savefig(output_dir / "error_distribution.png", dpi=150, bbox_inches="tight")
    plt.close()

    # 3. Cold-start comparison
    if hasattr(data["property"], "cold_start_mask"):
        cold_start = data["property"].cold_start_mask.numpy()[test_mask]

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        for ax, is_cold, title in zip(
            axes, [False, True], ["Warm Nodes", "Cold-Start Nodes"]
        ):
            mask = cold_start == is_cold
            if mask.any():
                ax.scatter(
                    test_targets[mask] / 1e6, test_preds[mask] / 1e6, alpha=0.5, s=10
                )
                max_val = max(test_targets[mask].max(), test_preds[mask].max()) / 1e6
                ax.plot([0, max_val], [0, max_val], "r--")
                ax.set_xlabel("Actual Price (M THB)")
                ax.set_ylabel("Predicted Price (M THB)")
                ax.set_title(f"{title} (n={mask.sum()})")

        plt.tight_layout()
        plt.savefig(
            output_dir / "cold_start_comparison.png", dpi=150, bbox_inches="tight"
        )
        plt.close()

    logger.info(f"Plots saved to {output_dir}")


def generate_report(all_results: dict, output_dir: Path):
    """Generate markdown evaluation report."""
    report = ["# HGT Model Evaluation Report\n"]
    report.append(f"Generated: {pd.Timestamp.now().isoformat()}\n")

    # Overall metrics
    if "splits" in all_results and "test" in all_results["splits"]:
        test = all_results["splits"]["test"]
        report.append("## Overall Test Performance\n")
        report.append("| Metric | Value |\n|--------|-------|\n")
        report.append(f"| MAPE | {test['mape']:.2f}% |\n")
        report.append(f"| MedAPE | {test['medape']:.2f}% |\n")
        report.append(f"| MAE | {test['mae']:,.0f} THB |\n")
        report.append(f"| RMSE | {test['rmse']:,.0f} THB |\n")
        report.append(f"| R² | {test['r2']:.4f} |\n")
        report.append(f"| Within 10% | {test['within_10pct']:.1f}% |\n")
        report.append(f"| Within 20% | {test['within_20pct']:.1f}% |\n")
        report.append(f"| N Samples | {test['n_samples']} |\n\n")

    # Cold-start analysis
    if "cold_start" in all_results:
        report.append("## Cold-Start Analysis\n")
        report.append("| Node Type | MAPE | R² | N |\n|-----------|------|----|-|\n")
        for node_type, metrics in all_results["cold_start"].items():
            report.append(
                f"| {node_type.title()} | {metrics['mape']:.2f}% | {metrics['r2']:.4f} | {metrics['n_samples']} |\n"
            )
        report.append("\n")

    # Price brackets
    if "price_brackets" in all_results:
        report.append("## Performance by Price Bracket\n")
        report.append("| Bracket | MAPE | R² | N |\n|---------|------|----|-|\n")
        for bracket, metrics in all_results["price_brackets"].items():
            report.append(
                f"| {bracket} | {metrics['mape']:.2f}% | {metrics['r2']:.4f} | {metrics['n_samples']} |\n"
            )
        report.append("\n")

    # Baseline comparison
    if "baselines" in all_results:
        report.append("## Baseline Comparison\n")
        report.append("| Model | MAPE | R² |\n|-------|------|----|\n")
        for model_name, metrics in all_results["baselines"].items():
            report.append(
                f"| {model_name} | {metrics['mape']:.2f}% | {metrics['r2']:.4f} |\n"
            )
        report.append("\n")

    # Write report
    report_path = output_dir / "evaluation_report.md"
    with open(report_path, "w") as f:
        f.writelines(report)

    logger.info(f"Report saved to {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate HGT model")
    parser.add_argument(
        "--model",
        type=str,
        default="models/hgt_valuator",
        help="Path to trained model directory",
    )
    parser.add_argument(
        "--graph",
        type=str,
        default="data/hetero_graph.pt",
        help="Path to heterogeneous graph",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="evaluation",
        help="Output directory for plots and report",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Device for inference",
    )
    args = parser.parse_args()

    model_dir = Path(args.model)
    graph_path = Path(args.graph)
    output_dir = Path(args.output)

    if not model_dir.exists():
        logger.error(f"Model not found: {model_dir}")
        logger.info("Train the model first with: python -m scripts.run_hgt_pipeline")
        return

    if not graph_path.exists():
        logger.error(f"Graph not found: {graph_path}")
        return

    # Load model and data
    logger.info("Loading model and graph...")
    model, data, metadata = load_model_and_graph(model_dir, graph_path, args.device)

    # Get predictions
    logger.info("Generating predictions...")
    predictions, targets = get_predictions(model, data, args.device)

    # Run evaluations
    all_results = {"metadata": metadata}

    logger.info("\n=== Split Evaluation ===")
    all_results["splits"] = evaluate_by_split(predictions, targets, data)

    logger.info("\n=== Cold-Start Evaluation ===")
    all_results["cold_start"] = evaluate_cold_start(predictions, targets, data)

    logger.info("\n=== Price Bracket Evaluation ===")
    all_results["price_brackets"] = evaluate_by_price_bracket(
        predictions, targets, data
    )

    logger.info("\n=== Baseline Comparison ===")
    all_results["baselines"] = compare_with_baseline(predictions, targets, data)

    # Generate plots
    logger.info("\nGenerating plots...")
    plot_predictions(predictions, targets, data, output_dir)

    # Generate report
    generate_report(all_results, output_dir)

    # Save raw results
    results_path = output_dir / "evaluation_results.json"
    with open(results_path, "w") as f:
        # Convert numpy types for JSON serialization
        def convert(obj):
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            return obj

        json.dump(convert(all_results), f, indent=2)

    logger.info(f"\nResults saved to {output_dir}")
    logger.info("Done!")


if __name__ == "__main__":
    main()
