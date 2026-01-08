"""
Build H3 hexagonal features for Spatial GNN.

Indexes all entities (properties, POIs, transit) to H3 cells at multiple resolutions.
Aggregates features per cell for Hex2Vec training and graph node features.

Usage:
    python -m scripts.build_h3_features --resolution 9 --output data/h3_features.parquet
"""

import argparse
import logging
from collections import defaultdict
from pathlib import Path

import h3
import pandas as pd
from sqlalchemy import text
from src.config.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# H3 resolution configs
# Res 7: ~5km² (district level), Res 9: ~0.1km² (block level), Res 11: ~500m² (building level)
RESOLUTIONS = [7, 9, 11]
DEFAULT_RESOLUTION = 9

# POI type categories for feature vectors
# Filter out noise: keep only semantically meaningful POI types
POI_CATEGORIES = [
    "school",
    "transit_stop",
    "bus_shelter",
    "police_station",
    "museum",
    "gas_station",
    "water_transport",
    "tourist_attraction",
    # From contributed POIs - high-value categories
    "restaurant",
    "cafe",
    "hospital",
    "bank",
    "mall",
    "supermarket",
    "park",
    "temple",
    "university",
]

# Noise filter: POI types to exclude from embeddings
NOISE_POI_TYPES = [
    "power_pole",
    "utility_pole",
    "manhole",
    "fire_hydrant",
    "street_lamp",
    "traffic_sign",
    "bollard",
    "waste_basket",
]


def fetch_properties(engine) -> pd.DataFrame:
    """Fetch house price data with coordinates."""
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
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    logger.info(f"Fetched {len(df)} properties")
    return df


def fetch_pois(engine) -> pd.DataFrame:
    """Fetch all POIs from unified view, filtering noise."""
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

    # Filter out noise POI types
    df = df[~df["poi_type"].isin(NOISE_POI_TYPES)]
    logger.info(f"Fetched {len(df)} POIs after noise filtering")
    return df


