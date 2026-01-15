"""
Build Subset S2-HGT Graph for Fast Iteration.

Creates a small heterogeneous graph (~5K properties) for rapid training iteration.
Ensures balanced sampling across districts, source types, and floor data availability.

Usage:
    python -m scripts.build_subset_graph --output data/s2_hetero_graph_subset.pt --sample 5000
"""

import argparse
import logging
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import torch
from sqlalchemy import text
from src.config.database import engine

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

try:
    from torch_geometric.data import HeteroData

    HAS_PYG = True
except ImportError:
    HAS_PYG = False
    logger.error("torch_geometric required")

# Constants
H3_RESOLUTION = 9
SOURCE_TREASURY = 0
SOURCE_LISTING = 1


def fetch_treasury_properties(engine, sample: int | None = None) -> pd.DataFrame:
    """Fetch Treasury appraisal properties."""
    query = """
    SELECT 
        id,
        building_area,
        land_area,
        building_age,
        no_of_floor,
        building_style_desc,
        total_price,
        amphur as district,
        ST_X(geometry::geometry) as lon,
        ST_Y(geometry::geometry) as lat
    FROM house_prices
    WHERE geometry IS NOT NULL 
      AND total_price > 0 
      AND building_area > 0
    """
    if sample:
        query += f" ORDER BY RANDOM() LIMIT {sample}"

    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)

    df["source_type"] = SOURCE_TREASURY
    df["h3_index"] = df.apply(
        lambda r: h3.latlng_to_cell(r["lat"], r["lon"], H3_RESOLUTION), axis=1
    )

    # Floor missing flag (keep before imputation)
    df["floor_missing"] = df["no_of_floor"].isna().astype(int)

    # Impute missing floors with median by building style
    # Houses typically 2 floors, Condos typically 8-12 floors
    floor_medians = {
        "บ้านเดี่ยว": 2,
        "บ้านแฝด": 2,
        "ทาวน์เฮ้าส์": 3,
        "ทาวน์โฮม": 3,
        "คอนโด": 10,
        "อาคารพาณิชย์": 4,
    }
    df["no_of_floor"] = df.apply(
        lambda r: floor_medians.get(r["building_style_desc"], 2)
        if pd.isna(r["no_of_floor"])
        else r["no_of_floor"],
        axis=1,
    )

    logger.info(f"Fetched {len(df)} Treasury properties (2023+)")
    return df


def fetch_listing_properties(engine, sample: int | None = None) -> pd.DataFrame:
    """Fetch listing properties from real_estate_listings with deduplication."""
    # Cast varchar columns to numeric, extract from geometry
    # Use subquery for DISTINCT ON, then sample from result
    # Filter: 500K < price < 50M THB to exclude outliers and invalid data
    limit_clause = f"LIMIT {sample}" if sample else ""
    query = f"""
    SELECT * FROM (
        SELECT DISTINCT ON (
            ST_X(geometry::geometry), 
            ST_Y(geometry::geometry), 
            CAST(REPLACE(REPLACE(price, ',', ''), ' THB', '') AS NUMERIC)
        )
            id,
            NULLIF(usable_area_sqm, '')::NUMERIC as building_area,
            NULLIF(land_size_sqw, '')::NUMERIC * 4 as land_area,
            0 as building_age,
            NULLIF(floors, '')::INTEGER as no_of_floor,
            property_type as building_style_desc,
            CAST(REPLACE(REPLACE(price, ',', ''), ' THB', '') AS NUMERIC) as total_price,
            location as district,
            ST_X(geometry::geometry) as lon,
            ST_Y(geometry::geometry) as lat
        FROM real_estate_listings
        WHERE geometry IS NOT NULL
          AND price IS NOT NULL
          AND price != ''
          AND CAST(REPLACE(REPLACE(price, ',', ''), ' THB', '') AS NUMERIC) > 500000
          AND CAST(REPLACE(REPLACE(price, ',', ''), ' THB', '') AS NUMERIC) < 50000000
        ORDER BY ST_X(geometry::geometry), ST_Y(geometry::geometry), 
                 CAST(REPLACE(REPLACE(price, ',', ''), ' THB', '') AS NUMERIC)
    ) AS deduped
    ORDER BY RANDOM()
    {limit_clause}
    """

    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)

        df["source_type"] = SOURCE_LISTING
        df["h3_index"] = df.apply(
            lambda r: h3.latlng_to_cell(r["lat"], r["lon"], H3_RESOLUTION), axis=1
        )
        df["floor_missing"] = df["no_of_floor"].isna().astype(int)

        # Impute missing floors by property type
        def get_median_floor(row):
            if pd.notna(row["no_of_floor"]):
                return row["no_of_floor"]
            prop_type = str(row.get("building_style_desc", "")).lower()
            if "condo" in prop_type:
                return 10
            if "town" in prop_type:
                return 3
            if "land" in prop_type:
                return 1
            return 2  # Default for houses

        df["no_of_floor"] = df.apply(get_median_floor, axis=1)

        logger.info(f"Fetched {len(df)} listing properties")
        return df
    except Exception as e:
        logger.warning(f"Listing fetch failed: {e}")
        return pd.DataFrame()


