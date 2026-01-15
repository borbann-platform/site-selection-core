"""
Train S2-HGT for Property Price Prediction.

Trains the Semantic-Spatial Heterogeneous Graph Transformer with:
- Phase A: Pre-training via masked attribute prediction (optional)
- Phase B: Fine-tuning on price regression with source token bias

Supports subset training for fast iteration (<1 min per epoch on 5K samples).

Usage:
    # Full training
    python -m scripts.train_s2hgt --graph data/s2_hetero_graph.pt --output models/s2hgt

    # Subset training (fast iteration)
    python -m scripts.train_s2hgt --graph data/s2_hetero_graph_subset.pt --epochs 20

    # With pre-training
    python -m scripts.train_s2hgt --graph data/s2_hetero_graph.pt --pretrain --pretrain-epochs 10
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

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import PyG
try:
    from torch_geometric.data import HeteroData

    HAS_PYG = True
except ImportError:
    HAS_PYG = False
    logger.error("torch_geometric required. Install: uv add torch-geometric")

# Import S2-HGT model
from src.models.s2_hgt import (
    SOURCE_LISTING,
    SOURCE_TREASURY,
    S2HGTLoss,
    create_s2hgt_from_data,
)

# =============================================================================
# Hyperparameters
# =============================================================================
HIDDEN_DIM = 128
NUM_HEADS = 4
NUM_LAYERS = 3
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
EPOCHS = 100
PATIENCE = 15
TRAIN_RATIO = 0.8
VAL_RATIO = 0.1
HUBER_DELTA = 0.5


def load_graph(graph_path: Path) -> "HeteroData":
    """Load heterogeneous graph from file."""
    if not graph_path.exists():
        raise FileNotFoundError(f"Graph not found: {graph_path}")

    data = torch.load(graph_path, weights_only=False)
    logger.info(
        f"Loaded graph: {len(data.node_types)} node types, {len(data.edge_types)} edge types"
    )

    for nt in data.node_types:
        if hasattr(data[nt], "x"):
            logger.info(f"  {nt}: {data[nt].x.shape}")

    return data


def prepare_data_splits(
    data: "HeteroData", train_ratio: float, val_ratio: float
) -> "HeteroData":
    """
    Create train/val/test masks.

    Stratifies by source_type to ensure balanced representation.
    """
    num_properties = data["property"].x.size(0)
    indices = np.arange(num_properties)

    # Get source type for stratification
    if hasattr(data["property"], "source_type"):
        source_type = data["property"].source_type.numpy()
    else:
        # Default: all treasury
        source_type = np.zeros(num_properties, dtype=np.int64)

    # Stratified split
    train_idx, temp_idx = train_test_split(
        indices, train_size=train_ratio, stratify=source_type, random_state=42
    )

    val_size = val_ratio / (1 - train_ratio)
    val_idx, test_idx = train_test_split(
        temp_idx, train_size=val_size, stratify=source_type[temp_idx], random_state=42
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

    # Log source type distribution
    for src in [SOURCE_TREASURY, SOURCE_LISTING]:
        src_mask = source_type == src
        in_train = np.sum(src_mask & train_mask.numpy())
        logger.info(f"  Source {src} in train: {in_train}")

    return data


def compute_metrics(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    price_log_mean: float = None,
    price_log_std: float = None,
) -> dict:
    """
    Compute evaluation metrics.

    If price_log_mean/std provided, denormalizes to compute MAPE on real prices.
    Otherwise computes metrics in normalized space.
    """
    predictions = predictions.detach().cpu().numpy()
    targets = targets.detach().cpu().numpy()

    # Metrics in normalized space (for R², RMSE)
    ss_res = np.sum((targets - predictions) ** 2)
    ss_tot = np.sum((targets - np.mean(targets)) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    rmse = np.sqrt(np.mean((predictions - targets) ** 2))

    # Denormalize for MAPE/MAE on real prices
    if price_log_mean is not None and price_log_std is not None:
        # Inverse: normalized -> log1p -> expm1 -> real price
        pred_log = predictions * price_log_std + price_log_mean
        tgt_log = targets * price_log_std + price_log_mean
        pred_real = np.expm1(pred_log)
        tgt_real = np.expm1(tgt_log)

        tgt_safe = np.maximum(tgt_real, 1.0)
        mape = np.mean(np.abs((pred_real - tgt_real) / tgt_safe)) * 100
        mae = np.mean(np.abs(pred_real - tgt_real))
    else:
        # Fallback: compute on raw values (may be normalized)
        targets_safe = np.maximum(np.abs(targets), 1e-8)
        mape = np.mean(np.abs((predictions - targets) / targets_safe)) * 100
        mae = np.mean(np.abs(predictions - targets))

    return {"mape": mape, "mae": mae, "rmse": rmse, "r2": r2}


def train_epoch(
    model: nn.Module,
    data: "HeteroData",
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: str,
) -> float:
    """Train for one epoch."""
    model.train()

    # Prepare inputs
    x_dict = {k: data[k].x.to(device) for k in data.node_types if hasattr(data[k], "x")}
    edge_index_dict = {
        k: data[k].edge_index.to(device)
        for k in data.edge_types
        if hasattr(data[k], "edge_index")
    }
    edge_attr_dict = {
        k: data[k].edge_attr.to(device)
        for k in data.edge_types
        if hasattr(data[k], "edge_attr")
    }

    targets = data["property"].y.to(device)
    train_mask = data["property"].train_mask.to(device)

    # Source type (if available)
    source_type = (
        data["property"].source_type.to(device)
        if hasattr(data["property"], "source_type")
        else None
    )

    # Coordinates (if available)
    coords_dict = {}
    if hasattr(data["property"], "coords"):
        coords_dict["property"] = data["property"].coords.to(device)
    if "anchor" in data.node_types and hasattr(data["anchor"], "coords"):
        coords_dict["anchor"] = data["anchor"].coords.to(device)

    optimizer.zero_grad()

    # Forward pass
    predictions = model(
        x_dict,
        edge_index_dict,
        edge_attr_dict=edge_attr_dict if edge_attr_dict else None,
        source_type=source_type,
        coords_dict=coords_dict if coords_dict else None,
    )

    # Loss on training nodes
    loss = criterion(
        predictions[train_mask],
        targets[train_mask],
        source_type[train_mask] if source_type is not None else None,
    )

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

    # Get price transform params if available
    price_log_mean = getattr(data, "price_log_mean", None)
    price_log_std = getattr(data, "price_log_std", None)

    with torch.no_grad():
        x_dict = {
            k: data[k].x.to(device) for k in data.node_types if hasattr(data[k], "x")
        }
        edge_index_dict = {
            k: data[k].edge_index.to(device)
            for k in data.edge_types
            if hasattr(data[k], "edge_index")
        }
        edge_attr_dict = {
            k: data[k].edge_attr.to(device)
            for k in data.edge_types
            if hasattr(data[k], "edge_attr")
        }
        targets = data["property"].y.to(device)

        source_type = (
            data["property"].source_type.to(device)
            if hasattr(data["property"], "source_type")
            else None
        )

        coords_dict = {}
        if hasattr(data["property"], "coords"):
            coords_dict["property"] = data["property"].coords.to(device)
        if "anchor" in data.node_types and hasattr(data["anchor"], "coords"):
            coords_dict["anchor"] = data["anchor"].coords.to(device)

        predictions = model(
            x_dict,
            edge_index_dict,
            edge_attr_dict=edge_attr_dict if edge_attr_dict else None,
            source_type=source_type,
            coords_dict=coords_dict if coords_dict else None,
        )

        metrics = compute_metrics(
            predictions[mask], targets[mask], price_log_mean, price_log_std
        )

    return metrics


def evaluate_by_source(
    model: nn.Module,
    data: "HeteroData",
    mask: torch.Tensor,
    device: str,
) -> dict:
    """Evaluate model separately for each source type."""
    model.eval()
    results = {}

    if not hasattr(data["property"], "source_type"):
        return results

    source_type = data["property"].source_type
    price_log_mean = getattr(data, "price_log_mean", None)
    price_log_std = getattr(data, "price_log_std", None)

    with torch.no_grad():
        x_dict = {
            k: data[k].x.to(device) for k in data.node_types if hasattr(data[k], "x")
        }
        edge_index_dict = {
            k: data[k].edge_index.to(device)
            for k in data.edge_types
            if hasattr(data[k], "edge_index")
        }
        edge_attr_dict = {
            k: data[k].edge_attr.to(device)
            for k in data.edge_types
            if hasattr(data[k], "edge_attr")
        }
        targets = data["property"].y.to(device)

        coords_dict = {}
        if hasattr(data["property"], "coords"):
            coords_dict["property"] = data["property"].coords.to(device)
        if "anchor" in data.node_types and hasattr(data["anchor"], "coords"):
            coords_dict["anchor"] = data["anchor"].coords.to(device)

        predictions = model(
            x_dict,
            edge_index_dict,
            edge_attr_dict=edge_attr_dict if edge_attr_dict else None,
            source_type=source_type.to(device),
            coords_dict=coords_dict if coords_dict else None,
        )

        for src, name in [(SOURCE_TREASURY, "treasury"), (SOURCE_LISTING, "listing")]:
            src_mask = (source_type == src) & mask
            if src_mask.sum() > 0:
                results[name] = compute_metrics(
                    predictions[src_mask],
                    targets[src_mask],
                    price_log_mean,
                    price_log_std,
                )

    return results


def pretrain_masked_prediction(
    model: nn.Module,
    data: "HeteroData",
    epochs: int,
    device: str,
    mask_ratio: float = 0.15,
) -> nn.Module:
    """
    Phase A: Pre-training via masked attribute prediction.

    Masks property_type and trains model to predict it from neighbors.
    """
    logger.info(f"Starting pre-training for {epochs} epochs...")

    model = model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

    # Get property type as target
    if not hasattr(data["property"], "property_type"):
        logger.warning("No property_type found; skipping pre-training")
        return model

    property_type = data["property"].property_type.to(device)
    num_classes = int(property_type.max().item()) + 1

    # Add classification head for pre-training
    pretrain_head = nn.Linear(model.hidden_dim, num_classes).to(device)
    criterion = nn.CrossEntropyLoss()

    for epoch in range(epochs):
        model.train()

        # Create random mask
        num_props = data["property"].x.size(0)
        mask = torch.rand(num_props) < mask_ratio
        mask = mask.to(device)

        # Prepare inputs (mask property_type feature)
        x_dict = {
            k: data[k].x.to(device) for k in data.node_types if hasattr(data[k], "x")
        }
        # Zero out property_type feature for masked nodes
        # Assuming property_type_encoded is last feature column
        x_dict["property"] = x_dict["property"].clone()
        x_dict["property"][mask, -1] = 0

        edge_index_dict = {
            k: data[k].edge_index.to(device)
            for k in data.edge_types
            if hasattr(data[k], "edge_index")
        }

        optimizer.zero_grad()

        # Get embeddings (not predictions)
        # Need to access intermediate representation
        h_dict = {}
        for node_type, x in x_dict.items():
            if node_type in model.encoders:
                h_dict[node_type] = model.encoders[node_type](x)

        # Apply HGT layers
        for i, (conv, norm) in enumerate(zip(model.hgt_layers, model.layer_norms)):
            h_dict_new = conv(h_dict, edge_index_dict)
            for node_type in h_dict:
                if node_type in h_dict_new:
                    h_dict[node_type] = norm(h_dict[node_type] + h_dict_new[node_type])

        # Predict property_type for masked nodes
        logits = pretrain_head(h_dict["property"][mask])
        loss = criterion(logits, property_type[mask])

        loss.backward()
        optimizer.step()

        if (epoch + 1) % 5 == 0:
            acc = (logits.argmax(dim=-1) == property_type[mask]).float().mean()
            logger.info(f"Pre-train Epoch {epoch + 1}: loss={loss:.4f}, acc={acc:.2%}")

    logger.info("Pre-training complete")
    return model


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
    Phase B: Fine-tuning on price regression.

    Returns:
        (trained_model, training_history)

    """
    model = model.to(device)

    criterion = S2HGTLoss()  # Log-Cosh loss

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

        # Evaluate
        val_metrics = evaluate(model, data, data["property"].val_mask, device)
        history["val_mape"].append(val_metrics["mape"])
        history["val_mae"].append(val_metrics["mae"])
        history["val_r2"].append(val_metrics["r2"])

        scheduler.step()

        # Early stopping
        if val_metrics["mape"] < best_val_mape:
            best_val_mape = val_metrics["mape"]
            best_model_state = {
                k: v.cpu().clone() for k, v in model.state_dict().items()
            }
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

        if epochs_without_improvement >= patience:
            logger.info(f"Early stopping at epoch {epoch + 1}")
            break

    # Load best model
    if best_model_state is not None:
        model.load_state_dict(best_model_state)
        logger.info(f"Loaded best model with Val MAPE: {best_val_mape:.2f}%")

    return model, history