def fetch_transit_stops(engine) -> pd.DataFrame:
    """Fetch transit stops with route info for centrality calculation."""
    query = """
    SELECT 
        t.stop_id,
        t.stop_name,
        t.source,
        ST_X(t.geometry::geometry) as lon,
        ST_Y(t.geometry::geometry) as lat
    FROM transit_stops t
    WHERE t.geometry IS NOT NULL
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    logger.info(f"Fetched {len(df)} transit stops")
    return df


def fetch_flood_risk(engine) -> pd.DataFrame:
    """
    Fetch flood warning zones.

    TODO: Replace with GISTDA API integration for real-time flood data.
    Currently uses static flood-warning.csv data.
    """
    # For now, load from CSV since it's district-level text data
    # Will need geocoding or manual mapping to coordinates
    csv_path = Path(__file__).parent.parent / "data" / "flood-warning.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} flood warning zones from CSV")
        # TODO: Geocode flood zones to coordinates
        # For now, return district -> risk_group mapping
        return df[["District", "risk_group"]].drop_duplicates()
    logger.warning("Flood warning CSV not found")
    return pd.DataFrame()


def coord_to_h3(lat: float, lon: float, resolution: int) -> str:
    """Convert lat/lon to H3 cell index."""
    return h3.latlng_to_cell(lat, lon, resolution)


def index_to_h3(df: pd.DataFrame, resolution: int) -> pd.DataFrame:
    """Add H3 index column to dataframe with lat/lon."""
    df = df.copy()
    df[f"h3_res{resolution}"] = df.apply(
        lambda row: coord_to_h3(row["lat"], row["lon"], resolution), axis=1
    )
    return df


def build_poi_vectors(pois_df: pd.DataFrame, resolution: int) -> pd.DataFrame:
    """
    Build POI count vectors per H3 cell.

    Returns DataFrame with H3 index and count per POI category.
    """
    pois_h3 = index_to_h3(pois_df, resolution)

    # Count POIs by type per H3 cell
    h3_col = f"h3_res{resolution}"
    poi_counts = defaultdict(lambda: defaultdict(int))

    for _, row in pois_h3.iterrows():
        cell = row[h3_col]
        poi_type = row["poi_type"]
        poi_counts[cell][poi_type] += 1

    # Convert to DataFrame with category columns
    records = []
    for cell, type_counts in poi_counts.items():
        record = {"h3_index": cell}
        for cat in POI_CATEGORIES:
            record[f"poi_{cat}"] = type_counts.get(cat, 0)
        # Total POI count
        record["poi_total"] = sum(type_counts.values())
        records.append(record)

    return pd.DataFrame(records)


def build_property_features(
    properties_df: pd.DataFrame, resolution: int
) -> pd.DataFrame:
    """
    Aggregate property features per H3 cell.

    For cells with transactions: compute mean intrinsic features.
    For cells without: will rely on spatial context (cold-start handling).
    """
    props_h3 = index_to_h3(properties_df, resolution)
    h3_col = f"h3_res{resolution}"

    # Encode building style as numeric
    style_map = {
        "บ้านเดี่ยว": 1,
        "ทาวน์เฮ้าส์": 2,
        "บ้านแฝด": 3,
        "อาคารพาณิชย์": 4,
        "ตึกแถว": 5,
    }
    props_h3["building_style_encoded"] = (
        props_h3["building_style_desc"].map(style_map).fillna(0)
    )

    # Aggregate per H3 cell
    agg_features = props_h3.groupby(h3_col).agg(
        {
            "building_area": ["mean", "std", "count"],
            "land_area": ["mean", "std"],
            "building_age": ["mean", "std"],
            "no_of_floor": ["mean"],
            "building_style_encoded": [
                "mean"
            ],  # Average style (proxy for area character)
            "total_price": ["mean", "median", "std"],
        }
    )

    # Flatten column names
    agg_features.columns = ["_".join(col).strip() for col in agg_features.columns]
    agg_features = agg_features.reset_index().rename(columns={h3_col: "h3_index"})

    # Rename for clarity
    agg_features = agg_features.rename(
        columns={
            "building_area_mean": "avg_building_area",
            "building_area_std": "std_building_area",
            "building_area_count": "property_count",
            "land_area_mean": "avg_land_area",
            "land_area_std": "std_land_area",
            "building_age_mean": "avg_building_age",
            "building_age_std": "std_building_age",
            "no_of_floor_mean": "avg_floors",
            "building_style_encoded_mean": "avg_building_style",
            "total_price_mean": "avg_price",
            "total_price_median": "median_price",
            "total_price_std": "std_price",
        }
    )

    return agg_features


def build_transit_features(transit_df: pd.DataFrame, resolution: int) -> pd.DataFrame:
    """
    Aggregate transit features per H3 cell.

    Includes stop counts and source diversity (BTS/MRT/Bus).
    """
    transit_h3 = index_to_h3(transit_df, resolution)
    h3_col = f"h3_res{resolution}"

    # Count by source type
    transit_counts = transit_h3.groupby([h3_col, "source"]).size().unstack(fill_value=0)
    transit_counts = transit_counts.reset_index().rename(columns={h3_col: "h3_index"})

    # Add total transit count
    source_cols = [c for c in transit_counts.columns if c != "h3_index"]
    transit_counts["transit_total"] = transit_counts[source_cols].sum(axis=1)

    # Rename source columns
    rename_map = {col: f"transit_{col}" for col in source_cols}
    transit_counts = transit_counts.rename(columns=rename_map)

    return transit_counts


def build_flood_risk_features(flood_df: pd.DataFrame) -> dict:
    """
    Build district -> flood risk mapping.

    TODO: Upgrade to H3-level flood risk when GISTDA API is integrated.
    Returns dict for lookup during graph construction.
    """
    if flood_df.empty:
        return {}

    # Map Thai district names to risk levels
    risk_map = {}
    for _, row in flood_df.iterrows():
        district = row["District"]
        risk_group = row["risk_group"]
        # risk_group 1 = high risk, 2 = medium risk
        risk_map[district] = risk_group

    logger.info(f"Built flood risk map for {len(risk_map)} districts")
    return risk_map


def get_h3_neighbors(h3_index: str, k: int = 1) -> list:
    """Get k-ring neighbors of an H3 cell."""
    return list(h3.grid_disk(h3_index, k))


def build_multi_resolution_features(
    properties_df: pd.DataFrame,
    pois_df: pd.DataFrame,
    transit_df: pd.DataFrame,
    resolutions: list = RESOLUTIONS,
) -> dict:
    """
    Build feature DataFrames at multiple H3 resolutions.

    Returns dict mapping resolution -> merged feature DataFrame.
    """
    features_by_res = {}

    for res in resolutions:
        logger.info(f"Building features at resolution {res}")

        # Build individual feature sets
        poi_features = build_poi_vectors(pois_df, res)
        prop_features = build_property_features(properties_df, res)
        transit_features = build_transit_features(transit_df, res)

        # Merge all features on H3 index
        # Start with POI features as base (covers most cells)
        merged = poi_features

        # Left join property features (sparse - only cells with transactions)
        if not prop_features.empty:
            merged = merged.merge(prop_features, on="h3_index", how="outer")

        # Left join transit features
        if not transit_features.empty:
            merged = merged.merge(transit_features, on="h3_index", how="outer")

        # Fill NaN with 0 for count features, but keep property features as NaN
        # (to distinguish cold-start cells)
        count_cols = [
            c
            for c in merged.columns
            if c.startswith("poi_") or c.startswith("transit_")
        ]
        merged[count_cols] = merged[count_cols].fillna(0)

        # Add resolution metadata
        merged["resolution"] = res

        # Add cell centroid coordinates for visualization
        merged["centroid_lat"] = merged["h3_index"].apply(
            lambda x: h3.cell_to_latlng(x)[0]
        )
        merged["centroid_lon"] = merged["h3_index"].apply(
            lambda x: h3.cell_to_latlng(x)[1]
        )

        features_by_res[res] = merged
        logger.info(f"Resolution {res}: {len(merged)} cells with features")

    return features_by_res


def identify_cold_start_cells(features_df: pd.DataFrame) -> pd.DataFrame:
    """
    Mark cells that have no transaction history (cold-start).

    Cold-start cells will rely on spatial context from neighbors
    during GNN inference.
    """
    features_df = features_df.copy()
    features_df["is_cold_start"] = features_df["property_count"].isna() | (
        features_df["property_count"] == 0
    )
    cold_count = features_df["is_cold_start"].sum()
    logger.info(
        f"Identified {cold_count} cold-start cells "
        f"({cold_count / len(features_df) * 100:.1f}%)"
    )
    return features_df


def save_features(features_by_res: dict, output_dir: Path):
    """Save feature DataFrames to parquet files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for res, df in features_by_res.items():
        output_path = output_dir / f"h3_features_res{res}.parquet"
        df.to_parquet(output_path, index=False)
        logger.info(f"Saved {len(df)} cells to {output_path}")

    # Also save combined file for convenience
    combined = pd.concat(features_by_res.values(), ignore_index=True)
    combined_path = output_dir / "h3_features_all.parquet"
    combined.to_parquet(combined_path, index=False)
    logger.info(f"Saved combined features to {combined_path}")


