"""
Build Heterogeneous Graph for Property Valuation.

Creates a PyTorch Geometric HeteroData object with multiple node types
(Property, Transit, FloodZone, Amenity) and typed edges representing
different spatial relationships.

Usage:
    python -m scripts.build_hetero_graph --output data/hetero_graph.pt
"""

import argparse
import logging
from pathlib import Path

import h3
import networkx as nx
import numpy as np
import pandas as pd
import torch
from sqlalchemy import text
from src.config.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Graph configuration
H3_RESOLUTION = 9
MAX_TRANSIT_DISTANCE_M = 1500  # Max distance for property-transit edges
MAX_AMENITY_DISTANCE_M = 1000  # Max distance for property-amenity edges
K_RING_NEIGHBORS = 1  # H3 adjacency ring

# Node type constants
NODE_PROPERTY = "property"
NODE_TRANSIT = "transit"
NODE_FLOOD = "flood_zone"
NODE_AMENITY = "amenity"
NODE_H3_CELL = "h3_cell"

# Edge type constants (source, relation, target)
EDGE_NEAR = "near"
EDGE_SERVED_BY = "served_by"
EDGE_IN_ZONE = "in_zone"
EDGE_ADJACENT = "adjacent"
EDGE_CONTAINS = "contains"


def load_h3_features(
    features_dir: Path, resolution: int = H3_RESOLUTION
) -> pd.DataFrame:
    """Load pre-computed H3 features."""
    path = features_dir / f"h3_features_res{resolution}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    logger.warning(f"H3 features not found at {path}")
    return pd.DataFrame()


def load_hex2vec_embeddings(
    models_dir: Path, resolution: int = H3_RESOLUTION
) -> pd.DataFrame:
    """Load pre-trained Hex2Vec embeddings."""
    path = models_dir / f"hex2vec_embeddings_res{resolution}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    logger.warning(f"Hex2Vec embeddings not found at {path}")
    return pd.DataFrame()


def fetch_properties(engine) -> pd.DataFrame:
    """Fetch properties with H3 indexing."""
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
    WHERE geometry IS NOT NULL AND total_price > 0
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)

    # Add H3 index
    df["h3_index"] = df.apply(
        lambda r: h3.latlng_to_cell(r["lat"], r["lon"], H3_RESOLUTION), axis=1
    )

    # Encode building style
    style_map = {
        "บ้านเดี่ยว": 0,
        "ทาวน์เฮ้าส์": 1,
        "บ้านแฝด": 2,
        "อาคารพาณิชย์": 3,
        "ตึกแถว": 4,
    }
    df["building_style_encoded"] = df["building_style_desc"].map(style_map).fillna(0)

    logger.info(f"Fetched {len(df)} properties")
    return df


def fetch_transit_stops(engine) -> pd.DataFrame:
    """Fetch transit stops with coordinates."""
    query = """
    SELECT 
        stop_id,
        stop_name,
        source,
        ST_X(geometry::geometry) as lon,
        ST_Y(geometry::geometry) as lat
    FROM transit_stops
    WHERE geometry IS NOT NULL
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)

    df["h3_index"] = df.apply(
        lambda r: h3.latlng_to_cell(r["lat"], r["lon"], H3_RESOLUTION), axis=1
    )

    logger.info(f"Fetched {len(df)} transit stops")
    return df


def fetch_amenities(engine) -> pd.DataFrame:
    """Fetch amenities from unified POI view."""
    query = """
    SELECT 
        name,
        type as poi_type,
        ST_X(geometry::geometry) as lon,
        ST_Y(geometry::geometry) as lat
    FROM view_all_pois
    WHERE geometry IS NOT NULL
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)

    df["h3_index"] = df.apply(
        lambda r: h3.latlng_to_cell(r["lat"], r["lon"], H3_RESOLUTION), axis=1
    )

    # Filter to key amenity types
    key_types = ["school", "hospital", "mall", "park", "university", "temple"]
    df = df[df["poi_type"].isin(key_types)]

    logger.info(f"Fetched {len(df)} key amenities")
    return df


