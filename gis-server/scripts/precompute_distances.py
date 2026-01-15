"""
Pre-compute Network Distances for S2-HGT Edges.

Calculates road network distances between houses and anchor nodes.
This is a SEPARATE job from graph building due to computational cost.

Pipeline:
1. Load houses and anchor nodes
2. KDTree pre-filtering (Euclidean < 2km)
3. Parallel Dijkstra on road network
4. Save edges to parquet

Usage:
    # Full run (expect 4-8 hours for 320K houses)
    python -m scripts.precompute_distances --output data/house_anchor_edges.parquet

    # Test with subset
    python -m scripts.precompute_distances --sample 5000 --output data/house_anchor_edges_subset.parquet

    # Resume from checkpoint
    python -m scripts.precompute_distances --resume --output data/house_anchor_edges.parquet
"""

import argparse
import logging
import pickle
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sqlalchemy import text
from src.config.database import engine

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Distance thresholds
EUCLIDEAN_CUTOFF_M = 2000  # KDTree pre-filter (meters)
NETWORK_CUTOFF_M = 3000  # Max network distance to keep edge
NETWORK_BUFFER_FACTOR = 1.5  # Allow network dist up to 1.5x Euclidean
MIN_ANCHORS_PER_HOUSE = 3  # k-NN guarantee: force at least this many anchors

# Parallelization
DEFAULT_WORKERS = 4
CHUNK_SIZE = 1000  # Houses per chunk for checkpointing

# Walking speed for travel time estimation (m/s)
WALKING_SPEED_MS = 1.4  # ~5 km/h


def load_road_graph(graph_path: Path) -> nx.Graph:
    """Load road network graph from GraphML."""
    logger.info(f"Loading road graph from {graph_path}...")
    G = nx.read_graphml(graph_path)

    # Ensure 'length' attribute exists and is float
    for u, v, data in G.edges(data=True):
        if "length" in data:
            data["length"] = float(data["length"])
        else:
            # Fallback: compute from coordinates if available
            data["length"] = 100.0  # Default 100m if missing

    logger.info(f"Road graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


def fetch_houses(engine, sample: int | None = None) -> pd.DataFrame:
    """Fetch house coordinates from database."""
    query = """
    SELECT 
        id,
        ST_X(geometry::geometry) as lon,
        ST_Y(geometry::geometry) as lat
    FROM house_prices
    WHERE geometry IS NOT NULL AND total_price > 0
    """
    if sample:
        query += f" ORDER BY RANDOM() LIMIT {sample}"

    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)

    logger.info(f"Fetched {len(df)} houses")
    return df


def load_anchor_nodes(anchors_path: Path) -> pd.DataFrame:
    """Load pre-computed anchor nodes from poi_tiers output."""
    if not anchors_path.exists():
        raise FileNotFoundError(
            f"Anchor nodes not found at {anchors_path}. "
            "Run 'python -m scripts.build_poi_tiers' first."
        )

    df = pd.read_parquet(anchors_path)
    df = df[df["tier"] == 1]  # Ensure only Tier 1
    logger.info(f"Loaded {len(df)} anchor nodes")
    return df


