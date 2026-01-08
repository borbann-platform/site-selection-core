"""
GraphMAE Pre-training for Spatial Context Learning.

Implements Graph Masked Autoencoder for self-supervised pre-training
on the urban graph. The model learns to reconstruct masked node features
from graph context, capturing correlations between POIs, transit, prices.

This pre-trained encoder is then fine-tuned for property valuation,
providing better generalization especially for cold-start areas.

Usage:
    python -m scripts.pretrain_graphmae --input data/hetero_graph.pt --output models/graphmae
"""

import argparse
import logging
import random
from pathlib import Path

import torch
import torch.nn.functional as F
from torch import nn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import PyG with fallback
try:
    from torch_geometric.data import HeteroData
    from torch_geometric.loader import NeighborLoader
    from torch_geometric.nn import GATConv, Linear

    HAS_PYG = True
except ImportError:
    HAS_PYG = False
    logger.warning("torch_geometric not available")

# Pre-training hyperparameters
MASK_RATIO = 0.3  # Fraction of nodes to mask
HIDDEN_DIM = 128
NUM_LAYERS = 2
LEARNING_RATE = 1e-3
EPOCHS = 100
BATCH_SIZE = 256


class FeatureMasker:
    """
    Mask node features for GraphMAE pre-training.

    Masking strategies:
    1. Random feature masking: mask random subset of feature dimensions
    2. Full node masking: mask all features for random nodes
    3. Structured masking: mask correlated feature groups (e.g., all POI counts)
    """

    def __init__(self, mask_ratio: float = MASK_RATIO, strategy: str = "node"):
        self.mask_ratio = mask_ratio
        self.strategy = strategy

    def mask_node_features(
        self,
        x: torch.Tensor,
        return_mask: bool = True,
    ) -> tuple:
        """
        Mask node features.

        Args:
            x: Node feature tensor [num_nodes, num_features]
            return_mask: Return mask tensor for loss computation

        Returns:
            (masked_x, mask) where mask[i] = True if node i was masked

        """
        num_nodes = x.size(0)
        num_mask = int(num_nodes * self.mask_ratio)

        # Random node selection
        mask_indices = random.sample(range(num_nodes), num_mask)
        mask = torch.zeros(num_nodes, dtype=torch.bool)
        mask[mask_indices] = True

        # Create masked version
        masked_x = x.clone()

        if self.strategy == "node":
            # Zero out entire node features
            masked_x[mask] = 0.0
        elif self.strategy == "feature":
            # Zero out random features per masked node
            num_features = x.size(1)
            feature_mask_ratio = 0.5
            for idx in mask_indices:
                num_feat_mask = int(num_features * feature_mask_ratio)
                feat_indices = random.sample(range(num_features), num_feat_mask)
                masked_x[idx, feat_indices] = 0.0
        elif self.strategy == "noise":
            # Add noise instead of zeroing
            noise = torch.randn_like(x[mask]) * 0.5
            masked_x[mask] = masked_x[mask] + noise

        if return_mask:
            return masked_x, mask
        return masked_x