def save_model(
    model: nn.Module,
    output_dir: Path,
    history: dict,
    data: "HeteroData",
    test_metrics: dict,
):
    """Save trained model and metadata."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save model weights
    model_path = output_dir / "s2hgt_model.pt"
    torch.save(model.state_dict(), model_path)
    logger.info(f"Saved model to {model_path}")

    # Convert metrics to native Python types
    def to_native(obj):
        if hasattr(obj, "item"):
            return obj.item()
        if isinstance(obj, dict):
            return {k: to_native(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [to_native(v) for v in obj]
        return float(obj) if isinstance(obj, (int, float)) else obj

    # Save metadata
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "hidden_dim": model.hidden_dim,
        "num_heads": model.num_heads,
        "num_layers": model.num_layers,
        "node_types": list(data.node_types),
        "edge_types": [str(et) for et in data.edge_types],
        "num_properties": int(data["property"].x.size(0)),
        "price_transform": {
            "log_mean": getattr(data, "price_log_mean", None),
            "log_std": getattr(data, "price_log_std", None),
            "raw_mean": getattr(data, "price_raw_mean", None),
            "raw_std": getattr(data, "price_raw_std", None),
        },
        "test_metrics": to_native(test_metrics),
        "training_history": {
            k: [float(v) for v in vals] for k, vals in history.items()
        },
    }

    metadata_path = output_dir / "s2hgt_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Saved metadata to {metadata_path}")


def main():
    parser = argparse.ArgumentParser(description="Train S2-HGT model")
    parser.add_argument(
        "--graph",
        type=Path,
        default=Path("data/s2_hetero_graph.pt"),
        help="Input graph file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("models/s2hgt"),
        help="Output directory for trained model",
    )
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--lr", type=float, default=LEARNING_RATE)
    parser.add_argument("--hidden-dim", type=int, default=HIDDEN_DIM)
    parser.add_argument("--patience", type=int, default=PATIENCE)
    parser.add_argument(
        "--pretrain", action="store_true", help="Run Phase A pre-training"
    )
    parser.add_argument("--pretrain-epochs", type=int, default=10)
    parser.add_argument(
        "--device",
        type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
    )
    args = parser.parse_args()

    logger.info(f"Device: {args.device}")

    # Load graph
    data = load_graph(args.graph)
    data = prepare_data_splits(data, TRAIN_RATIO, VAL_RATIO)

    # Create model
    model = create_s2hgt_from_data(data, hidden_dim=args.hidden_dim)
    total_params = sum(p.numel() for p in model.parameters())
    logger.info(f"Model parameters: {total_params:,}")

    # Phase A: Pre-training (optional)
    if args.pretrain:
        model = pretrain_masked_prediction(
            model, data, epochs=args.pretrain_epochs, device=args.device
        )

    # Phase B: Fine-tuning
    model, history = train(
        model,
        data,
        epochs=args.epochs,
        lr=args.lr,
        patience=args.patience,
        device=args.device,
    )

    # Final evaluation
    test_metrics = evaluate(model, data, data["property"].test_mask, args.device)
    logger.info("\n=== Test Results ===")
    logger.info(f"MAPE: {test_metrics['mape']:.2f}%")
    logger.info(f"MAE: {test_metrics['mae']:,.0f} THB")
    logger.info(f"R²: {test_metrics['r2']:.4f}")

    # Evaluate by source type
    source_metrics = evaluate_by_source(
        model, data, data["property"].test_mask, args.device
    )
    for src_name, metrics in source_metrics.items():
        logger.info(f"\n{src_name.upper()} metrics:")
        logger.info(f"  MAPE: {metrics['mape']:.2f}%")
        logger.info(f"  MAE: {metrics['mae']:,.0f} THB")

    # Save model
    save_model(model, args.output, history, data, test_metrics)
    logger.info("Training complete!")


if __name__ == "__main__":
    main()