def load_flood_risk(features_dir: Path) -> pd.DataFrame:
    """Load flood risk by district."""
    path = features_dir / "flood_risk_by_district.parquet"
    if path.exists():
        return pd.read_parquet(path)
    logger.warning("Flood risk data not found")
    return pd.DataFrame()


def compute_transit_centrality(
    transit_df: pd.DataFrame, graph_path: Path | None = None
) -> pd.DataFrame:
    """
    Compute network centrality for transit stops.

    Uses PageRank on transit network graph. If bangkok_graph.graphml available,
    also computes betweenness centrality on street network.
    """
    transit_df = transit_df.copy()

    # Build simple transit network graph
    # Connect stops that are within same route (approximated by source + proximity)
    G = nx.Graph()

    for _, row in transit_df.iterrows():
        G.add_node(row["stop_id"], source=row["source"])

    # Connect nearby stops (same source = same transit line)
    for source in transit_df["source"].unique():
        source_stops = transit_df[transit_df["source"] == source]
        stop_ids = source_stops["stop_id"].tolist()
        # Connect sequential stops (assuming ordered by stop_id)
        for i in range(len(stop_ids) - 1):
            G.add_edge(stop_ids[i], stop_ids[i + 1])

    # Compute PageRank
    if len(G.edges) > 0:
        pagerank = nx.pagerank(G)
        transit_df["pagerank"] = transit_df["stop_id"].map(pagerank)
    else:
        transit_df["pagerank"] = 0.0

    # Compute degree (number of connections = interchange indicator)
    degree = dict(G.degree())
    transit_df["degree"] = transit_df["stop_id"].map(degree).fillna(0)

    # Mark interchanges (high degree or multiple sources nearby)
    transit_df["is_interchange"] = transit_df["degree"] > 2

    logger.info(f"Computed centrality for {len(transit_df)} stops")
    logger.info(f"Interchanges identified: {transit_df['is_interchange'].sum()}")

    return transit_df


def build_h3_adjacency(h3_cells: list) -> tuple:
    """
    Build H3 adjacency edge index.

    Connects each H3 cell to its k-ring neighbors.
    Returns (src, dst) edge index arrays.
    """
    cell_to_idx = {cell: i for i, cell in enumerate(h3_cells)}
    cell_set = set(h3_cells)

    src_nodes = []
    dst_nodes = []

    for cell in h3_cells:
        neighbors = h3.grid_disk(cell, K_RING_NEIGHBORS)
        cell_idx = cell_to_idx[cell]

        for neighbor in neighbors:
            if neighbor in cell_set and neighbor != cell:
                neighbor_idx = cell_to_idx[neighbor]
                src_nodes.append(cell_idx)
                dst_nodes.append(neighbor_idx)

    logger.info(f"Built H3 adjacency: {len(h3_cells)} cells, {len(src_nodes)} edges")
    return src_nodes, dst_nodes


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate haversine distance in meters."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)

    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def build_property_transit_edges(
    properties_df: pd.DataFrame,
    transit_df: pd.DataFrame,
    max_distance: float = MAX_TRANSIT_DISTANCE_M,
) -> tuple:
    """
    Build edges connecting properties to nearby transit stops.

    Edge weight = inverse distance (closer = stronger connection).
    """
    src_nodes = []
    dst_nodes = []
    edge_weights = []

    for prop_idx, prop_row in properties_df.iterrows():
        prop_lat, prop_lon = prop_row["lat"], prop_row["lon"]

        for transit_idx, transit_row in transit_df.iterrows():
            transit_lat, transit_lon = transit_row["lat"], transit_row["lon"]

            dist = haversine_distance(prop_lat, prop_lon, transit_lat, transit_lon)

            if dist < max_distance:
                src_nodes.append(prop_idx)
                dst_nodes.append(transit_idx)
                # Inverse distance weight (normalized)
                weight = 1.0 - (dist / max_distance)
                edge_weights.append(weight)

    logger.info(f"Built {len(src_nodes)} property-transit edges")
    return src_nodes, dst_nodes, edge_weights