class GraphMAEEncoder(nn.Module):
    """
    GNN Encoder for GraphMAE.

    Uses GAT layers to aggregate neighborhood context.
    Output: latent node embeddings that capture spatial relationships.
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = HIDDEN_DIM,
        num_layers: int = NUM_LAYERS,
        num_heads: int = 4,
        dropout: float = 0.1,
    ):
        super().__init__()

        self.input_proj = nn.Linear(input_dim, hidden_dim)

        self.gat_layers = nn.ModuleList()
        self.layer_norms = nn.ModuleList()

        for i in range(num_layers):
            # GAT layer
            gat = GATConv(
                in_channels=hidden_dim,
                out_channels=hidden_dim // num_heads,
                heads=num_heads,
                dropout=dropout,
                concat=True,
            )
            self.gat_layers.append(gat)
            self.layer_norms.append(nn.LayerNorm(hidden_dim))

        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        # Project input
        h = self.input_proj(x)

        # Apply GAT layers
        for gat, norm in zip(self.gat_layers, self.layer_norms):
            h_new = gat(h, edge_index)
            h = norm(h + self.dropout(h_new))  # Residual + norm

        return h


class GraphMAEDecoder(nn.Module):
    """
    Decoder for GraphMAE feature reconstruction.

    Takes latent embeddings and reconstructs original node features.
    """

    def __init__(
        self,
        hidden_dim: int,
        output_dim: int,
        num_layers: int = 2,
    ):
        super().__init__()

        layers = []
        for i in range(num_layers - 1):
            layers.extend(
                [
                    nn.Linear(hidden_dim, hidden_dim),
                    nn.ReLU(),
                    nn.LayerNorm(hidden_dim),
                ]
            )
        layers.append(nn.Linear(hidden_dim, output_dim))

        self.decoder = nn.Sequential(*layers)

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        return self.decoder(h)


class GraphMAE(nn.Module):
    """
    Graph Masked Autoencoder for self-supervised pre-training.

    Training objective: reconstruct masked node features from
    graph context provided by unmasked neighbors.

    Architecture:
    1. Masker: randomly mask node features
    2. Encoder: GNN aggregates context from unmasked neighbors
    3. Decoder: MLP reconstructs original features

    Loss: MSE between reconstructed and original features (masked nodes only)
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = HIDDEN_DIM,
        num_layers: int = NUM_LAYERS,
        mask_ratio: float = MASK_RATIO,
    ):
        super().__init__()

        self.masker = FeatureMasker(mask_ratio=mask_ratio, strategy="node")
        self.encoder = GraphMAEEncoder(input_dim, hidden_dim, num_layers)
        self.decoder = GraphMAEDecoder(hidden_dim, input_dim)

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        return_embeddings: bool = False,
    ) -> tuple:
        """
        Forward pass with masking and reconstruction.

        Returns:
            (loss, reconstructed, embeddings) tuple

        """
        # Mask features
        masked_x, mask = self.masker.mask_node_features(x)

        # Encode
        embeddings = self.encoder(masked_x, edge_index)

        # Decode
        reconstructed = self.decoder(embeddings)

        # Compute loss only on masked nodes
        if mask.any():
            loss = F.mse_loss(reconstructed[mask], x[mask])
        else:
            loss = torch.tensor(0.0)

        if return_embeddings:
            return loss, reconstructed, embeddings
        return loss, reconstructed

    def encode(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        """Encode without masking (for inference)."""
        return self.encoder(x, edge_index)


class HeteroGraphMAE(nn.Module):
    """
    GraphMAE for heterogeneous graphs.

    Handles multiple node types with type-specific encoders and decoders,
    but shared latent space for cross-type information flow.
    """

    def __init__(
        self,
        node_feature_dims: dict,
        hidden_dim: int = HIDDEN_DIM,
        num_layers: int = NUM_LAYERS,
        mask_ratio: float = MASK_RATIO,
    ):
        super().__init__()

        self.hidden_dim = hidden_dim
        self.masker = FeatureMasker(mask_ratio=mask_ratio)

        # Type-specific input projections
        self.input_projs = nn.ModuleDict()
        for node_type, dim in node_feature_dims.items():
            self.input_projs[node_type] = nn.Linear(dim, hidden_dim)

        # Shared encoder (simplified: homogeneous GAT on projected features)
        # For full heterogeneous encoding, use HGTConv
        self.encoder_layers = nn.ModuleList(
            [
                nn.TransformerEncoderLayer(
                    d_model=hidden_dim,
                    nhead=4,
                    dim_feedforward=hidden_dim * 2,
                    dropout=0.1,
                    batch_first=True,
                )
                for _ in range(num_layers)
            ]
        )

        # Type-specific decoders
        self.decoders = nn.ModuleDict()
        for node_type, dim in node_feature_dims.items():
            self.decoders[node_type] = GraphMAEDecoder(hidden_dim, dim)

        self.node_feature_dims = node_feature_dims

    def forward(self, data: "HeteroData") -> tuple:
        """
        Forward pass on heterogeneous graph.

        Returns:
            (total_loss, losses_per_type, embeddings_dict)

        """
        losses = {}
        embeddings = {}

        # Process each node type independently (simplified version)
        # For full version, use message passing across types
        for node_type in self.node_feature_dims:
            if not hasattr(data[node_type], "x"):
                continue

            x = data[node_type].x

            # Mask
            masked_x, mask = self.masker.mask_node_features(x)

            # Project to hidden dim
            h = self.input_projs[node_type](masked_x)

            # Apply transformer layers (self-attention as simplified GNN)
            h = h.unsqueeze(0)  # Add batch dim
            for layer in self.encoder_layers:
                h = layer(h)
            h = h.squeeze(0)

            embeddings[node_type] = h

            # Decode
            reconstructed = self.decoders[node_type](h)

            # Compute loss
            if mask.any():
                losses[node_type] = F.mse_loss(reconstructed[mask], x[mask])
            else:
                losses[node_type] = torch.tensor(0.0)

        total_loss = sum(losses.values()) / len(losses) if losses else torch.tensor(0.0)

        return total_loss, losses, embeddings

    def get_pretrained_embeddings(self, data: "HeteroData") -> dict:
        """Get embeddings without masking."""
        embeddings = {}

        for node_type in self.node_feature_dims:
            if not hasattr(data[node_type], "x"):
                continue

            x = data[node_type].x
            h = self.input_projs[node_type](x)

            h = h.unsqueeze(0)
            for layer in self.encoder_layers:
                h = layer(h)
            h = h.squeeze(0)

            embeddings[node_type] = h

        return embeddings


def train_graphmae(
    model: GraphMAE,
    data: torch.Tensor,
    edge_index: torch.Tensor,
    epochs: int = EPOCHS,
    lr: float = LEARNING_RATE,
    device: str = "cpu",
) -> GraphMAE:
    """
    Train GraphMAE on homogeneous graph.
    """
    model = model.to(device)
    data = data.to(device)
    edge_index = edge_index.to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    model.train()
    for epoch in range(epochs):
        optimizer.zero_grad()

        loss, _ = model(data, edge_index)
        loss.backward()

        optimizer.step()
        scheduler.step()

        if (epoch + 1) % 10 == 0:
            logger.info(f"Epoch {epoch + 1}/{epochs}, Loss: {loss.item():.4f}")

    return model


def train_hetero_graphmae(
    model: HeteroGraphMAE,
    data: "HeteroData",
    epochs: int = EPOCHS,
    lr: float = LEARNING_RATE,
    device: str = "cpu",
) -> HeteroGraphMAE:
    """
    Train HeteroGraphMAE on heterogeneous graph.
    """
    model = model.to(device)
    data = data.to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    model.train()
    for epoch in range(epochs):
        optimizer.zero_grad()

        total_loss, losses, _ = model(data)
        total_loss.backward()

        optimizer.step()
        scheduler.step()

        if (epoch + 1) % 10 == 0:
            loss_str = ", ".join(f"{k}: {v.item():.4f}" for k, v in losses.items())
            logger.info(
                f"Epoch {epoch + 1}/{epochs}, Total: {total_loss.item():.4f}, {loss_str}"
            )

    return model


def save_pretrained(
    model: nn.Module,
    embeddings: dict,
    output_dir: Path,
):
    """Save pretrained model and embeddings."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save model
    model_path = output_dir / "graphmae_pretrained.pt"
    torch.save(model.state_dict(), model_path)
    logger.info(f"Saved model to {model_path}")

    # Save embeddings
    for node_type, emb in embeddings.items():
        emb_path = output_dir / f"pretrained_embeddings_{node_type}.pt"
        torch.save(emb.detach().cpu(), emb_path)
        logger.info(f"Saved {node_type} embeddings to {emb_path}")


def main():
    parser = argparse.ArgumentParser(description="Pre-train GraphMAE")
    parser.add_argument(
        "--input",
        type=str,
        default="data/hetero_graph.pt",
        help="Input heterogeneous graph path",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="models/graphmae",
        help="Output directory for pretrained model",
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
        "--device",
        type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="Device to train on",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)

    if not input_path.exists():
        logger.error(f"Input graph not found: {input_path}")
        logger.info("Run build_hetero_graph.py first")
        return

    # Load graph
    logger.info(f"Loading graph from {input_path}")
    data = torch.load(input_path)

    # Infer feature dimensions
    node_feature_dims = {}
    for node_type in data.node_types:
        if hasattr(data[node_type], "x"):
            node_feature_dims[node_type] = data[node_type].x.size(1)

    logger.info(f"Node types and dimensions: {node_feature_dims}")

    # Create model
    model = HeteroGraphMAE(
        node_feature_dims=node_feature_dims,
        hidden_dim=HIDDEN_DIM,
        mask_ratio=MASK_RATIO,
    )

    logger.info(f"Training HeteroGraphMAE for {args.epochs} epochs on {args.device}")

    # Train
    model = train_hetero_graphmae(
        model,
        data,
        epochs=args.epochs,
        lr=args.lr,
        device=args.device,
    )

    # Get final embeddings
    model.eval()
    with torch.no_grad():
        embeddings = model.get_pretrained_embeddings(data.to(args.device))

    # Save
    save_pretrained(model, embeddings, output_dir)

    logger.info("Done!")


if __name__ == "__main__":
    main()
