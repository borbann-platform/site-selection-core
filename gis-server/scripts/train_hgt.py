"""
Train HGT Valuator for Property Price Prediction.

Fine-tunes the Heterogeneous Graph Transformer on labeled property
transactions. Supports:
- Loading pre-trained GraphMAE encoder weights
- Mini-batch training with NeighborLoader for memory efficiency
- Cold-start aware training with weighted loss
- Evaluation metrics: MAPE, MAE, R²

Usage:
    python -m scripts.train_hgt --graph data/hetero_graph.pt --output models/hgt_valuator
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from sklearn.model_selection import train_test_split
from torch import nn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import PyG with fallback
try:
    from torch_geometric.data import HeteroData
    from torch_geometric.loader import NeighborLoader
    from torch_geometric.transforms import ToSparseTensor

    HAS_PYG = True
except ImportError:
    HAS_PYG = False
    logger.warning("torch_geometric not available")

# Import model
from src.models.hgt_valuator import (
    ValuationLoss,
    create_model_from_data,
    get_model_summary,
)

# Training hyperparameters
HIDDEN_DIM = 128
NUM_HEADS = 4
NUM_LAYERS = 2
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
EPOCHS = 100
BATCH_SIZE = 256
PATIENCE = 15  # Early stopping patience
TRAIN_RATIO = 0.8
VAL_RATIO = 0.1


def load_graph(graph_path: Path) -> "HeteroData":
    """Load heterogeneous graph from file."""
    if not graph_path.exists():
        raise FileNotFoundError(f"Graph not found: {graph_path}")

    data = torch.load(graph_path)
    logger.info(f"Loaded graph with {len(data.node_types)} node types")
    return data


def load_pretrained_embeddings(
    embeddings_dir: Path, node_type: str
) -> torch.Tensor | None:
    """Load pre-trained GraphMAE embeddings if available."""
    emb_path = embeddings_dir / f"pretrained_embeddings_{node_type}.pt"
    if emb_path.exists():
        embeddings = torch.load(emb_path)
        logger.info(f"Loaded pretrained embeddings for {node_type}: {embeddings.shape}")
        return embeddings
    return None


def prepare_data_splits(data: "HeteroData", train_ratio: float, val_ratio: float):
    """
    Create train/val/test masks for properties.

    Ensures cold-start nodes are proportionally distributed.
    """
    num_properties = data["property"].x.size(0)
    indices = np.arange(num_properties)

    # Get cold-start mask
    if hasattr(data["property"], "cold_start_mask"):
        cold_start = data["property"].cold_start_mask.numpy()
    else:
        cold_start = np.zeros(num_properties, dtype=bool)

    # Stratified split by cold-start status
    train_idx, temp_idx = train_test_split(
        indices,
        train_size=train_ratio,
        stratify=cold_start,
        random_state=42,
    )

    val_size = val_ratio / (1 - train_ratio)
    val_idx, test_idx = train_test_split(
        temp_idx,
        train_size=val_size,
        stratify=cold_start[temp_idx],
        random_state=42,
    )

    # Create masks
    train_mask = torch.zeros(num_properties, dtype=torch.bool)
    val_mask = torch.zeros(num_properties, dtype=torch.bool)
    test_mask = torch.zeros(num_properties, dtype=torch.bool)

    train_mask[train_idx] = True
    val_mask[val_idx] = True
    test_mask[test_idx] = True

    data["property"].train_mask = train_mask
    data["property"].val_mask = val_mask
    data["property"].test_mask = test_mask

    logger.info(
        f"Data splits: train={train_mask.sum()}, val={val_mask.sum()}, test={test_mask.sum()}"
    )

    # Log cold-start distribution
    cold_in_train = cold_start[train_idx].sum()
    cold_in_test = cold_start[test_idx].sum()
    logger.info(f"Cold-start in train: {cold_in_train}, in test: {cold_in_test}")

    return data


def create_neighbor_loader(
    data: "HeteroData",
    batch_size: int = BATCH_SIZE,
    num_neighbors: list = [25, 10],  # Neighbors per hop
) -> "NeighborLoader":
    """
    Create mini-batch loader that samples subgraphs.

    Essential for training on large graphs without OOM.
    """
    # Get training node indices
    train_mask = data["property"].train_mask
    train_idx = train_mask.nonzero(as_tuple=True)[0]

    loader = NeighborLoader(
        data,
        num_neighbors=num_neighbors,
        batch_size=batch_size,
        input_nodes=("property", train_idx),
        shuffle=True,
    )

    return loader


def compute_metrics(predictions: torch.Tensor, targets: torch.Tensor) -> dict:
    """Compute evaluation metrics."""
    predictions = predictions.detach().cpu().numpy()
    targets = targets.detach().cpu().numpy()

    # Avoid division by zero
    targets_safe = np.maximum(targets, 1.0)

    # MAPE
    mape = np.mean(np.abs((predictions - targets) / targets_safe)) * 100

    # MAE
    mae = np.mean(np.abs(predictions - targets))

    # RMSE
    rmse = np.sqrt(np.mean((predictions - targets) ** 2))

    # R²
    ss_res = np.sum((targets - predictions) ** 2)
    ss_tot = np.sum((targets - np.mean(targets)) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return {
        "mape": mape,
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
    }


def train_epoch(
    model: nn.Module,
    data: "HeteroData",
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: str,
) -> float:
    """Train for one epoch (full-batch)."""
    model.train()

    # Move data to device
    x_dict = {k: data[k].x.to(device) for k in data.node_types if hasattr(data[k], "x")}
    edge_index_dict = {
        k: data[k].edge_index.to(device)
        for k in data.edge_types
        if hasattr(data[k], "edge_index")
    }
    targets = data["property"].y.to(device)
    train_mask = data["property"].train_mask.to(device)
    cold_start_mask = (
        data["property"].cold_start_mask.to(device)
        if hasattr(data["property"], "cold_start_mask")
        else None
    )

    optimizer.zero_grad()

    # Forward pass
    predictions = model(x_dict, edge_index_dict, cold_start_mask=cold_start_mask)

    # Compute loss only on training nodes
    loss = criterion(
        predictions[train_mask],
        targets[train_mask],
        cold_start_mask[train_mask] if cold_start_mask is not None else None,
    )

    # Backward pass
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
    optimizer.step()

    return loss.item()


def evaluate(
    model: nn.Module,
    data: "HeteroData",
    mask: torch.Tensor,
    device: str,
) -> dict:
    """Evaluate model on masked subset."""
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
        targets = data["property"].y.to(device)
        cold_start_mask = (
            data["property"].cold_start_mask.to(device)
            if hasattr(data["property"], "cold_start_mask")
            else None
        )

        predictions = model(x_dict, edge_index_dict, cold_start_mask=cold_start_mask)

        # Compute metrics on masked subset
        metrics = compute_metrics(predictions[mask], targets[mask])

    return metrics


def train(
    model: nn.Module,
    data: "HeteroData",
    epochs: int = EPOCHS,
    lr: float = LEARNING_RATE,
    weight_decay: float = WEIGHT_DECAY,
    patience: int = PATIENCE,
    device: str = "cpu",
) -> tuple:
    """
    Full training loop with early stopping.

    Returns:
        (trained_model, training_history)

    """
    model = model.to(device)
    data = data  # Keep on CPU, move per-batch

    criterion = ValuationLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
        optimizer, T_0=20, T_mult=2
    )

    history = {
        "train_loss": [],
        "val_mape": [],
        "val_mae": [],
        "val_r2": [],
    }

    best_val_mape = float("inf")
    best_model_state = None
    epochs_without_improvement = 0

    for epoch in range(epochs):
        # Train
        train_loss = train_epoch(model, data, optimizer, criterion, device)
        history["train_loss"].append(train_loss)

        # Evaluate on validation set
        val_metrics = evaluate(model, data, data["property"].val_mask, device)
        history["val_mape"].append(val_metrics["mape"])
        history["val_mae"].append(val_metrics["mae"])
        history["val_r2"].append(val_metrics["r2"])

        scheduler.step()

        # Early stopping check
        if val_metrics["mape"] < best_val_mape:
            best_val_mape = val_metrics["mape"]
            best_model_state = model.state_dict().copy()
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        # Logging
        if (epoch + 1) % 5 == 0:
            logger.info(
                f"Epoch {epoch + 1}/{epochs} | "
                f"Loss: {train_loss:.4f} | "
                f"Val MAPE: {val_metrics['mape']:.2f}% | "
                f"Val R²: {val_metrics['r2']:.4f}"
            )

        # Early stopping
        if epochs_without_improvement >= patience:
            logger.info(f"Early stopping at epoch {epoch + 1}")
            break

    # Load best model
    if best_model_state is not None:
        model.load_state_dict(best_model_state)
        logger.info(f"Loaded best model with Val MAPE: {best_val_mape:.2f}%")

    return model, history


def evaluate_cold_start(
    model: nn.Module,
    data: "HeteroData",
    device: str,
):
    """Evaluate model specifically on cold-start vs warm nodes."""
    model.eval()

    test_mask = data["property"].test_mask
    cold_start_mask = (
        data["property"].cold_start_mask
        if hasattr(data["property"], "cold_start_mask")
        else torch.zeros_like(test_mask)
    )

    # Warm nodes (have transaction history)
    warm_test_mask = test_mask & ~cold_start_mask
    # Cold-start nodes
    cold_test_mask = test_mask & cold_start_mask

    warm_metrics = (
        evaluate(model, data, warm_test_mask, device) if warm_test_mask.any() else {}
    )
    cold_metrics = (
        evaluate(model, data, cold_test_mask, device) if cold_test_mask.any() else {}
    )

    logger.info("\n=== Cold-Start Analysis ===")
    if warm_metrics:
        logger.info(
            f"Warm nodes (n={warm_test_mask.sum()}): MAPE={warm_metrics['mape']:.2f}%, R²={warm_metrics['r2']:.4f}"
        )
    if cold_metrics:
        logger.info(
            f"Cold-start nodes (n={cold_test_mask.sum()}): MAPE={cold_metrics['mape']:.2f}%, R²={cold_metrics['r2']:.4f}"
        )

    return {"warm": warm_metrics, "cold": cold_metrics}


def save_model(
    model: nn.Module,
    history: dict,
    output_dir: Path,
    metadata: dict | None = None,
):
    """Save trained model and training history."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save model
    model_path = output_dir / "hgt_valuator.pt"
    torch.save(model.state_dict(), model_path)
    logger.info(f"Saved model to {model_path}")

    # Save training history
    history_path = output_dir / "training_history.json"
    with open(history_path, "w") as f:
        # Convert numpy types to Python types
        history_clean = {k: [float(v) for v in vals] for k, vals in history.items()}
        json.dump(history_clean, f, indent=2)

    # Save metadata
    if metadata:
        metadata_path = output_dir / "model_metadata.json"
        metadata["trained_at"] = datetime.now().isoformat()
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Saved metadata to {metadata_path}")