def build_kdtree(anchors_df: pd.DataFrame) -> tuple[cKDTree, np.ndarray]:
    """Build KDTree for anchor nodes."""
    coords = anchors_df[["lat", "lon"]].values
    tree = cKDTree(coords)
    return tree, coords


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate haversine distance in meters."""
    R = 6371000
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def find_nearest_graph_node(G: nx.Graph, lat: float, lon: float) -> str | None:
    """
    Find nearest node in road graph to given coordinates.

    Note: Graph nodes have 'x' (lon) and 'y' (lat) attributes.
    """
    min_dist = float("inf")
    nearest = None

    for node, data in G.nodes(data=True):
        if "x" not in data or "y" not in data:
            continue
        node_lon = float(data["x"])
        node_lat = float(data["y"])
        dist = haversine_distance(lat, lon, node_lat, node_lon)
        if dist < min_dist:
            min_dist = dist
            nearest = node

    return nearest


def compute_network_distance(
    G: nx.Graph,
    house_node: str,
    anchor_node: str,
    euclidean_dist: float,
) -> float | None:
    """
    Compute shortest path distance on road network.

    Returns None if:
    - No path exists (e.g., river/canal blocking)
    - Network distance exceeds threshold
    """
    try:
        path_length = nx.shortest_path_length(
            G, house_node, anchor_node, weight="length"
        )

        # Sanity check: network distance shouldn't be too much larger than Euclidean
        if path_length > euclidean_dist * NETWORK_BUFFER_FACTOR:
            if path_length > NETWORK_CUTOFF_M:
                return None

        return path_length

    except nx.NetworkXNoPath:
        return None
    except nx.NodeNotFound:
        return None


def process_house_chunk(
    chunk_data: tuple[int, pd.DataFrame, pd.DataFrame, Path, cKDTree, np.ndarray],
) -> list[dict]:
    """
    Process a chunk of houses (for parallel execution).

    Args:
        chunk_data: (chunk_id, houses_chunk, anchors_df, graph_path, tree, anchor_coords)

    Returns:
        List of edge dictionaries

    """
    chunk_id, houses_df, anchors_df, graph_path, tree, anchor_coords = chunk_data

    # Load graph in each worker (cannot pickle networkx graph)
    G = load_road_graph(graph_path)

    # Build node coordinate index for fast nearest-node lookup
    node_coords = {}
    for node, data in G.nodes(data=True):
        if "x" in data and "y" in data:
            node_coords[node] = (float(data["y"]), float(data["x"]))  # (lat, lon)

    # Build KDTree for graph nodes
    node_ids = list(node_coords.keys())
    node_positions = np.array([node_coords[n] for n in node_ids])
    node_tree = cKDTree(node_positions)

    edges = []
    processed = 0

    for _, house in houses_df.iterrows():
        house_lat, house_lon = house["lat"], house["lon"]

        # Find nearest graph node for house
        _, house_node_idx = node_tree.query([house_lat, house_lon])
        house_graph_node = node_ids[house_node_idx]

        # KDTree query for candidate anchors (Euclidean pre-filter)
        # Convert lat/lon to approximate meters for query radius
        # At Bangkok latitude (~13.7°), 1° lat ≈ 111km, 1° lon ≈ 108km
        radius_deg = EUCLIDEAN_CUTOFF_M / 111000  # Approximate

        candidate_indices = tree.query_ball_point([house_lat, house_lon], radius_deg)

        for anchor_idx in candidate_indices:
            anchor = anchors_df.iloc[anchor_idx]
            anchor_lat, anchor_lon = anchor["lat"], anchor["lon"]

            # Compute Euclidean distance
            euclidean_dist = haversine_distance(
                house_lat, house_lon, anchor_lat, anchor_lon
            )

            if euclidean_dist > EUCLIDEAN_CUTOFF_M:
                continue

            # Find nearest graph node for anchor
            _, anchor_node_idx = node_tree.query([anchor_lat, anchor_lon])
            anchor_graph_node = node_ids[anchor_node_idx]

            # Compute network distance
            network_dist = compute_network_distance(
                G, house_graph_node, anchor_graph_node, euclidean_dist
            )

            if network_dist is not None:
                travel_time_min = (network_dist / WALKING_SPEED_MS) / 60

                edges.append(
                    {
                        "house_id": house["id"],
                        "anchor_id": anchor["id"],
                        "anchor_category": anchor["category"],
                        "euclidean_dist": euclidean_dist,
                        "network_dist": network_dist,
                        "travel_time_min": travel_time_min,
                    }
                )

        # ====== k-NN Guarantee: No Blind Nodes ======
        # If this house has fewer than MIN_ANCHORS edges, force-fetch nearest k anchors
        house_edges = [e for e in edges if e["house_id"] == house["id"]]
        if len(house_edges) < MIN_ANCHORS_PER_HOUSE:
            _, nearest_indices = tree.query(
                [house_lat, house_lon], k=MIN_ANCHORS_PER_HOUSE
            )
            if isinstance(nearest_indices, np.integer):
                nearest_indices = [nearest_indices]

            existing_anchor_ids = {e["anchor_id"] for e in house_edges}

            for anchor_idx in nearest_indices:
                if anchor_idx >= len(anchors_df):
                    continue
                anchor = anchors_df.iloc[anchor_idx]
                if anchor["id"] in existing_anchor_ids:
                    continue

                anchor_lat, anchor_lon = anchor["lat"], anchor["lon"]
                euclidean_dist = haversine_distance(
                    house_lat, house_lon, anchor_lat, anchor_lon
                )

                _, anchor_node_idx = node_tree.query([anchor_lat, anchor_lon])
                anchor_graph_node = node_ids[anchor_node_idx]

                try:
                    network_dist = nx.shortest_path_length(
                        G, house_graph_node, anchor_graph_node, weight="length"
                    )
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    network_dist = euclidean_dist * 1.4  # Fallback estimate

                travel_time_min = (network_dist / WALKING_SPEED_MS) / 60
                edges.append(
                    {
                        "house_id": house["id"],
                        "anchor_id": anchor["id"],
                        "anchor_category": anchor["category"],
                        "euclidean_dist": euclidean_dist,
                        "network_dist": network_dist,
                        "travel_time_min": travel_time_min,
                    }
                )
                existing_anchor_ids.add(anchor["id"])

                if len(existing_anchor_ids) >= MIN_ANCHORS_PER_HOUSE:
                    break

        processed += 1
        if processed % 100 == 0:
            logger.debug(f"Chunk {chunk_id}: processed {processed}/{len(houses_df)}")

    logger.info(
        f"Chunk {chunk_id} complete: {len(edges)} edges from {len(houses_df)} houses"
    )
    return edges


def save_checkpoint(edges: list[dict], checkpoint_path: Path, chunk_id: int):
    """Save intermediate results to checkpoint file."""
    checkpoint_file = checkpoint_path / f"chunk_{chunk_id:04d}.pkl"
    with open(checkpoint_file, "wb") as f:
        pickle.dump(edges, f)
    logger.info(f"Saved checkpoint: {checkpoint_file}")


def load_checkpoints(checkpoint_path: Path) -> tuple[list[dict], set[int]]:
    """Load all checkpoint files and return edges + completed chunk IDs."""
    all_edges = []
    completed_chunks = set()

    if not checkpoint_path.exists():
        return all_edges, completed_chunks

    for ckpt_file in checkpoint_path.glob("chunk_*.pkl"):
        chunk_id = int(ckpt_file.stem.split("_")[1])
        with open(ckpt_file, "rb") as f:
            edges = pickle.load(f)
        all_edges.extend(edges)
        completed_chunks.add(chunk_id)

    logger.info(
        f"Loaded {len(completed_chunks)} checkpoints with {len(all_edges)} edges"
    )
    return all_edges, completed_chunks


def main():
    parser = argparse.ArgumentParser(description="Pre-compute network distances")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/house_anchor_edges.parquet"),
        help="Output parquet file",
    )
    parser.add_argument(
        "--graph-path",
        type=Path,
        default=Path("data/bangkok_graph.graphml"),
        help="Road network graph file",
    )
    parser.add_argument(
        "--anchors-path",
        type=Path,
        default=Path("data/anchor_nodes.parquet"),
        help="Anchor nodes file (from build_poi_tiers.py)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Sample N houses for testing (default: all)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help="Number of parallel workers",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=CHUNK_SIZE,
        help="Houses per chunk",
    )
    args = parser.parse_args()

    # Setup checkpoint directory
    checkpoint_dir = args.output.parent / "distance_checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    houses_df = fetch_houses(engine, sample=args.sample)
    anchors_df = load_anchor_nodes(args.anchors_path)

    # Build KDTree for anchors
    anchor_tree, anchor_coords = build_kdtree(anchors_df)

    # Resume from checkpoint if requested
    existing_edges, completed_chunks = [], set()
    if args.resume:
        existing_edges, completed_chunks = load_checkpoints(checkpoint_dir)

    # Split houses into chunks
    n_chunks = (len(houses_df) + args.chunk_size - 1) // args.chunk_size
    chunks = []

    for i in range(n_chunks):
        if i in completed_chunks:
            logger.info(f"Skipping completed chunk {i}")
            continue

        start_idx = i * args.chunk_size
        end_idx = min((i + 1) * args.chunk_size, len(houses_df))
        chunk_df = houses_df.iloc[start_idx:end_idx].copy()

        chunks.append(
            (i, chunk_df, anchors_df, args.graph_path, anchor_tree, anchor_coords)
        )

    logger.info(f"Processing {len(chunks)} chunks with {args.workers} workers")

    # Process chunks in parallel
    all_edges = existing_edges.copy()

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(process_house_chunk, chunk): chunk[0] for chunk in chunks
        }

        for future in as_completed(futures):
            chunk_id = futures[future]
            try:
                edges = future.result()
                all_edges.extend(edges)

                # Save checkpoint
                save_checkpoint(edges, checkpoint_dir, chunk_id)

            except Exception as e:
                logger.error(f"Chunk {chunk_id} failed: {e}")

    # Combine and save final output
    if all_edges:
        edges_df = pd.DataFrame(all_edges)
        edges_df.to_parquet(args.output, index=False)
        logger.info(f"Saved {len(edges_df)} edges to {args.output}")

        # Summary stats
        logger.info("Edge statistics:")
        logger.info(f"  Houses with edges: {edges_df['house_id'].nunique()}")
        logger.info(f"  Anchors connected: {edges_df['anchor_id'].nunique()}")
        logger.info(
            f"  Avg edges per house: {len(edges_df) / edges_df['house_id'].nunique():.1f}"
        )
        logger.info(f"  Avg network distance: {edges_df['network_dist'].mean():.0f}m")
        logger.info(f"  Avg travel time: {edges_df['travel_time_min'].mean():.1f}min")
    else:
        logger.warning("No edges computed!")


if __name__ == "__main__":
    main()
