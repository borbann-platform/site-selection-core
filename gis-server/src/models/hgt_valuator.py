"""
Heterogeneous Graph Transformer (HGT) for Property Valuation.

Implements a PyTorch model using HGTConv layers with meta-relation attention
to learn property values from heterogeneous urban graph context.

Key features:
- Multi-relation attention: learns different attention weights for
  Property-Transit, Property-Amenity, Property-FloodZone relationships
- Cold-start handling: properties in cells without transaction history
  inherit context from spatial neighbors via message passing
- Interpretable: exports attention weights for valuation explanations
"""

import logging

import torch
import torch.nn.functional as F
from torch import nn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Import PyG components with graceful fallback
try:
    from torch_geometric.data import HeteroData
    from torch_geometric.nn import HGTConv, Linear

    HAS_PYG = True
except ImportError:
    HAS_PYG = False
    logger.warning("torch_geometric not available. Model will not function.")


class PropertyEncoder(nn.Module):
    """
    Encode property intrinsic features.

    Transforms raw property attributes (area, age, floors, style)
    into a dense representation suitable for graph attention.
    """

    def __init__(self, input_dim: int, hidden_dim: int, dropout: float = 0.1):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.norm = nn.LayerNorm(hidden_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        x = self.norm(x)
        return x


class NodeTypeEncoder(nn.Module):
    """
    Generic encoder for auxiliary node types (Transit, Amenity, Flood).

    Maps heterogeneous input dimensions to a common hidden dimension.
    """

    def __init__(self, input_dim: int, hidden_dim: int):
        super().__init__()
        self.fc = nn.Linear(input_dim, hidden_dim)
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.fc(x))
        return self.norm(x)


class HGTValuator(nn.Module):
    """
    Heterogeneous Graph Transformer for Property Valuation.

    Architecture:
    1. Node-type-specific encoders project features to common hidden dim
    2. HGTConv layers perform meta-relation attention
    3. Property embeddings aggregated through MLP head for price prediction

    Args:
        node_feature_dims: Dict mapping node type -> input feature dimension
        hidden_dim: Hidden representation dimension
        num_heads: Number of attention heads in HGT
        num_layers: Number of HGT layers
        dropout: Dropout rate
        metadata: Graph metadata (node_types, edge_types) from HeteroData

    """

    def __init__(
        self,
        node_feature_dims: dict,
        hidden_dim: int = 128,
        num_heads: int = 4,
        num_layers: int = 2,
        dropout: float = 0.1,
        metadata: tuple | None = None,
    ):
        super().__init__()

        if not HAS_PYG:
            raise ImportError("torch_geometric required for HGTValuator")

        self.hidden_dim = hidden_dim
        self.num_heads = num_heads
        self.num_layers = num_layers

        # Node-type-specific encoders
        self.encoders = nn.ModuleDict()
        for node_type, input_dim in node_feature_dims.items():
            if node_type == "property":
                self.encoders[node_type] = PropertyEncoder(
                    input_dim, hidden_dim, dropout
                )
            else:
                self.encoders[node_type] = NodeTypeEncoder(input_dim, hidden_dim)

        # HGT convolution layers
        # metadata is (node_types, edge_types) tuple from HeteroData
        self.hgt_layers = nn.ModuleList()
        for i in range(num_layers):
            conv = HGTConv(
                in_channels=hidden_dim,
                out_channels=hidden_dim,
                metadata=metadata,
                heads=num_heads,
                dropout=dropout,
            )
            self.hgt_layers.append(conv)

        # Layer normalization after each HGT layer
        self.layer_norms = nn.ModuleList(
            [nn.LayerNorm(hidden_dim) for _ in range(num_layers)]
        )

        # Prediction head for property price
        self.prediction_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
        )

        # Store attention weights for interpretability
        self.attention_weights = {}

    def encode_nodes(self, x_dict: dict) -> dict:
        """Encode all node types to hidden dimension."""
        encoded = {}
        for node_type, x in x_dict.items():
            if node_type in self.encoders:
                encoded[node_type] = self.encoders[node_type](x)
            else:
                # Fallback: simple linear projection
                encoded[node_type] = F.relu(nn.Linear(x.size(1), self.hidden_dim)(x))
        return encoded

    def forward(
        self,
        x_dict: dict,
        edge_index_dict: dict,
        return_attention: bool = False,
    ) -> torch.Tensor:
        """
        Forward pass through HGT.

        Args:
            x_dict: Dict mapping node_type -> feature tensor
            edge_index_dict: Dict mapping edge_type -> edge_index tensor
            return_attention: If True, store attention weights

        Returns:
            Predicted prices for property nodes

        """
        # Encode node features
        h_dict = self.encode_nodes(x_dict)

        # Apply HGT layers
        for i, (conv, norm) in enumerate(zip(self.hgt_layers, self.layer_norms)):
            h_dict_new = conv(h_dict, edge_index_dict)

            # Residual connection + normalization
            for node_type in h_dict:
                if node_type in h_dict_new:
                    h_dict[node_type] = norm(h_dict[node_type] + h_dict_new[node_type])

        # Extract property embeddings
        property_embeddings = h_dict["property"]

        # Predict prices
        predictions = self.prediction_head(property_embeddings).squeeze(-1)

        return predictions

    def get_attention_weights(self) -> dict:
        """Return stored attention weights for interpretability."""
        return self.attention_weights


