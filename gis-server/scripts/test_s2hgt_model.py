"""
Test S2-HGT model architecture with synthetic data.

Verifies:
- Model instantiation
- Forward pass with all features (source token, spatial encoding, anchor attention)
- Loss computation
- Attention extraction for explainability

Usage:
    python -m scripts.test_s2hgt_model
"""

import torch
from src.models.s2_hgt import S2HGT, S2HGTLoss
from torch_geometric.data import HeteroData


def create_synthetic_graph():
    """Create synthetic HeteroData for testing."""
    data = HeteroData()

    n_props = 100
    n_anchors = 20
    n_h3 = 30

    # Property nodes
    data["property"].x = torch.randn(n_props, 5)
    data["property"].y = torch.randn(n_props)
    data["property"].source_type = torch.randint(0, 2, (n_props,))
    data["property"].coords = torch.randn(n_props, 2) * 0.1 + torch.tensor(
        [13.75, 100.6]
    )

    # Anchor nodes
    data["anchor"].x = torch.randn(n_anchors, 2)
    data["anchor"].coords = torch.randn(n_anchors, 2) * 0.1 + torch.tensor(
        [13.75, 100.6]
    )

    # H3 cells
    data["h3_cell"].x = torch.randn(n_h3, 1)

    # Property -> H3 edges
    data["property", "in_cell", "h3_cell"].edge_index = torch.stack(
        [torch.arange(n_props), torch.randint(0, n_h3, (n_props,))]
    )

    # H3 -> H3 adjacency
    n_h3_edges = 60
    data["h3_cell", "adjacent", "h3_cell"].edge_index = torch.stack(
        [torch.randint(0, n_h3, (n_h3_edges,)), torch.randint(0, n_h3, (n_h3_edges,))]
    )

    # Property -> Anchor edges with network distance
    n_access_edges = 200
    data["property", "access", "anchor"].edge_index = torch.stack(
        [
            torch.randint(0, n_props, (n_access_edges,)),
            torch.randint(0, n_anchors, (n_access_edges,)),
        ]
    )
    data["property", "access", "anchor"].edge_attr = (
        torch.rand(n_access_edges, 1) * 2000
    )

    return data


def test_model():
    """Test S2-HGT model with synthetic data."""
    print("=== S2-HGT Model Architecture Test ===\n")

    # Create data
    data = create_synthetic_graph()
    print(f"Node types: {data.node_types}")
    print(f"Edge types: {data.edge_types}")

    # Create model
    node_feature_dims = {
        "property": 5,
        "anchor": 2,
        "h3_cell": 1,
    }
    metadata = data.metadata()

    model = S2HGT(
        node_feature_dims=node_feature_dims,
        hidden_dim=64,
        num_heads=4,
        num_layers=2,
        metadata=metadata,
    )

    total_params = sum(p.numel() for p in model.parameters())
    print(f"Model parameters: {total_params:,}")

    # Prepare inputs
    x_dict = {k: data[k].x for k in data.node_types}
    edge_index_dict = {k: data[k].edge_index for k in data.edge_types}
    edge_attr_dict = {
        ("property", "access", "anchor"): data["property", "access", "anchor"].edge_attr
    }
    source_type = data["property"].source_type
    coords_dict = {
        "property": data["property"].coords,
        "anchor": data["anchor"].coords,
    }

    # Forward pass
    predictions = model(
        x_dict,
        edge_index_dict,
        edge_attr_dict=edge_attr_dict,
        source_type=source_type,
        coords_dict=coords_dict,
        return_attention=True,
    )

    print(f"Predictions shape: {predictions.shape}")
    print(f"Prediction range: [{predictions.min():.2f}, {predictions.max():.2f}]")

    # Test loss
    criterion = S2HGTLoss(delta=0.5)
    targets = data["property"].y
    loss = criterion(predictions, targets, source_type)
    print(f"Loss: {loss.item():.4f}")

    # Test attention extraction
    top_anchors = model.get_top_k_anchor_attention(k=3)
    print(f"Top anchor attention extracted for {len(top_anchors)} properties")

    # Backward pass test
    loss.backward()
    print("Backward pass successful")

    print("\n✅ S2-HGT model architecture test PASSED!")
    return True


if __name__ == "__main__":
    test_model()