def build_property_amenity_edges(
    properties_df: pd.DataFrame,
    amenities_df: pd.DataFrame,
    max_distance: float = MAX_AMENITY_DISTANCE_M,
) -> tuple:
    """
    Build edges connecting properties to nearby amenities.
    """
    src_nodes = []
    dst_nodes = []
    edge_weights = []

    for prop_idx, prop_row in properties_df.iterrows():
        prop_lat, prop_lon = prop_row["lat"], prop_row["lon"]

        for amen_idx, amen_row in amenities_df.iterrows():
            amen_lat, amen_lon = amen_row["lat"], amen_row["lon"]

            dist = haversine_distance(prop_lat, prop_lon, amen_lat, amen_lon)

            if dist < max_distance:
                src_nodes.append(prop_idx)
                dst_nodes.append(amen_idx)
                weight = 1.0 - (dist / max_distance)
                edge_weights.append(weight)

    logger.info(f"Built {len(src_nodes)} property-amenity edges")
    return src_nodes, dst_nodes, edge_weights


def build_property_flood_edges(
    properties_df: pd.DataFrame,
    flood_df: pd.DataFrame,
) -> tuple:
    """
    Build edges connecting properties to flood risk zones.

    TODO: Replace with H3-level flood zones when GISTDA API integrated.
    Currently uses district-level mapping.
    """
    if flood_df.empty:
        logger.warning("No flood data available")
        return [], [], []

    # Create district -> flood zone idx mapping
    flood_df = flood_df.reset_index(drop=True)
    district_to_flood = {row["district"]: idx for idx, row in flood_df.iterrows()}

    src_nodes = []
    dst_nodes = []
    risk_levels = []

    for prop_idx, prop_row in properties_df.iterrows():
        district = prop_row.get("district")
        if district and district in district_to_flood:
            flood_idx = district_to_flood[district]
            src_nodes.append(prop_idx)
            dst_nodes.append(flood_idx)
            # Risk level as edge attribute
            risk = flood_df.iloc[flood_idx]["risk_group"]
            risk_levels.append(risk)

    logger.info(f"Built {len(src_nodes)} property-flood edges")
    return src_nodes, dst_nodes, risk_levels