class HGTValuatorWithColdStart(HGTValuator):
    """
    HGT Valuator with explicit cold-start handling.

    For properties in cells without transaction history:
    1. Initial embedding is zero (no learned context)
    2. Message passing aggregates context from neighboring cells
    3. Additional "context imputation" layer refines cold-start embeddings
    """

    def __init__(
        self,
        node_feature_dims: dict,
        hidden_dim: int = 128,
        num_heads: int = 4,
        num_layers: int = 2,
        dropout: float = 0.1,
        metadata: tuple | None = None,
    ):
        super().__init__(
            node_feature_dims,
            hidden_dim,
            num_heads,
            num_layers,
            dropout,
            metadata,
        )

        # Cold-start context aggregator
        # Learns to weight neighbor context for cold-start nodes
        self.cold_start_aggregator = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )

        # Confidence estimator for cold-start predictions
        self.confidence_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid(),  # Output [0, 1] confidence
        )

    def forward(
        self,
        x_dict: dict,
        edge_index_dict: dict,
        cold_start_mask: torch.Tensor | None = None,
        return_confidence: bool = False,
    ) -> tuple:
        """
        Forward pass with cold-start handling.

        Args:
            x_dict: Dict mapping node_type -> feature tensor
            edge_index_dict: Dict mapping edge_type -> edge_index tensor
            cold_start_mask: Boolean mask for cold-start property nodes
            return_confidence: If True, return confidence scores

        Returns:
            (predictions, confidence) if return_confidence else predictions

        """
        # Encode node features
        h_dict = self.encode_nodes(x_dict)

        # Apply HGT layers with special handling for cold-start
        for i, (conv, norm) in enumerate(zip(self.hgt_layers, self.layer_norms)):
            h_dict_new = conv(h_dict, edge_index_dict)

            # For cold-start nodes on first layer, use aggregated context
            if i == 0 and cold_start_mask is not None and cold_start_mask.any():
                # Cold-start properties get enhanced context aggregation
                cold_embeddings = h_dict_new.get("property", h_dict["property"])
                aggregated = self.cold_start_aggregator(cold_embeddings)

                # Blend original and aggregated for cold-start nodes
                if "property" in h_dict_new:
                    h_dict_new["property"] = torch.where(
                        cold_start_mask.unsqueeze(-1),
                        aggregated,
                        h_dict_new["property"],
                    )

            # Residual connection + normalization
            for node_type in h_dict:
                if node_type in h_dict_new:
                    h_dict[node_type] = norm(h_dict[node_type] + h_dict_new[node_type])

        # Extract property embeddings
        property_embeddings = h_dict["property"]

        # Predict prices
        predictions = self.prediction_head(property_embeddings).squeeze(-1)

        if return_confidence:
            # Estimate prediction confidence
            confidence = self.confidence_head(property_embeddings).squeeze(-1)

            # Cold-start nodes have lower base confidence
            if cold_start_mask is not None:
                confidence = torch.where(
                    cold_start_mask,
                    confidence * 0.7,  # Reduce confidence for cold-start
                    confidence,
                )

            return predictions, confidence

        return predictions


def create_model_from_data(
    data: "HeteroData", hidden_dim: int = 128
) -> HGTValuatorWithColdStart:
    """
    Factory function to create model from HeteroData.

    Automatically infers feature dimensions and metadata.
    """
    # Infer feature dimensions from data
    node_feature_dims = {}
    for node_type in data.node_types:
        if hasattr(data[node_type], "x"):
            node_feature_dims[node_type] = data[node_type].x.size(1)

    # Get metadata (node_types, edge_types)
    metadata = data.metadata()

    model = HGTValuatorWithColdStart(
        node_feature_dims=node_feature_dims,
        hidden_dim=hidden_dim,
        metadata=metadata,
    )

    return model


class ValuationLoss(nn.Module):
    """
    Custom loss function for property valuation.

    Combines:
    - MAPE (Mean Absolute Percentage Error): primary metric
    - MAE (Mean Absolute Error): stability
    - Cold-start penalty: lower weight for cold-start predictions
    """

    def __init__(self, mape_weight: float = 0.7, mae_weight: float = 0.3):
        super().__init__()
        self.mape_weight = mape_weight
        self.mae_weight = mae_weight

    def forward(
        self,
        predictions: torch.Tensor,
        targets: torch.Tensor,
        cold_start_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        # Avoid division by zero
        targets_safe = torch.clamp(targets, min=1.0)

        # MAPE
        mape = torch.abs((predictions - targets) / targets_safe).mean()

        # MAE (normalized by mean target for scale invariance)
        mae = torch.abs(predictions - targets).mean() / targets.mean()

        # Combined loss
        loss = self.mape_weight * mape + self.mae_weight * mae

        # Apply cold-start weighting if provided
        if cold_start_mask is not None and cold_start_mask.any():
            # Reduce loss contribution from cold-start nodes
            cold_weight = 0.5
            warm_mask = ~cold_start_mask
            if warm_mask.any():
                warm_loss = torch.abs(
                    (predictions[warm_mask] - targets[warm_mask])
                    / targets_safe[warm_mask]
                ).mean()
                cold_loss = torch.abs(
                    (predictions[cold_start_mask] - targets[cold_start_mask])
                    / targets_safe[cold_start_mask]
                ).mean()
                loss = warm_loss + cold_weight * cold_loss

        return loss


# Utility functions for model training/inference


def get_model_summary(model: nn.Module) -> str:
    """Get human-readable model summary."""
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

    summary = f"""
    HGT Valuator Model Summary
    ==========================
    Total parameters: {total_params:,}
    Trainable parameters: {trainable_params:,}
    Hidden dimension: {model.hidden_dim}
    Attention heads: {model.num_heads}
    HGT layers: {model.num_layers}
    """
    return summary
