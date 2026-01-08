#!/usr/bin/env python
"""
Full HGT Training Pipeline.

Runs all steps needed to train the Heterogeneous Graph Transformer model:
1. Build H3 features from database
2. Train Hex2Vec embeddings
3. Build heterogeneous graph
4. (Optional) Pre-train GraphMAE
5. Train HGT valuator

Usage:
    python -m scripts.run_hgt_pipeline
    python -m scripts.run_hgt_pipeline --skip-pretrain  # Skip GraphMAE pre-training
    python -m scripts.run_hgt_pipeline --device cuda    # Use GPU
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_step(name: str, command: list, check: bool = True):
    """Run a pipeline step."""
    logger.info(f"\n{'=' * 60}")
    logger.info(f"STEP: {name}")
    logger.info(f"{'=' * 60}")
    logger.info(f"Command: {' '.join(command)}")

    result = subprocess.run(command, check=False, capture_output=False)

    if check and result.returncode != 0:
        logger.error(f"Step '{name}' failed with code {result.returncode}")
        sys.exit(result.returncode)

    logger.info(f"✓ {name} completed")
    return result


def check_prerequisites():
    """Check that required packages are installed."""
    try:
        import torch

        logger.info(f"PyTorch version: {torch.__version__}")
        logger.info(f"CUDA available: {torch.cuda.is_available()}")
    except ImportError:
        logger.error("PyTorch not installed. Run: pip install torch torch-geometric")
        sys.exit(1)

    try:
        import torch_geometric

        logger.info(f"PyTorch Geometric version: {torch_geometric.__version__}")
    except ImportError:
        logger.error(
            "PyTorch Geometric not installed. Run: pip install torch-geometric"
        )
        sys.exit(1)

    try:
        import gensim

        logger.info(f"Gensim version: {gensim.__version__}")
    except ImportError:
        logger.error("Gensim not installed. Run: pip install gensim")
        sys.exit(1)

    try:
        import h3

        logger.info(f"H3 version: {h3.__version__}")
    except ImportError:
        logger.error("H3 not installed. Run: pip install h3")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Run full HGT training pipeline")
    parser.add_argument(
        "--skip-pretrain",
        action="store_true",
        help="Skip GraphMAE pre-training step",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Device for training (cpu or cuda)",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="Training epochs for HGT",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=9,
        help="H3 resolution (7-11)",
    )
    args = parser.parse_args()

    logger.info("HGT Training Pipeline")
    logger.info("=====================")

    # Check prerequisites
    logger.info("\nChecking prerequisites...")
    check_prerequisites()

    # Define output directories
    data_dir = Path("data")
    h3_features_dir = data_dir / "h3_features"
    models_dir = Path("models")
    hex2vec_dir = models_dir / "hex2vec"
    graphmae_dir = models_dir / "graphmae"
    hgt_dir = models_dir / "hgt_valuator"

    # Step 1: Build H3 Features
    run_step(
        "Build H3 Features",
        [
            sys.executable,
            "-m",
            "scripts.build_h3_features",
            "--output",
            str(h3_features_dir),
            "--resolutions",
            str(args.resolution),
        ],
    )

    # Step 2: Train Hex2Vec
    run_step(
        "Train Hex2Vec Embeddings",
        [
            sys.executable,
            "-m",
            "scripts.train_hex2vec",
            "--input",
            str(h3_features_dir),
            "--output",
            str(hex2vec_dir),
            "--resolution",
            str(args.resolution),
            "--use-spatial",
        ],
    )

    # Step 3: Build Heterogeneous Graph
    run_step(
        "Build Heterogeneous Graph",
        [
            sys.executable,
            "-m",
            "scripts.build_hetero_graph",
            "--features-dir",
            str(h3_features_dir),
            "--models-dir",
            str(hex2vec_dir),
            "--output",
            str(data_dir / "hetero_graph.pt"),
        ],
    )

    # Step 4: (Optional) Pre-train GraphMAE
    if not args.skip_pretrain:
        run_step(
            "Pre-train GraphMAE",
            [
                sys.executable,
                "-m",
                "scripts.pretrain_graphmae",
                "--input",
                str(data_dir / "hetero_graph.pt"),
                "--output",
                str(graphmae_dir),
                "--epochs",
                "50",
                "--device",
                args.device,
            ],
        )
    else:
        logger.info("Skipping GraphMAE pre-training")

    # Step 5: Train HGT Valuator
    pretrained_arg = (
        ["--pretrained", str(graphmae_dir)] if not args.skip_pretrain else []
    )
    run_step(
        "Train HGT Valuator",
        [
            sys.executable,
            "-m",
            "scripts.train_hgt",
            "--graph",
            str(data_dir / "hetero_graph.pt"),
            "--output",
            str(hgt_dir),
            "--epochs",
            str(args.epochs),
            "--device",
            args.device,
            *pretrained_arg,
        ],
    )

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)
    logger.info("\nOutputs:")
    logger.info(f"  - H3 Features: {h3_features_dir}")
    logger.info(f"  - Hex2Vec: {hex2vec_dir}")
    logger.info(f"  - Graph: {data_dir / 'hetero_graph.pt'}")
    if not args.skip_pretrain:
        logger.info(f"  - GraphMAE: {graphmae_dir}")
    logger.info(f"  - HGT Model: {hgt_dir}")
    logger.info("\nTo use the model, start the API server and call:")
    logger.info("  POST /api/v1/hgt-valuation/predict")
    logger.info("  GET /api/v1/hgt-valuation/{property_id}/predict")


if __name__ == "__main__":
    main()
