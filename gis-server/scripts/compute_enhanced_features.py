#!/usr/bin/env python3
"""
Compute enhanced features for property price prediction.

This script adds:
1. Nearest distance to specific POI types (school, hospital, park, mall, university, police)
2. Density features (POI counts normalized by H3 area)
3. Amenity composition features (essential vs lifestyle counts, diversity index)
4. Market context features (local price stats, computed fold-safe)

All features are computed in a leakage-safe manner for cross-validation.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import h3
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.model_selection import GroupKFold

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
H3_FEATURES_PATH = DATA_DIR / "h3_features" / "h3_features_res9.parquet"
H3_AREA_KM2 = 0.105  # Approximate area of H3 res9 hexagon in km²

POI_CATEGORIES = {
    "essential": ["poi_school", "poi_hospital", "poi_supermarket", "poi_transit_stop"],
    "lifestyle": ["poi_mall", "poi_restaurant", "poi_cafe", "poi_park"],
    "education": ["poi_school", "poi_university"],
    "health": ["poi_hospital"],
    "transit": ["poi_transit_stop", "poi_bus_shelter", "poi_water_transport"],
}

POI_DISTANCE_TYPES = [
    "poi_school",
    "poi_hospital",
    "poi_park",
    "poi_mall",
    "poi_university",
    "poi_police_station",
]


def load_h3_features_with_coords() -> pd.DataFrame:
    """Load H3 features with centroid coordinates."""
    df = pd.read_parquet(H3_FEATURES_PATH)
    logger.info(f"Loaded H3 features: {df.shape}")
    return df


def compute_nearest_poi_distances(
    properties: pd.DataFrame,
    h3_features: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute nearest distance to specific POI types for each property.

    Uses H3 centroids with non-zero POI counts as POI locations.
    Distance is Euclidean converted to km (approximate).
    """
    result = properties.copy()
    prop_coords = np.radians(properties[["lat", "lon"]].values)

    for poi_type in POI_DISTANCE_TYPES:
        if poi_type not in h3_features.columns:
            logger.warning(f"POI type {poi_type} not in H3 features, skipping")
            result[f"dist_to_{poi_type.replace('poi_', '')}"] = np.nan
            continue

        poi_mask = h3_features[poi_type] > 0
        if poi_mask.sum() == 0:
            logger.warning(f"No {poi_type} found in H3 features")
            result[f"dist_to_{poi_type.replace('poi_', '')}"] = np.nan
            continue

        poi_coords = np.radians(
            h3_features.loc[poi_mask, ["centroid_lat", "centroid_lon"]].values
        )
        tree = cKDTree(poi_coords)
        distances, _ = tree.query(prop_coords, k=1)
        result[f"dist_to_{poi_type.replace('poi_', '')}"] = distances * 6371.0

    logger.info(f"Computed nearest POI distances for {len(POI_DISTANCE_TYPES)} types")
    return result