def prepare_node_features(
    properties_df: pd.DataFrame,
    transit_df: pd.DataFrame,
    amenities_df: pd.DataFrame,
    h3_features: pd.DataFrame,
    hex2vec_embeddings: pd.DataFrame,
) -> dict:
    """
    Prepare feature tensors for each node type.

    Cold-start handling:
    - Properties inherit H3 cell features + Hex2Vec embeddings
    - Missing embeddings filled with zeros (GNN will aggregate from neighbors)
    """
    node_features = {}

    # Property features
    prop_intrinsic = (
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
        .values
    )

    # Add H3 cell context features for each property
    if not h3_features.empty and not hex2vec_embeddings.empty:
        # Merge H3 features
        h3_feat_cols = [
            c
            for c in h3_features.columns
            if c.startswith("poi_") or c.startswith("transit_")
        ]
        emb_cols = [c for c in hex2vec_embeddings.columns if c.startswith("emb_")]

        prop_context = []
        for _, row in properties_df.iterrows():
            h3_idx = row["h3_index"]

            # Get H3 features
            h3_row = h3_features[h3_features["h3_index"] == h3_idx]
            if not h3_row.empty:
                h3_vals = h3_row[h3_feat_cols].values[0]
            else:
                h3_vals = np.zeros(len(h3_feat_cols))

            # Get Hex2Vec embedding
            emb_row = hex2vec_embeddings[hex2vec_embeddings["h3_index"] == h3_idx]
            if not emb_row.empty:
                emb_vals = emb_row[emb_cols].values[0]
            else:
                # Cold-start: zero embedding
                emb_vals = np.zeros(len(emb_cols))

            prop_context.append(np.concatenate([h3_vals, emb_vals]))

        prop_context = np.array(prop_context)
        prop_features = np.hstack([prop_intrinsic, prop_context])
    else:
        prop_features = prop_intrinsic

    node_features[NODE_PROPERTY] = torch.tensor(prop_features, dtype=torch.float)

    # Transit features
    transit_features = transit_df[["pagerank", "degree"]].fillna(0).values
    # Add source encoding (BTS=0, MRT=1, Bus=2, etc.)
    source_map = {"bangkok_gtfs": 0, "longdomap_bus": 1}
    transit_source = (
        transit_df["source"].map(source_map).fillna(2).values.reshape(-1, 1)
    )
    transit_interchange = (
        transit_df["is_interchange"].astype(float).values.reshape(-1, 1)
    )
    transit_features = np.hstack(
        [transit_features, transit_source, transit_interchange]
    )
    node_features[NODE_TRANSIT] = torch.tensor(transit_features, dtype=torch.float)

    # Amenity features
    # One-hot encode amenity type
    amenity_types = ["school", "hospital", "mall", "park", "university", "temple"]
    amenity_onehot = (
        pd.get_dummies(amenities_df["poi_type"])
        .reindex(columns=amenity_types, fill_value=0)
        .astype(np.float32)
        .values
    )
    node_features[NODE_AMENITY] = torch.tensor(amenity_onehot, dtype=torch.float)

    logger.info(f"Property features: {node_features[NODE_PROPERTY].shape}")
    logger.info(f"Transit features: {node_features[NODE_TRANSIT].shape}")
    logger.info(f"Amenity features: {node_features[NODE_AMENITY].shape}")

    return node_features


def build_hetero_data(
    properties_df: pd.DataFrame,
    transit_df: pd.DataFrame,
    amenities_df: pd.DataFrame,
    flood_df: pd.DataFrame,
    h3_features: pd.DataFrame,
    hex2vec_embeddings: pd.DataFrame,
):
    """
    Build PyTorch Geometric HeteroData object.
    """
    # Import here to handle optional dependency gracefully
    try:
        from torch_geometric.data import HeteroData
    except ImportError:
        logger.error("torch_geometric not installed. Run: pip install torch-geometric")
        raise

    data = HeteroData()

    # Reset indices for proper edge indexing
    properties_df = properties_df.reset_index(drop=True)
    transit_df = transit_df.reset_index(drop=True)
    amenities_df = amenities_df.reset_index(drop=True)

    # Prepare node features
    node_features = prepare_node_features(
        properties_df, transit_df, amenities_df, h3_features, hex2vec_embeddings
    )

    # Add node features
    data[NODE_PROPERTY].x = node_features[NODE_PROPERTY]
    data[NODE_TRANSIT].x = node_features[NODE_TRANSIT]
    data[NODE_AMENITY].x = node_features[NODE_AMENITY]

    # Add target labels (price) for properties
    data[NODE_PROPERTY].y = torch.tensor(
        properties_df["total_price"].values, dtype=torch.float
    )

    # Mark cold-start nodes (properties in cells with no prior transactions)
    if not h3_features.empty:
        cold_start_cells = set(
            h3_features[h3_features.get("is_cold_start", False) == True]["h3_index"]
        )
        is_cold_start = properties_df["h3_index"].isin(cold_start_cells).values
        data[NODE_PROPERTY].cold_start_mask = torch.tensor(
            is_cold_start, dtype=torch.bool
        )
    else:
        data[NODE_PROPERTY].cold_start_mask = torch.zeros(
            len(properties_df), dtype=torch.bool
        )

    # Build edges

    # Property -> Transit (served_by)
    src, dst, weights = build_property_transit_edges(properties_df, transit_df)
    if src:
        data[NODE_PROPERTY, EDGE_SERVED_BY, NODE_TRANSIT].edge_index = torch.tensor(
            [src, dst], dtype=torch.long
        )
        data[NODE_PROPERTY, EDGE_SERVED_BY, NODE_TRANSIT].edge_attr = torch.tensor(
            weights, dtype=torch.float
        ).unsqueeze(1)

    # Property -> Amenity (near)
    src, dst, weights = build_property_amenity_edges(properties_df, amenities_df)
    if src:
        data[NODE_PROPERTY, EDGE_NEAR, NODE_AMENITY].edge_index = torch.tensor(
            [src, dst], dtype=torch.long
        )
        data[NODE_PROPERTY, EDGE_NEAR, NODE_AMENITY].edge_attr = torch.tensor(
            weights, dtype=torch.float
        ).unsqueeze(1)

    # Property -> Flood Zone (in_zone)
    if not flood_df.empty:
        src, dst, risk_levels = build_property_flood_edges(properties_df, flood_df)
        if src:
            # Add flood zone node features (just risk level)
            flood_features = torch.tensor(
                flood_df["risk_group"].values.reshape(-1, 1), dtype=torch.float
            )
            data[NODE_FLOOD].x = flood_features

            data[NODE_PROPERTY, EDGE_IN_ZONE, NODE_FLOOD].edge_index = torch.tensor(
                [src, dst], dtype=torch.long
            )
            data[NODE_PROPERTY, EDGE_IN_ZONE, NODE_FLOOD].edge_attr = torch.tensor(
                risk_levels, dtype=torch.float
            ).unsqueeze(1)

    # Store metadata
    data.metadata = {
        "num_properties": len(properties_df),
        "num_transit": len(transit_df),
        "num_amenities": len(amenities_df),
        "num_flood_zones": len(flood_df) if not flood_df.empty else 0,
        "h3_resolution": H3_RESOLUTION,
    }

    # Store ID mappings for inference
    data.property_ids = properties_df["id"].tolist()
    data.transit_ids = transit_df["stop_id"].tolist()

    return data