def load_anchor_nodes(anchors_path: Path) -> pd.DataFrame:
    """Load Tier-1 anchor nodes."""
    if not anchors_path.exists():
        logger.warning(f"Anchor file not found: {anchors_path}")
        return pd.DataFrame()

    df = pd.read_parquet(anchors_path)
    df = df[df["tier"] == 1]
    logger.info(f"Loaded {len(df)} anchor nodes")
    return df


def load_precomputed_edges(edges_path: Path) -> pd.DataFrame:
    """Load pre-computed house-anchor edges."""
    if not edges_path.exists():
        logger.warning(f"Edges file not found: {edges_path}")
        return pd.DataFrame()

    df = pd.read_parquet(edges_path)
    logger.info(f"Loaded {len(df)} pre-computed edges")
    return df


def stratified_sample(
    df: pd.DataFrame, n: int, stratify_cols: list[str]
) -> pd.DataFrame:
    """Stratified sampling ensuring representation across groups."""
    # Create stratification key
    strat_key = df[stratify_cols].astype(str).agg("_".join, axis=1)
    groups = strat_key.unique()

    samples_per_group = max(1, n // len(groups))
    sampled = []

    for group in groups:
        group_df = df[strat_key == group]
        n_sample = min(len(group_df), samples_per_group)
        sampled.append(group_df.sample(n=n_sample, random_state=42))

    result = pd.concat(sampled, ignore_index=True)

    # If we need more samples, randomly add
    if len(result) < n:
        remaining = df[~df.index.isin(result.index)]
        extra = remaining.sample(
            n=min(n - len(result), len(remaining)), random_state=42
        )
        result = pd.concat([result, extra], ignore_index=True)

    return result.head(n)


def encode_building_style(style: str | None) -> int:
    """Encode building style to integer."""
    style_map = {
        "บ้านเดี่ยว": 0,
        "ทาวน์เฮ้าส์": 1,
        "บ้านแฝด": 2,
        "อาคารพาณิชย์": 3,
        "ตึกแถว": 4,
        "คอนโด": 5,
        "house": 0,
        "townhome": 1,
        "apartment": 5,
    }
    if style is None:
        return 0
    return style_map.get(style.lower(), 0)


def build_subset_graph(
    properties_df: pd.DataFrame,
    anchors_df: pd.DataFrame,
    edges_df: pd.DataFrame,
) -> "HeteroData":
    """Build HeteroData object from subset data."""
    data = HeteroData()

    # Reset indices
    properties_df = properties_df.reset_index(drop=True)
    prop_id_to_idx = {pid: idx for idx, pid in enumerate(properties_df["id"])}

    # ====== Property Node Features ======
    # Features: [building_area, land_area, building_age, no_of_floor, style_encoded]
    properties_df["building_style_encoded"] = properties_df[
        "building_style_desc"
    ].apply(encode_building_style)

    prop_features = (
        properties_df[
            [
                "building_area",
                "land_area",
                "building_age",
                "no_of_floor",
                "building_style_encoded",
            ]
        ]
        .fillna(0)
        .values.astype(np.float32)
    )

    # Log-transform price for target, then standardize for faster convergence
    log_prices = np.log1p(properties_df["total_price"].values).astype(np.float32)
    price_log_mean = float(log_prices.mean())
    price_log_std = float(log_prices.std())
    prices_normalized = (log_prices - price_log_mean) / (price_log_std + 1e-8)

    data["property"].x = torch.tensor(prop_features, dtype=torch.float)
    data["property"].y = torch.tensor(prices_normalized, dtype=torch.float)
    data["property"].source_type = torch.tensor(
        properties_df["source_type"].values, dtype=torch.long
    )
    data["property"].floor_missing = torch.tensor(
        properties_df["floor_missing"].values, dtype=torch.long
    )
    data["property"].coords = torch.tensor(
        properties_df[["lat", "lon"]].values, dtype=torch.float
    )

    # Store price transform stats for inverse transform at inference
    data.price_log_mean = price_log_mean
    data.price_log_std = price_log_std
    data.price_raw_mean = float(properties_df["total_price"].mean())
    data.price_raw_std = float(properties_df["total_price"].std())

    logger.info(f"Property features: {data['property'].x.shape}")
    logger.info(
        f"Price transform: log_mean={price_log_mean:.4f}, log_std={price_log_std:.4f}"
    )

    # ====== Anchor Node Features ======
    if not anchors_df.empty:
        anchors_df = anchors_df.reset_index(drop=True)
        anchor_id_to_idx = {aid: idx for idx, aid in enumerate(anchors_df["id"])}

        # Simple features: category encoded
        category_map = {
            "transit": 0,
            "retail": 1,
            "cafe": 2,
            "restaurant": 3,
            "hospital": 4,
            "education": 5,
            "bank": 6,
            "fitness": 7,
        }
        anchors_df["category_encoded"] = (
            anchors_df["category"].map(category_map).fillna(8)
        )

        anchor_features = np.zeros((len(anchors_df), 2), dtype=np.float32)
        anchor_features[:, 0] = anchors_df["tier"].values
        anchor_features[:, 1] = anchors_df["category_encoded"].values

        data["anchor"].x = torch.tensor(anchor_features, dtype=torch.float)
        data["anchor"].coords = torch.tensor(
            anchors_df[["lat", "lon"]].values, dtype=torch.float
        )

        logger.info(f"Anchor features: {data['anchor'].x.shape}")

        # ====== Property -> Anchor Edges ======
        if not edges_df.empty:
            # Filter edges to our subset
            valid_edges = edges_df[
                edges_df["house_id"].isin(prop_id_to_idx)
                & edges_df["anchor_id"].isin(anchor_id_to_idx)
            ]

            if not valid_edges.empty:
                src = [prop_id_to_idx[hid] for hid in valid_edges["house_id"]]
                dst = [anchor_id_to_idx[aid] for aid in valid_edges["anchor_id"]]

                data["property", "access", "anchor"].edge_index = torch.tensor(
                    [src, dst], dtype=torch.long
                )
                data["property", "access", "anchor"].edge_attr = torch.tensor(
                    valid_edges["network_dist"].values, dtype=torch.float
                ).unsqueeze(1)

                # Add reverse edges for bidirectional message passing
                data["anchor", "rev_access", "property"].edge_index = torch.tensor(
                    [dst, src], dtype=torch.long
                )
                data["anchor", "rev_access", "property"].edge_attr = data[
                    "property", "access", "anchor"
                ].edge_attr.clone()

                logger.info(
                    f"Property->Anchor edges: {data['property', 'access', 'anchor'].edge_index.shape}"
                )
                logger.info(
                    f"Anchor->Property edges (reverse): {data['anchor', 'rev_access', 'property'].edge_index.shape}"
                )

    # ====== H3 Cell Nodes (optional) ======
    unique_h3 = properties_df["h3_index"].unique()
    h3_to_idx = {h: idx for idx, h in enumerate(unique_h3)}

    # H3 features: just count of properties per cell for now
    h3_counts = (
        properties_df.groupby("h3_index").size().reindex(unique_h3, fill_value=0)
    )
    h3_features = np.array(h3_counts.values, dtype=np.float32).reshape(-1, 1)

    data["h3_cell"].x = torch.tensor(h3_features, dtype=torch.float)

    # Property -> H3 Cell edges
    prop_h3_src = list(range(len(properties_df)))
    prop_h3_dst = [h3_to_idx[h] for h in properties_df["h3_index"]]
    data["property", "in_cell", "h3_cell"].edge_index = torch.tensor(
        [prop_h3_src, prop_h3_dst], dtype=torch.long
    )

    logger.info(f"H3 cells: {data['h3_cell'].x.shape}")

    # ====== H3 Adjacency Edges ======
    h3_adj_src = []
    h3_adj_dst = []
    for h3_idx in unique_h3:
        neighbors = h3.grid_disk(h3_idx, 1)
        for neighbor in neighbors:
            if neighbor != h3_idx and neighbor in h3_to_idx:
                h3_adj_src.append(h3_to_idx[h3_idx])
                h3_adj_dst.append(h3_to_idx[neighbor])

    if h3_adj_src:
        data["h3_cell", "adjacent", "h3_cell"].edge_index = torch.tensor(
            [h3_adj_src, h3_adj_dst], dtype=torch.long
        )
        logger.info(f"H3 adjacency edges: {len(h3_adj_src)}")

    # Store metadata
    data.property_ids = properties_df["id"].tolist()
    if not anchors_df.empty:
        data.anchor_ids = anchors_df["id"].tolist()

    return data


def main():
    parser = argparse.ArgumentParser(description="Build subset S2-HGT graph")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/s2_hetero_graph_subset.pt"),
        help="Output graph file",
    )
    parser.add_argument(
        "--anchors-path",
        type=Path,
        default=Path("data/anchor_nodes.parquet"),
        help="Anchor nodes file",
    )
    parser.add_argument(
        "--edges-path",
        type=Path,
        default=Path("data/house_anchor_edges.parquet"),
        help="Pre-computed edges file (optional)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=5000,
        help="Number of properties to sample",
    )
    parser.add_argument(
        "--treasury-ratio",
        type=float,
        default=0.7,
        help="Ratio of Treasury vs Listing properties",
    )
    args = parser.parse_args()

    # Fetch properties
    treasury_sample = int(args.sample * args.treasury_ratio)
    listing_sample = args.sample - treasury_sample

    treasury_df = fetch_treasury_properties(engine, sample=treasury_sample * 2)
    listing_df = fetch_listing_properties(engine, sample=listing_sample * 2)

    # Stratified sampling
    if not treasury_df.empty:
        treasury_df = stratified_sample(
            treasury_df, treasury_sample, ["district", "floor_missing"]
        )
    if not listing_df.empty:
        listing_df = stratified_sample(
            listing_df, listing_sample, ["district", "floor_missing"]
        )

    # Combine
    if not listing_df.empty:
        # Align columns
        common_cols = [
            "id",
            "building_area",
            "land_area",
            "building_age",
            "no_of_floor",
            "building_style_desc",
            "total_price",
            "district",
            "lon",
            "lat",
            "source_type",
            "h3_index",
            "floor_missing",
        ]
        treasury_df = treasury_df[[c for c in common_cols if c in treasury_df.columns]]
        listing_df = listing_df[[c for c in common_cols if c in listing_df.columns]]
        properties_df = pd.concat([treasury_df, listing_df], ignore_index=True)
    else:
        properties_df = treasury_df

    logger.info(f"Total properties: {len(properties_df)}")
    logger.info(
        f"  Treasury: {(properties_df['source_type'] == SOURCE_TREASURY).sum()}"
    )
    logger.info(f"  Listing: {(properties_df['source_type'] == SOURCE_LISTING).sum()}")
    logger.info(f"  Floor missing: {properties_df['floor_missing'].sum()}")

    # Load anchors and edges
    anchors_df = load_anchor_nodes(args.anchors_path)
    edges_df = load_precomputed_edges(args.edges_path)

    # Build graph
    data = build_subset_graph(properties_df, anchors_df, edges_df)

    # Save
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(data, args.output)
    logger.info(f"Saved graph to {args.output}")

    # Summary
    logger.info("\n=== Graph Summary ===")
    logger.info(f"Node types: {data.node_types}")
    logger.info(f"Edge types: {data.edge_types}")
    for nt in data.node_types:
        if hasattr(data[nt], "x"):
            logger.info(f"  {nt}: {data[nt].x.shape}")


if __name__ == "__main__":
    main()
