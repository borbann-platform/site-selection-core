#!/usr/bin/env python
"""Analyze listing outliers and calculate robust metrics."""

import numpy as np
import torch
from src.models.s2_hgt import create_s2hgt_from_data

data = torch.load("data/s2_hetero_graph_subset.pt", weights_only=False)
y = data["property"].y.numpy()
source = data["property"].source_type.numpy()

# Use stored normalization params
log_mean = getattr(data, "price_log_mean", 15.1)
log_std = getattr(data, "price_log_std", 0.7)
print(f"Normalization: log_mean={log_mean:.3f}, log_std={log_std:.3f}")


def to_thb(y_norm):
    """Convert normalized target to THB using expm1."""
    log_price = y_norm * log_std + log_mean
    return np.expm1(log_price)  # exp(x) - 1, inverse of log1p


# Load trained model
model = create_s2hgt_from_data(data)
state = torch.load("models/s2hgt/s2hgt_model.pt", weights_only=False)
model.load_state_dict(state)
model.eval()

# Prepare data
x_dict = {node_type: data[node_type].x for node_type in data.node_types}
edge_index_dict = {
    edge_type: data[edge_type].edge_index for edge_type in data.edge_types
}
source_type = data["property"].source_type

with torch.no_grad():
    preds = model(x_dict, edge_index_dict, source_type=source_type).numpy()

# Convert to THB
pred_thb = to_thb(preds)
true_thb = to_thb(y)

# Calculate MAPE for listings excluding outliers
listing_mask = source == 1
listing_y = y[listing_mask]
extreme_mask = np.abs(listing_y) > 3

# Full listing MAPE
true_safe = np.maximum(true_thb[listing_mask], 1.0)
ape_all = np.abs(pred_thb[listing_mask] - true_thb[listing_mask]) / true_safe
print(f"\nFull Listing MAPE: {100 * ape_all.mean():.1f}%")

# Robust MAPE (excluding outliers)
normal_idx = np.where(listing_mask)[0][~extreme_mask]
true_safe_normal = np.maximum(true_thb[normal_idx], 1.0)
ape_robust = np.abs(pred_thb[normal_idx] - true_thb[normal_idx]) / true_safe_normal
print(f"Robust Listing MAPE (excl |z|>3): {100 * ape_robust.mean():.1f}%")

# Outlier stats
outlier_idx = np.where(listing_mask)[0][extreme_mask]
true_safe_outlier = np.maximum(true_thb[outlier_idx], 1.0)
ape_outliers = np.abs(pred_thb[outlier_idx] - true_thb[outlier_idx]) / true_safe_outlier
print(f"Outlier MAPE: {100 * ape_outliers.mean():.1f}%")
print(
    f"Outliers: n={len(outlier_idx)}, {true_thb[outlier_idx].min() / 1e6:.0f}M - {true_thb[outlier_idx].max() / 1e6:.0f}M THB"
)

# Treasury for comparison
treasury_mask = source == 0
true_safe_t = np.maximum(true_thb[treasury_mask], 1.0)
ape_t = np.abs(pred_thb[treasury_mask] - true_thb[treasury_mask]) / true_safe_t
print(f"\nTreasury MAPE: {100 * ape_t.mean():.1f}%")