def save_graph(data, output_path: Path):
    """Save HeteroData to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(data, output_path)
    logger.info(f"Saved heterogeneous graph to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Build heterogeneous property graph")
    parser.add_argument(
        "--features-dir",
        type=str,
        default="data/h3_features",
        help="Directory with H3 features",
    )
    parser.add_argument(
        "--models-dir",
        type=str,
        default="models/hex2vec",
        help="Directory with Hex2Vec embeddings",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/hetero_graph.pt",
        help="Output path for graph",
    )
    args = parser.parse_args()

    features_dir = Path(args.features_dir)
    models_dir = Path(args.models_dir)
    output_path = Path(args.output)

    # Load data
    logger.info("Loading data...")
    properties_df = fetch_properties(engine)
    transit_df = fetch_transit_stops(engine)
    amenities_df = fetch_amenities(engine)
    flood_df = load_flood_risk(features_dir)
    h3_features = load_h3_features(features_dir)
    hex2vec_embeddings = load_hex2vec_embeddings(models_dir)

    # Compute transit centrality
    logger.info("Computing transit centrality...")
    transit_df = compute_transit_centrality(transit_df)

    # Build graph
    logger.info("Building heterogeneous graph...")
    data = build_hetero_data(
        properties_df,
        transit_df,
        amenities_df,
        flood_df,
        h3_features,
        hex2vec_embeddings,
    )

    # Log graph summary
    logger.info("\n=== Graph Summary ===")
    logger.info(f"Node types: {data.node_types}")
    logger.info(f"Edge types: {data.edge_types}")
    for node_type in data.node_types:
        if hasattr(data[node_type], "x"):
            logger.info(f"  {node_type}: {data[node_type].x.shape}")
    for edge_type in data.edge_types:
        if hasattr(data[edge_type], "edge_index"):
            logger.info(f"  {edge_type}: {data[edge_type].edge_index.shape}")

    # Save graph
    save_graph(data, output_path)
    logger.info("Done!")


if __name__ == "__main__":
    main()
