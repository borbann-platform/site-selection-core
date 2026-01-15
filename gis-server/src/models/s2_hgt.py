"""
Semantic-Spatial Heterogeneous Graph Transformer (S2-HGT) for Property Valuation.

Extends HGTValuator with:
1. Categorical Source Token: Learns bias between Treasury/Listing/Transaction prices
2. Fourier Spatial Encoding: Position-aware embeddings for lat/lon
3. Anchor Node Attention: Network-distance-weighted attention to Tier-1 POIs
4. Explainability Hooks: Returns Top-K attention weights for Agent integration

Architecture:
    Property → Encoder → +SourceBias → +SpatialEmb → HGT Layers → Price Head
                                                         ↑
    Anchor Nodes → Encoder → +SpatialEmb → Network-Distance-Weighted Attention
"""

import logging
import math

import torch
import torch.nn.functional as F
from torch import nn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import PyG components with graceful fallback
try:
    from torch_geometric.data import HeteroData
    from torch_geometric.nn import HeteroConv, HGTConv, SAGEConv

    HAS_PYG = True
except ImportError:
    HAS_PYG = False
    logger.warning("torch_geometric not available. S2-HGT will not function.")


# =============================================================================
# Source Token Constants
# =============================================================================
SOURCE_TREASURY = 0  # Treasury appraisal (tax base, typically 30-50% below market)
SOURCE_LISTING = 1  # Listing price (seller expectation, typically 10-20% above market)
SOURCE_TRANSACTION = 2  # Actual transaction (ground truth, if available)
NUM_SOURCE_TYPES = 3


class FourierSpatialEncoder(nn.Module):
    """
    Fourier feature encoding for spatial coordinates (lat/lon).

    Maps 2D coordinates to higher-dimensional space using sinusoidal features,
    enabling the model to learn spatial patterns at multiple frequencies.

    Based on: "Fourier Features Let Networks Learn High Frequency Functions"
    (Tancik et al., NeurIPS 2020)
    """

    def __init__(self, hidden_dim: int, num_frequencies: int = 16, scale: float = 10.0):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_frequencies = num_frequencies

        # Learnable frequency matrix
        # Initialize with geometric series of frequencies
        freqs = scale * 2.0 ** torch.linspace(0, num_frequencies - 1, num_frequencies)
        self.register_buffer("freqs", freqs)

        # Project Fourier features to hidden dim
        # Input: 2 coords × num_frequencies × 2 (sin, cos) = 4 × num_frequencies
        self.projection = nn.Linear(4 * num_frequencies, hidden_dim)

    def forward(self, coords: torch.Tensor) -> torch.Tensor:
        """
        Encode spatial coordinates.

        Args:
            coords: (N, 2) tensor of (lat, lon) coordinates

        Returns:
            (N, hidden_dim) spatial embeddings

        """
        # Normalize coordinates to [-1, 1] range (Bangkok approx)
        # Lat: 13.5-14.0, Lon: 100.3-100.9
        lat_norm = (coords[:, 0] - 13.75) / 0.5
        lon_norm = (coords[:, 1] - 100.6) / 0.5

        # Compute Fourier features
        lat_freqs = lat_norm.unsqueeze(-1) * self.freqs  # (N, num_freq)
        lon_freqs = lon_norm.unsqueeze(-1) * self.freqs

        # Sin and cos for each frequency
        features = torch.cat(
            [
                torch.sin(lat_freqs),
                torch.cos(lat_freqs),
                torch.sin(lon_freqs),
                torch.cos(lon_freqs),
            ],
            dim=-1,
        )  # (N, 4 * num_freq)

        return self.projection(features)