def compute_density_features(
    properties: pd.DataFrame,
    h3_features: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute density features (POI counts per km²).

    Uses H3 area approximation for normalization.
    """
    result = properties.copy()

    h3_subset = h3_features[
        ["h3_index"] + [c for c in h3_features.columns if c.startswith("poi_")]
    ].copy()

    poi_count_cols = [
        c for c in h3_subset.columns if c.startswith("poi_") and c != "poi_total"
    ]

    for col in poi_count_cols:
        density_col = f"{col}_density"
        h3_subset[density_col] = h3_subset[col] / H3_AREA_KM2

    density_cols = [f"{c}_density" for c in poi_count_cols]
    merge_cols = ["h3_index"] + density_cols
    result = result.merge(h3_subset[merge_cols], on="h3_index", how="left")

    for col in density_cols:
        result[col] = result[col].fillna(0)

    logger.info(f"Computed {len(density_cols)} density features")
    return result


def compute_composition_features(
    properties: pd.DataFrame,
    h3_features: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute amenity composition features.

    - essential_amenity_count: school + hospital + supermarket + transit
    - lifestyle_amenity_count: mall + restaurant + cafe + park
    - poi_diversity_index: Shannon entropy of POI distribution
    """
    result = properties.copy()

    h3_subset = h3_features[["h3_index"]].copy()

    for category, poi_types in POI_CATEGORIES.items():
        available = [p for p in poi_types if p in h3_features.columns]
        if available:
            h3_subset[f"{category}_amenity_count"] = h3_features[available].sum(axis=1)
        else:
            h3_subset[f"{category}_amenity_count"] = 0

    poi_cols = [
        c for c in h3_features.columns if c.startswith("poi_") and c != "poi_total"
    ]
    if poi_cols:
        poi_counts = h3_features[poi_cols].values
        poi_totals = poi_counts.sum(axis=1, keepdims=True)
        poi_totals = np.maximum(poi_totals, 1)
        proportions = poi_counts / poi_totals
        entropy = -np.sum(proportions * np.log(proportions + 1e-10), axis=1)
        h3_subset["poi_diversity_index"] = entropy
    else:
        h3_subset["poi_diversity_index"] = 0

    merge_cols = (
        ["h3_index"]
        + [f"{cat}_amenity_count" for cat in POI_CATEGORIES.keys()]
        + ["poi_diversity_index"]
    )
    result = result.merge(h3_subset[merge_cols], on="h3_index", how="left")

    for col in merge_cols[1:]:
        result[col] = result[col].fillna(0)

    logger.info("Computed composition features")
    return result


def compute_accessibility_features(properties: pd.DataFrame) -> pd.DataFrame:
    """Compute travel-time proxy and accessibility score features."""
    result = properties.copy()

    # Approximate Bangkok speeds for simple travel-time proxies.
    drive_speed_kmh = 22.0
    transit_speed_kmh = 30.0

    if "dist_to_cbd_min" in result.columns:
        result["drive_time_to_cbd_min"] = (
            result["dist_to_cbd_min"].clip(lower=0.0) / drive_speed_kmh * 60.0
        )

    if "dist_to_bts" in result.columns:
        result["transit_time_to_bts_min"] = (
            result["dist_to_bts"].clip(lower=0.0) / transit_speed_kmh * 60.0
        )

    score_inputs: list[pd.Series] = []
    for col in [
        "dist_to_bts",
        "dist_to_school",
        "dist_to_hospital",
        "dist_to_park",
        "dist_to_mall",
    ]:
        if col in result.columns:
            score_inputs.append(1.0 / (1.0 + result[col].clip(lower=0.0)))

    if score_inputs:
        score_matrix = np.vstack(
            [series.to_numpy(dtype=float) for series in score_inputs]
        )
        result["accessibility_score"] = score_matrix.mean(axis=0)
    else:
        result["accessibility_score"] = 0.0

    logger.info("Computed accessibility proxy features")
    return result


def compute_market_context_features(
    df: pd.DataFrame,
    fold_col: str = "fold",
    group_col: str = "h3_index",
    forward_chaining: bool = False,
) -> pd.DataFrame:
    """
    Compute market context features in a fold-safe manner.

    For each fold, computes:
    - local_price_median_h3: median price in same H3 (from train folds only)
    - local_price_iqr_h3: price IQR in same H3 (from train folds only)
    - price_vs_local: property price vs local median

    IMPORTANT: Stats are computed only from training data for each fold.
    """
    result = df.copy()

    if fold_col not in df.columns:
        logger.warning(f"No fold column {fold_col} found, skipping market context")
        result["local_price_median_h3"] = np.nan
        result["local_price_iqr_h3"] = np.nan
        result["price_vs_local"] = 0
        return result

    result["local_price_median_h3"] = np.nan
    result["local_price_iqr_h3"] = np.nan
    result["price_vs_local"] = 0.0

    folds = sorted(df[fold_col].unique())
    logger.info(f"Computing market context features across {len(folds)} folds")

    for fold in folds:
        train_mask = (
            (df[fold_col] < fold) if forward_chaining else (df[fold_col] != fold)
        )
        val_mask = df[fold_col] == fold

        train_data = df[train_mask]
        val_data = df[val_mask]

        h3_stats = (
            train_data.groupby(group_col)["target_price_thb"]
            .agg(local_median="median", local_q75=lambda x: x.quantile(0.75))
            .reset_index()
        )

        h3_q25 = (
            train_data.groupby(group_col)["target_price_thb"]
            .quantile(0.25)
            .reset_index(name="local_q25")
        )
        h3_stats = h3_stats.merge(h3_q25, on=group_col, how="left")
        h3_stats["local_iqr"] = h3_stats["local_q75"] - h3_stats["local_q25"]

        val_merged = val_data.merge(
            h3_stats[[group_col, "local_median", "local_iqr"]],
            on=group_col,
            how="left",
        )

        val_indices = df[fold_col] == fold
        result.loc[val_indices, "local_price_median_h3"] = val_merged[
            "local_median"
        ].values
        result.loc[val_indices, "local_price_iqr_h3"] = val_merged["local_iqr"].values

        valid_mask = val_indices & result["local_price_median_h3"].notna()
        result.loc[valid_mask, "price_vs_local"] = (
            result.loc[valid_mask, "target_price_thb"]
            / result.loc[valid_mask, "local_price_median_h3"]
            - 1.0
        )

    global_median = df["target_price_thb"].median()
    result["local_price_median_h3"] = result["local_price_median_h3"].fillna(
        global_median
    )
    result["local_price_iqr_h3"] = result["local_price_iqr_h3"].fillna(0)
    result["price_vs_local"] = result["price_vs_local"].fillna(0)

    logger.info("Computed market context features (fold-safe)")
    return result


def add_enhanced_features(
    df: pd.DataFrame,
    compute_distances: bool = True,
    compute_density: bool = True,
    compute_composition: bool = True,
    compute_market: bool = True,
    fold_col: str = "fold",
) -> pd.DataFrame:
    """
    Add all enhanced features to the dataset.

    Parameters:
    -----------
    df : pd.DataFrame
        Input dataframe with property data (must have lat, lon, h3_index, target_price_thb)
    compute_distances : bool
        Whether to compute nearest POI distance features
    compute_density : bool
        Whether to compute density features
    compute_composition : bool
        Whether to compute composition features
    compute_market : bool
        Whether to compute market context features (requires fold column)
    fold_col : str
        Column name for fold assignment (for leakage-safe market features)

    Returns:
    --------
    pd.DataFrame with all enhanced features added
    """
    result = df.copy()

    if "h3_index" not in result.columns:
        logger.info("Computing H3 index from lat/lon")
        result["h3_index"] = result.apply(
            lambda row: h3.latlng_to_cell(row["lat"], row["lon"], 9), axis=1
        )

    h3_features = load_h3_features_with_coords()

    if compute_distances:
        result = compute_nearest_poi_distances(result, h3_features)

    if compute_density:
        result = compute_density_features(result, h3_features)

    if compute_composition:
        result = compute_composition_features(result, h3_features)

    result = compute_accessibility_features(result)

    if compute_market and fold_col in result.columns:
        result = compute_market_context_features(result, fold_col=fold_col)

    new_feature_cols = []
    if compute_distances:
        new_feature_cols.extend(
            [f"dist_to_{t.replace('poi_', '')}" for t in POI_DISTANCE_TYPES]
        )
    if compute_density:
        new_feature_cols.extend(
            [
                f"{c}_density"
                for c in h3_features.columns
                if c.startswith("poi_") and c != "poi_total"
            ]
        )
    if compute_composition:
        new_feature_cols.extend(
            [f"{cat}_amenity_count" for cat in POI_CATEGORIES.keys()]
            + ["poi_diversity_index"]
        )
    if compute_market:
        new_feature_cols.extend(
            ["local_price_median_h3", "local_price_iqr_h3", "price_vs_local"]
        )
    new_feature_cols.extend(
        ["drive_time_to_cbd_min", "transit_time_to_bts_min", "accessibility_score"]
    )

    new_feature_cols = [c for c in new_feature_cols if c in result.columns]

    logger.info(f"Added {len(new_feature_cols)} enhanced features")
    return result, new_feature_cols


def get_enhanced_feature_columns() -> list[str]:
    """Return list of all enhanced feature column names."""
    features = []

    features.extend([f"dist_to_{t.replace('poi_', '')}" for t in POI_DISTANCE_TYPES])

    h3_df = pd.read_parquet(H3_FEATURES_PATH)
    poi_cols = [c for c in h3_df.columns if c.startswith("poi_") and c != "poi_total"]
    features.extend([f"{c}_density" for c in poi_cols])

    features.extend([f"{cat}_amenity_count" for cat in POI_CATEGORIES.keys()])
    features.append("poi_diversity_index")

    features.extend(["local_price_median_h3", "local_price_iqr_h3", "price_vs_local"])
    features.extend(
        ["drive_time_to_cbd_min", "transit_time_to_bts_min", "accessibility_score"]
    )

    return features


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compute enhanced features")
    parser.add_argument("--input", required=True, help="Input parquet file")
    parser.add_argument("--output", required=True, help="Output parquet file")
    parser.add_argument(
        "--no-distances", action="store_true", help="Skip distance features"
    )
    parser.add_argument(
        "--no-density", action="store_true", help="Skip density features"
    )
    parser.add_argument(
        "--no-composition", action="store_true", help="Skip composition features"
    )
    parser.add_argument(
        "--no-market", action="store_true", help="Skip market context features"
    )
    parser.add_argument("--fold-col", default="fold", help="Fold column name")

    args = parser.parse_args()

    df = pd.read_parquet(args.input)
    logger.info(f"Loaded {len(df)} rows from {args.input}")

    result, new_cols = add_enhanced_features(
        df,
        compute_distances=not args.no_distances,
        compute_density=not args.no_density,
        compute_composition=not args.no_composition,
        compute_market=not args.no_market,
        fold_col=args.fold_col,
    )

    result.to_parquet(args.output, index=False)
    logger.info(
        f"Saved {len(result)} rows with {len(new_cols)} new features to {args.output}"
    )
    logger.info(f"New features: {new_cols}")