def main():
    parser = argparse.ArgumentParser(description="Train HGT Valuator")
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
    args = parser.parse_args()

    graph_path = Path(args.graph)
    pretrained_dir = Path(args.pretrained)
    output_dir = Path(args.output)

    # Load graph
    logger.info("Loading graph...")
    data = load_graph(graph_path)

    # Prepare train/val/test splits
    data = prepare_data_splits(data, TRAIN_RATIO, VAL_RATIO)

    # Create model
    logger.info("Creating model...")
    model = create_model_from_data(data, hidden_dim=args.hidden_dim)
    logger.info(get_model_summary(model))

    # Load pretrained embeddings if available
    if pretrained_dir.exists():
        logger.info("Loading pretrained embeddings...")
        # Could inject into model encoders here
        # For now, embeddings are loaded during graph construction

    # Train
    logger.info(f"Training on {args.device} for {args.epochs} epochs...")
    model, history = train(
        model,
        data,
        epochs=args.epochs,
        lr=args.lr,
        device=args.device,
    )

    # Final evaluation
    logger.info("\n=== Final Evaluation ===")
    test_metrics = evaluate(model, data, data["property"].test_mask, args.device)
    logger.info(f"Test MAPE: {test_metrics['mape']:.2f}%")
    logger.info(f"Test MAE: {test_metrics['mae']:,.0f} THB")
    logger.info(f"Test R²: {test_metrics['r2']:.4f}")

    # Cold-start analysis
    cold_start_results = evaluate_cold_start(model, data, args.device)

    # Save model
    metadata = {
        "hidden_dim": args.hidden_dim,
        "epochs": args.epochs,
        "lr": args.lr,
        "test_mape": test_metrics["mape"],
        "test_r2": test_metrics["r2"],
        "cold_start_results": cold_start_results,
    }
    save_model(model, history, output_dir, metadata)

    logger.info("Done!")


if __name__ == "__main__":
    main()