class PropertyEncoder(nn.Module):
    """
    Encode property intrinsic features.

    Handles missing floor data via learned flag embedding.
    """

    def __init__(self, input_dim: int, hidden_dim: int, dropout: float = 0.1):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.norm = nn.LayerNorm(hidden_dim)
        self.dropout = nn.Dropout(dropout)

        # Floor missing flag embedding (learned)
        self.floor_missing_emb = nn.Embedding(2, hidden_dim // 4)

    def forward(
        self, x: torch.Tensor, floor_missing: torch.Tensor | None = None
    ) -> torch.Tensor:
        h = F.relu(self.fc1(x))
        h = self.dropout(h)
        h = self.fc2(h)
        h = self.norm(h)

        # Add floor missing embedding if provided
        if floor_missing is not None:
            floor_emb = self.floor_missing_emb(floor_missing.long())
            # Pad to match hidden dim
            floor_emb = F.pad(floor_emb, (0, h.size(-1) - floor_emb.size(-1)))
            h = h + floor_emb

        return h


class AnchorEncoder(nn.Module):
    """
    Encode anchor node features (Tier-1 POIs).

    Includes tier embedding and category embedding for rich anchor representation.
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        num_categories: int = 10,
        num_tiers: int = 3,
    ):
        super().__init__()
        self.fc = nn.Linear(input_dim, hidden_dim)
        self.norm = nn.LayerNorm(hidden_dim)

        # Category and tier embeddings
        self.category_emb = nn.Embedding(num_categories, hidden_dim // 2)
        self.tier_emb = nn.Embedding(num_tiers, hidden_dim // 4)

    def forward(
        self,
        x: torch.Tensor,
        category: torch.Tensor | None = None,
        tier: torch.Tensor | None = None,
    ) -> torch.Tensor:
        h = F.relu(self.fc(x))
        h = self.norm(h)

        if category is not None:
            cat_emb = self.category_emb(category)
            cat_emb = F.pad(cat_emb, (0, h.size(-1) - cat_emb.size(-1)))
            h = h + cat_emb

        if tier is not None:
            tier_e = self.tier_emb(tier)
            tier_e = F.pad(tier_e, (0, h.size(-1) - tier_e.size(-1)))
            h = h + tier_e

        return h


class NodeTypeEncoder(nn.Module):
    """Generic encoder for auxiliary node types."""

    def __init__(self, input_dim: int, hidden_dim: int):
        super().__init__()
        self.fc = nn.Linear(input_dim, hidden_dim)
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.norm(F.relu(self.fc(x)))


class DistanceWeightedAttention(nn.Module):
    """
    Attention layer weighted by network distance using RBF kernel.

    For Property → Anchor edges, modulates attention scores by Gaussian RBF:
    weight = exp(-gamma * d^2), making nearby anchors more influential.
    Learnable gamma per head allows different distance sensitivities.
    """

    def __init__(
        self,
        hidden_dim: int,
        num_heads: int = 4,
        dropout: float = 0.1,
        rbf_gamma_init: float = 0.00001,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_heads = num_heads
        self.head_dim = hidden_dim // num_heads

        # Query, Key, Value projections
        self.q_proj = nn.Linear(hidden_dim, hidden_dim)
        self.k_proj = nn.Linear(hidden_dim, hidden_dim)
        self.v_proj = nn.Linear(hidden_dim, hidden_dim)
        self.out_proj = nn.Linear(hidden_dim, hidden_dim)

        # RBF kernel: learnable gamma per head
        # gamma=0.00001 → sigma≈316m (half-attention at ~316m)
        self.rbf_gamma = nn.Parameter(
            torch.full((num_heads,), rbf_gamma_init, dtype=torch.float)
        )

        self.dropout = nn.Dropout(dropout)
        self.scale = math.sqrt(self.head_dim)

    def forward(
        self,
        query: torch.Tensor,  # Property embeddings
        key: torch.Tensor,  # Anchor embeddings
        value: torch.Tensor,  # Anchor embeddings
        edge_index: torch.Tensor,  # (2, E) property->anchor edges
        edge_attr: torch.Tensor,  # (E, 1) network distances
        return_attention: bool = False,
    ) -> tuple:
        """
        Compute distance-weighted attention.

        Returns:
            Updated property embeddings, optionally attention weights

        """
        # Project Q, K, V
        Q = self.q_proj(query)  # (N_prop, hidden)
        K = self.k_proj(key)  # (N_anchor, hidden)
        V = self.v_proj(value)  # (N_anchor, hidden)

        # Reshape for multi-head attention
        Q = Q.view(-1, self.num_heads, self.head_dim)
        K = K.view(-1, self.num_heads, self.head_dim)
        V = V.view(-1, self.num_heads, self.head_dim)

        # Compute attention scores for edges only (sparse)
        src, dst = edge_index  # src=property, dst=anchor

        # Get Q for source (property) and K for dest (anchor)
        q_src = Q[src]  # (E, heads, head_dim)
        k_dst = K[dst]  # (E, heads, head_dim)

        # Attention scores: q · k / sqrt(d)
        attn_scores = (q_src * k_dst).sum(dim=-1) / self.scale  # (E, heads)

        # Apply RBF distance weighting: exp(-gamma * d^2)
        # edge_attr is in meters, gamma is learnable per head
        dist_squared = edge_attr**2  # (E, 1)
        # Clamp gamma to positive, expand for broadcasting
        gamma = torch.clamp(self.rbf_gamma, min=1e-8)  # (heads,)
        rbf_weight = torch.exp(-gamma.unsqueeze(0) * dist_squared)  # (E, heads)

        # Multiplicative modulation: closer anchors get higher attention
        attn_scores = attn_scores * rbf_weight

        # Softmax over neighbors for each property node
        # Need to scatter softmax per source node
        attn_probs = self._sparse_softmax(attn_scores, src, num_nodes=query.size(0))
        attn_probs = self.dropout(attn_probs)

        # Gather values and aggregate
        v_dst = V[dst]  # (E, heads, head_dim)
        weighted_v = attn_probs.unsqueeze(-1) * v_dst  # (E, heads, head_dim)

        # Scatter-add to property nodes
        out = torch.zeros(
            query.size(0), self.num_heads, self.head_dim, device=query.device
        )
        out.scatter_add_(
            0, src.unsqueeze(-1).unsqueeze(-1).expand_as(weighted_v), weighted_v
        )

        # Reshape and project
        out = out.view(-1, self.hidden_dim)
        out = self.out_proj(out)

        if return_attention:
            return out, (edge_index, attn_probs)
        return out, None

    def _sparse_softmax(
        self, scores: torch.Tensor, index: torch.Tensor, num_nodes: int
    ) -> torch.Tensor:
        """Compute softmax over sparse edge scores grouped by source node."""
        # Subtract max for numerical stability (per source node)
        max_scores = torch.zeros(num_nodes, scores.size(1), device=scores.device)
        max_scores.scatter_reduce_(
            0, index.unsqueeze(-1).expand_as(scores), scores, reduce="amax"
        )
        scores = scores - max_scores[index]

        # Exp
        exp_scores = torch.exp(scores)

        # Sum per source node
        sum_exp = torch.zeros(num_nodes, scores.size(1), device=scores.device)
        sum_exp.scatter_add_(0, index.unsqueeze(-1).expand_as(exp_scores), exp_scores)

        # Normalize
        return exp_scores / (sum_exp[index] + 1e-8)


class S2HGT(nn.Module):
    """
    Semantic-Spatial Heterogeneous Graph Transformer.

    Key innovations:
    1. Source Token: Categorical bias for Treasury vs Listing prices
    2. Spatial Encoding: Fourier features for coordinate awareness
    3. Distance-Weighted Anchor Attention: Network distance modulates importance
    4. Explainability: Stores attention weights for Top-K anchor analysis

    Forward flow:
        Property features → Encode → +SourceBias → +SpatialEmb
        → HGT Layer 1 (H3 context aggregation)
        → HGT Layer 2 (neighborhood spillover)
        → Anchor Attention (distance-weighted)
        → Price prediction head
    """

    def __init__(
        self,
        node_feature_dims: dict,
        hidden_dim: int = 128,
        num_heads: int = 4,
        num_layers: int = 3,
        dropout: float = 0.1,
        metadata: tuple | None = None,
    ):
        super().__init__()

        if not HAS_PYG:
            raise ImportError("torch_geometric required for S2HGT")

        self.hidden_dim = hidden_dim
        self.num_heads = num_heads
        self.num_layers = num_layers

        # ====== Source Token Embedding ======
        # Learns the "gap" between price sources
        self.source_embedding = nn.Embedding(NUM_SOURCE_TYPES, hidden_dim)
        # Multiplicative scale factor per source (learns variance scaling)
        self.source_scale = nn.Embedding(NUM_SOURCE_TYPES, hidden_dim)
        # Initialize scale weights to produce ~1.0 after sigmoid
        nn.init.zeros_(self.source_scale.weight)  # sigmoid(0) = 0.5, *2 = 1.0

        # ====== Spatial Encoding ======
        self.spatial_encoder = FourierSpatialEncoder(hidden_dim)

        # ====== Node Encoders ======
        self.encoders = nn.ModuleDict()
        for node_type, input_dim in node_feature_dims.items():
            if node_type == "property":
                self.encoders[node_type] = PropertyEncoder(
                    input_dim, hidden_dim, dropout
                )
            elif node_type == "anchor":
                self.encoders[node_type] = AnchorEncoder(input_dim, hidden_dim)
            else:
                self.encoders[node_type] = NodeTypeEncoder(input_dim, hidden_dim)

        # ====== HGT Layers ======
        # Standard HGT for heterogeneous message passing
        # Note: HGTConv dropout handled via separate Dropout layers
        self.dropout = nn.Dropout(dropout)
        if metadata is not None:
            self.hgt_layers = nn.ModuleList()
            for _ in range(num_layers):
                conv = HGTConv(
                    in_channels=hidden_dim,
                    out_channels=hidden_dim,
                    metadata=metadata,
                    heads=num_heads,
                )
                self.hgt_layers.append(conv)
        else:
            self.hgt_layers = nn.ModuleList()
            logger.warning("No metadata provided; HGT layers disabled")

        self.layer_norms = nn.ModuleList(
            [nn.LayerNorm(hidden_dim) for _ in range(num_layers)]
        )

        # ====== Distance-Weighted Anchor Attention ======
        self.anchor_attention = DistanceWeightedAttention(
            hidden_dim, num_heads, dropout
        )

        # ====== Prediction Head (Shared) ======
        self.prediction_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
        )

        # ====== Per-Source Output Adjustment ======
        # Scale and bias applied after prediction head
        # Addresses systematic price gap between sources (listings ~0.42 higher)
        self.output_scale = nn.Parameter(torch.ones(NUM_SOURCE_TYPES))
        output_bias_init = torch.zeros(NUM_SOURCE_TYPES)
        output_bias_init[SOURCE_LISTING] = 0.3  # Prior: listings are higher
        self.output_bias = nn.Parameter(output_bias_init)

        # ====== Explainability Storage ======
        self.attention_weights = {}

    def forward(
        self,
        x_dict: dict,
        edge_index_dict: dict,
        edge_attr_dict: dict | None = None,
        source_type: torch.Tensor | None = None,
        coords_dict: dict | None = None,
        return_attention: bool = False,
    ) -> torch.Tensor:
        """
        Forward pass through S2-HGT.

        Args:
            x_dict: Node features {node_type: (N, D)}
            edge_index_dict: Edge indices {(src, rel, dst): (2, E)}
            edge_attr_dict: Edge attributes (e.g., network distance)
            source_type: (N_property,) tensor of source types (0/1/2)
            coords_dict: Coordinates {node_type: (N, 2)} for spatial encoding
            return_attention: Store attention weights for explainability

        Returns:
            Predicted prices for property nodes

        """
        # ====== 1. Encode Node Features ======
        h_dict = {}
        for node_type, x in x_dict.items():
            if node_type in self.encoders:
                h_dict[node_type] = self.encoders[node_type](x)
            else:
                # Fallback projection
                h_dict[node_type] = F.relu(
                    nn.Linear(x.size(1), self.hidden_dim, device=x.device)(x)
                )

        # ====== 2. Add Source Scale + Bias (Property nodes only) ======
        # Multiplicative gate allows Listings to "stretch" feature importance
        if source_type is not None and "property" in h_dict:
            scale = torch.sigmoid(self.source_scale(source_type)) * 2.0  # Range [0, 2]
            bias = self.source_embedding(source_type)
            h_dict["property"] = h_dict["property"] * scale + bias

        # ====== 3. Add Spatial Encoding ======
        if coords_dict is not None:
            for node_type, coords in coords_dict.items():
                if node_type in h_dict:
                    spatial_emb = self.spatial_encoder(coords)
                    h_dict[node_type] = h_dict[node_type] + spatial_emb

        # ====== 4. HGT Message Passing ======
        for i, (conv, norm) in enumerate(zip(self.hgt_layers, self.layer_norms)):
            h_dict_new = conv(h_dict, edge_index_dict)

            # Residual + LayerNorm + Dropout
            for node_type in h_dict:
                if node_type in h_dict_new:
                    h_dict[node_type] = self.dropout(
                        norm(h_dict[node_type] + h_dict_new[node_type])
                    )

        # ====== 5. Anchor Attention (if anchor nodes present) ======
        if "anchor" in h_dict and ("property", "access", "anchor") in edge_index_dict:
            edge_key = ("property", "access", "anchor")
            anchor_edge_index = edge_index_dict[edge_key]
            anchor_edge_attr = (
                edge_attr_dict.get(edge_key, torch.ones(anchor_edge_index.size(1), 1))
                if edge_attr_dict
                else torch.ones(
                    anchor_edge_index.size(1), 1, device=h_dict["property"].device
                )
            )

            anchor_out, attn_info = self.anchor_attention(
                query=h_dict["property"],
                key=h_dict["anchor"],
                value=h_dict["anchor"],
                edge_index=anchor_edge_index,
                edge_attr=anchor_edge_attr,
                return_attention=return_attention,
            )

            # Residual connection
            h_dict["property"] = h_dict["property"] + anchor_out

            if return_attention and attn_info is not None:
                self.attention_weights["anchor"] = attn_info

        # ====== 6. Prediction ======
        property_embeddings = h_dict["property"]
        predictions = self.prediction_head(property_embeddings).squeeze(-1)

        # ====== 7. Source-Aware Price Adjustment ======
        if source_type is not None:
            scale = self.output_scale[source_type]
            bias = self.output_bias[source_type]
            predictions = predictions * scale + bias

        return predictions

    def get_top_k_anchor_attention(
        self, k: int = 5, anchor_ids: list | None = None
    ) -> list[dict]:
        """
        Extract top-K anchor nodes by attention weight for each property.

        Used by Agent for explainability.

        Returns:
            List of dicts: [{"property_idx": i, "anchors": [(anchor_idx, weight), ...]}]

        """
        if "anchor" not in self.attention_weights:
            return []

        edge_index, attn_probs = self.attention_weights["anchor"]
        src_nodes = edge_index[0]  # property indices
        dst_nodes = edge_index[1]  # anchor indices

        # Average attention across heads
        attn_mean = attn_probs.mean(dim=-1)  # (E,)

        results = []
        unique_props = src_nodes.unique()

        for prop_idx in unique_props:
            mask = src_nodes == prop_idx
            prop_anchors = dst_nodes[mask]
            prop_weights = attn_mean[mask]

            # Top-K
            topk_indices = prop_weights.topk(min(k, len(prop_weights))).indices
            top_anchors = [
                {
                    "anchor_idx": prop_anchors[i].item(),
                    "anchor_id": anchor_ids[prop_anchors[i]] if anchor_ids else None,
                    "attention_weight": prop_weights[i].item(),
                }
                for i in topk_indices
            ]

            results.append(
                {"property_idx": prop_idx.item(), "top_anchors": top_anchors}
            )

        return results


def create_s2hgt_from_data(data: "HeteroData", hidden_dim: int = 128) -> S2HGT:
    """
    Factory function to create S2-HGT model from HeteroData.

    Automatically infers feature dimensions and metadata.
    """
    node_feature_dims = {}
    for node_type in data.node_types:
        if hasattr(data[node_type], "x"):
            node_feature_dims[node_type] = data[node_type].x.size(1)

    metadata = data.metadata()

    model = S2HGT(
        node_feature_dims=node_feature_dims,
        hidden_dim=hidden_dim,
        metadata=metadata,
    )

    return model


class S2HGTLoss(nn.Module):
    """
    Loss function for S2-HGT training.

    Uses Log-Cosh Loss: log(cosh(pred - target))
    - Smooth like MSE for small errors
    - Linear like MAE for large errors (robust to outliers)
    - More numerically stable than Huber+MAPE combo
    """

    def __init__(self, scale: float = 1.0):
        super().__init__()
        self.scale = scale

    def forward(
        self,
        predictions: torch.Tensor,
        targets: torch.Tensor,
        source_type: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """
        Compute Log-Cosh loss with source-aware weighting.
        """
        diff = predictions - targets

        # Log-Cosh: numerically stable version
        # log(cosh(x)) = x + softplus(-2x) - log(2)
        loss = torch.mean(diff + F.softplus(-2.0 * diff) - math.log(2.0))

        # Source-aware weighting disabled - was causing early stopping issues
        # Keep simple Log-Cosh loss for stability
        if source_type is not None:
            # Just track per-source metrics for monitoring
            pass

        return loss * self.scale
