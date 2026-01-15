#!/usr/bin/env python
"""Compare prediction distributions."""

import torch
from src.models.s2_hgt import create_s2hgt_from_data

data = torch.load("data/s2_hetero_graph_subset.pt", weights_only=False)
model = create_s2hgt_from_data(data)
state = torch.load("models/s2hgt/s2hgt_model.pt", weights_only=False)
model.load_state_dict(state)
model.eval()

x_dict = {node_type: data[node_type].x for node_type in data.node_types}
edge_index_dict = {
    edge_type: data[edge_type].edge_index for edge_type in data.edge_types
}
source_type = data["property"].source_type
y = data["property"].y.numpy()

with torch.no_grad():
    preds = model(x_dict, edge_index_dict, source_type=source_type).numpy()

source = source_type.numpy()
print("Predictions (normalized):")
print(
    f"  Treasury: mean={preds[source == 0].mean():.3f}, std={preds[source == 0].std():.3f}"
)
print(
    f"  Listing: mean={preds[source == 1].mean():.3f}, std={preds[source == 1].std():.3f}"
)
print()
print("Targets (normalized):")
print(f"  Treasury: mean={y[source == 0].mean():.3f}, std={y[source == 0].std():.3f}")
print(f"  Listing: mean={y[source == 1].mean():.3f}, std={y[source == 1].std():.3f}")

# Gap analysis
pred_gap = preds[source == 1].mean() - preds[source == 0].mean()
target_gap = y[source == 1].mean() - y[source == 0].mean()
print()
print("Mean gap (Listing - Treasury):")
print(f"  Predicted: {pred_gap:.3f}")
print(f"  Target: {target_gap:.3f}")
print(f"  Ratio: {pred_gap / target_gap:.1%}")