def main():
    parser = argparse.ArgumentParser(description="Build H3 hexagonal features")
    parser.add_argument(
        "--output",
        type=str,
        default="data/h3_features",
        help="Output directory for parquet files",
    )
    parser.add_argument(
        "--resolutions",
        type=int,
        nargs="+",
        default=RESOLUTIONS,
        help="H3 resolutions to build features for",
    )
    args = parser.parse_args()

    output_dir = Path(args.output)

    logger.info("Fetching data from database...")
    properties_df = fetch_properties(engine)
    pois_df = fetch_pois(engine)
    transit_df = fetch_transit_stops(engine)
    flood_df = fetch_flood_risk(engine)

    logger.info("Building multi-resolution H3 features...")
    features_by_res = build_multi_resolution_features(
        properties_df, pois_df, transit_df, args.resolutions
    )

    # Mark cold-start cells
    for res in features_by_res:
        features_by_res[res] = identify_cold_start_cells(features_by_res[res])

    # Save flood risk mapping separately (district-level for now)
    flood_risk_map = build_flood_risk_features(flood_df)
    if flood_risk_map:
        flood_df_out = pd.DataFrame(
            list(flood_risk_map.items()), columns=["district", "risk_group"]
        )
        flood_path = output_dir / "flood_risk_by_district.parquet"
        output_dir.mkdir(parents=True, exist_ok=True)
        flood_df_out.to_parquet(flood_path, index=False)
        logger.info(f"Saved flood risk map to {flood_path}")

    logger.info("Saving features...")
    save_features(features_by_res, output_dir)

    logger.info("Done!")


if __name__ == "__main__":
    main()
