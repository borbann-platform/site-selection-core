"""
ETL script for loading POIs from OpenStreetMap thailand-260111.osm.pbf.

Extends POI coverage to match bkk_house_price.parquet extent.
Includes spatial+name-based deduplication against existing data sources.

Usage:
    python -m scripts.etl.load_osm_pois
    python -m scripts.etl.load_osm_pois --export-duplicates  # Export flagged dupes to CSV
"""

import argparse
import logging
import os
import sys
import unicodedata
from pathlib import Path

import pandas as pd
try:
    import pyrosm
except ImportError as exc:  # pragma: no cover - only hit when ETL extras missing
    raise SystemExit(
        "pyrosm is required for this ETL script. Install the extra with:\n"
        "  uv sync --extra etl\n"
        "or\n"
        "  pip install -e '.[etl]'"
    ) from exc
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.config.database import SessionLocal, engine
from src.models.places import OsmPOI

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
PBF_PATH = DATA_DIR / "thailand-260111.osm.pbf"

# Bounding box for Bangkok + nearby (with buffer to cover all housing data)
# Based on bkk_house_price.parquet extent + ~10km buffer
BBOX_MIN_LAT = 13.4
BBOX_MAX_LAT = 14.2
BBOX_MIN_LON = 100.2
BBOX_MAX_LON = 101.0

# Deduplication thresholds
EXACT_MATCH_DISTANCE_M = 5  # Consider exact duplicate if within 5m AND same name
SPATIAL_TYPE_MATCH_DISTANCE_M = 30  # Flag if same type within 30m
NAME_SIMILARITY_THRESHOLD = 0.7  # Trigram similarity threshold

# Map OSM amenity/shop tags to normalized poi_type categories
AMENITY_MAPPING = {
    # Education
    "school": "school",
    "university": "university",
    "college": "university",
    "kindergarten": "school",
    "library": "library",
    # Healthcare
    "hospital": "hospital",
    "clinic": "hospital",
    "doctors": "hospital",
    "dentist": "hospital",
    "pharmacy": "pharmacy",
    # Services
    "bank": "bank",
    "atm": "bank",
    "police": "police_station",
    "fire_station": "fire_station",
    "post_office": "post_office",
    # Commercial - Food
    "restaurant": "restaurant",
    "cafe": "cafe",
    "fast_food": "restaurant",
    "food_court": "restaurant",
    "bar": "bar",
    "pub": "bar",
    # Commercial - Other
    "fuel": "gas_station",
    "marketplace": "market",
    # Religious
    "place_of_worship": "temple",
    # Recreation
    "cinema": "entertainment",
    "theatre": "entertainment",
    "nightclub": "entertainment",
    # Public
    "parking": "parking",
    "bus_station": "transit_stop",
    "ferry_terminal": "water_transport",
}

SHOP_MAPPING = {
    "supermarket": "supermarket",
    "mall": "mall",
    "department_store": "mall",
    "convenience": "convenience_store",
    "grocery": "supermarket",
    "bakery": "bakery",
    "butcher": "market",
    "seafood": "market",
    "clothes": "retail",
    "electronics": "retail",
    "mobile_phone": "retail",
    "jewelry": "retail",
    "optician": "retail",
    "cosmetics": "retail",
    "hairdresser": "service",
    "beauty": "service",
    "laundry": "service",
    "car_repair": "service",
    "car": "retail",
    "motorcycle": "retail",
}

LEISURE_MAPPING = {
    "park": "park",
    "garden": "park",
    "playground": "park",
    "sports_centre": "sports",
    "fitness_centre": "fitness",
    "swimming_pool": "sports",
    "golf_course": "sports",
    "stadium": "sports",
}

# Noise types to skip
NOISE_TYPES = {
    "toilets",
    "waste_basket",
    "bench",
    "drinking_water",
    "telephone",
    "vending_machine",
    "recycling",
    "shelter",
    "hunting_stand",
}


def normalize_name(name: str | None) -> str:
    """Normalize name for comparison: lowercase, strip, remove diacritics."""
    if not name:
        return ""
    # Normalize unicode
    name = unicodedata.normalize("NFKC", name)
    # Lowercase and strip
    name = name.lower().strip()
    # Remove common suffixes/prefixes for Thai names
    for suffix in ["สาขา", "branch", "สาขาที่"]:
        if suffix in name:
            name = name.split(suffix)[0].strip()
    return name


def get_poi_type(row) -> str | None:
    """Map OSM tags to normalized poi_type."""
    amenity = row.get("amenity")
    shop = row.get("shop")
    leisure = row.get("leisure")
    tourism = row.get("tourism")

    # Skip noise
    if amenity in NOISE_TYPES:
        return None

    # Check mappings in order of priority
    if amenity and amenity in AMENITY_MAPPING:
        return AMENITY_MAPPING[amenity]
    if shop and shop in SHOP_MAPPING:
        return SHOP_MAPPING[shop]
    if leisure and leisure in LEISURE_MAPPING:
        return LEISURE_MAPPING[leisure]
    if tourism == "hotel":
        return "hotel"
    if tourism == "attraction":
        return "tourist_attraction"
    if tourism == "museum":
        return "museum"

    return None


def extract_osm_pois() -> pd.DataFrame:
    """Extract POIs from OSM PBF file, filtered to Bangkok bounding box."""
    logger.info(f"Loading OSM data from: {PBF_PATH}")

    if not PBF_PATH.exists():
        raise FileNotFoundError(f"OSM PBF file not found: {PBF_PATH}")

    # Use pyrosm with bounding box filter
    osm = pyrosm.OSM(
        str(PBF_PATH),
        bounding_box=[BBOX_MIN_LON, BBOX_MIN_LAT, BBOX_MAX_LON, BBOX_MAX_LAT],
    )

    logger.info(
        f"Bounding box: {BBOX_MIN_LAT}-{BBOX_MAX_LAT}°N, {BBOX_MIN_LON}-{BBOX_MAX_LON}°E"
    )

    # Extract POIs
    logger.info("Extracting POIs...")
    pois_gdf = osm.get_pois()

    if pois_gdf is None or len(pois_gdf) == 0:
        logger.warning("No POIs found in bounding box")
        return pd.DataFrame()

    logger.info(f"Found {len(pois_gdf):,} raw POIs in bounding box")

    # Process POIs
    records = []
    for idx, row in pois_gdf.iterrows():
        poi_type = get_poi_type(row)
        if not poi_type:
            continue

        # Get centroid for polygon geometries
        geom = row.geometry
        if geom is None:
            continue
        if geom.geom_type != "Point":
            geom = geom.centroid

        # Extract coordinates
        lon, lat = geom.x, geom.y

        # Double-check bounds (pyrosm bbox can be imprecise)
        if not (
            BBOX_MIN_LAT <= lat <= BBOX_MAX_LAT and BBOX_MIN_LON <= lon <= BBOX_MAX_LON
        ):
            continue

        records.append(
            {
                "osm_id": str(row.get("id", idx)),
                "osm_type": row.get("osm_type", "node"),
                "name": row.get("name"),
                "name_en": row.get("name:en"),
                "name_th": row.get("name:th"),
                "poi_type": poi_type,
                "amenity": row.get("amenity"),
                "shop": row.get("shop"),
                "brand": row.get("brand"),
                "operator": row.get("operator"),
                "lon": lon,
                "lat": lat,
            }
        )

    df = pd.DataFrame(records)
    logger.info(f"Filtered to {len(df):,} categorized POIs")

    # Log distribution
    logger.info("POI type distribution:")
    for poi_type, count in df["poi_type"].value_counts().head(20).items():
        logger.info(f"  {poi_type}: {count:,}")

    return df


def find_duplicates(df: pd.DataFrame, db: Session) -> pd.DataFrame:
    """
    Mark potential duplicates against existing POI sources.
    Uses spatial proximity + name similarity matching.

    Strategy:
    - Tier 1: Same coordinates (within 5m) AND same normalized name -> exact duplicate
    - Tier 2: Same poi_type within 30m -> potential duplicate (flag for review)

    For chain stores (7-Eleven, etc.), we allow multiple within 30m as valid.
    """
    logger.info("Running deduplication against existing POIs...")

    # Get existing POIs from mat_all_pois view (exclude OSM source to avoid self-matching)
    try:
        existing_pois = pd.read_sql(
            """
            SELECT 
                id,
                name,
                type as poi_type,
                ST_X(geometry::geometry) as lon,
                ST_Y(geometry::geometry) as lat
            FROM mat_all_pois
            WHERE geometry IS NOT NULL
              AND source != 'osm_thailand'
            """,
            engine,
        )
        logger.info(f"Loaded {len(existing_pois):,} existing POIs for dedup check")
    except Exception as e:
        logger.warning(f"Could not load existing POIs (view may not exist yet): {e}")
        existing_pois = pd.DataFrame()

    if existing_pois.empty:
        df["is_duplicate"] = False
        df["duplicate_of"] = None
        df["duplicate_reason"] = None
        return df

    # Normalize names for comparison
    existing_pois["name_norm"] = existing_pois["name"].apply(normalize_name)
    df["name_norm"] = df["name"].apply(normalize_name)

    # For each new POI, check against existing
    is_duplicate = []
    duplicate_of = []
    duplicate_reason = []

    for idx, row in df.iterrows():
        if idx % 5000 == 0 and idx > 0:
            logger.info(f"Dedup progress: {idx:,}/{len(df):,}")

        dup_found = False
        dup_id = None
        dup_reason = None

        # Skip if no name (can't deduplicate reliably)
        if not row["name_norm"]:
            is_duplicate.append(False)
            duplicate_of.append(None)
            duplicate_reason.append(None)
            continue

        # Calculate distances to all existing POIs (vectorized for speed)
        # Using simple Euclidean approximation (good enough for ~30m scale)
        # 1 degree lat ≈ 111km, 1 degree lon ≈ 111km * cos(lat)
        lat_diff = (existing_pois["lat"] - row["lat"]) * 111000
        lon_diff = (existing_pois["lon"] - row["lon"]) * 111000 * 0.857  # cos(13.7°)
        distances = (lat_diff**2 + lon_diff**2) ** 0.5

        # Tier 1: Exact match (within 5m AND same normalized name)
        close_mask = distances < EXACT_MATCH_DISTANCE_M
        if close_mask.any():
            close_pois = existing_pois[close_mask]
            for _, existing in close_pois.iterrows():
                if existing["name_norm"] == row["name_norm"]:
                    dup_found = True
                    dup_id = existing["id"]
                    dup_reason = "exact_match_5m"
                    break

        # Tier 2: Same type within 30m (only if not a chain store)
        if not dup_found and row["brand"] is None:
            type_mask = existing_pois["poi_type"] == row["poi_type"]
            spatial_mask = distances < SPATIAL_TYPE_MATCH_DISTANCE_M
            combined_mask = type_mask & spatial_mask

            if combined_mask.any():
                close_same_type = existing_pois[combined_mask]
                # Check name similarity
                for _, existing in close_same_type.iterrows():
                    if existing["name_norm"] and row["name_norm"]:
                        # Simple substring check (faster than trigram)
                        if (
                            existing["name_norm"] in row["name_norm"]
                            or row["name_norm"] in existing["name_norm"]
                        ):
                            dup_found = True
                            dup_id = existing["id"]
                            dup_reason = "type_match_30m_name_similar"
                            break

        is_duplicate.append(dup_found)
        duplicate_of.append(dup_id)
        duplicate_reason.append(dup_reason)

    df["is_duplicate"] = is_duplicate
    df["duplicate_of"] = duplicate_of
    df["duplicate_reason"] = duplicate_reason

    dup_count = df["is_duplicate"].sum()
    logger.info(
        f"Marked {dup_count:,} POIs as duplicates ({dup_count / len(df) * 100:.1f}%)"
    )

    return df


def load_osm_pois(db: Session, skip_dedup: bool = False, clear_existing: bool = True):
    """
    Main ETL function to extract, deduplicate, and load OSM POIs.

    Args:
        db: Database session
        skip_dedup: If True, skip deduplication step
        clear_existing: If True, clear existing OSM POIs before loading

    """
    # Extract POIs from PBF
    df = extract_osm_pois()

    if df.empty:
        logger.warning("No POIs extracted, nothing to load")
        return

    # Run deduplication
    if not skip_dedup:
        df = find_duplicates(df, db)
    else:
        df["is_duplicate"] = False
        df["duplicate_of"] = None
        df["duplicate_reason"] = None

    # Clear existing data
    if clear_existing:
        logger.info("Clearing existing OSM POI data...")
        db.query(OsmPOI).delete()
        db.commit()

    # Load to database
    logger.info(f"Loading {len(df):,} OSM POIs to database...")
    count = 0

    for _, row in df.iterrows():
        geometry = from_shape(Point(row["lon"], row["lat"]), srid=4326)

        poi = OsmPOI(
            osm_id=row["osm_id"],
            osm_type=row.get("osm_type"),
            name=row.get("name"),
            name_en=row.get("name_en"),
            name_th=row.get("name_th"),
            poi_type=row["poi_type"],
            amenity=row.get("amenity"),
            shop=row.get("shop"),
            brand=row.get("brand"),
            operator=row.get("operator"),
            is_duplicate=row["is_duplicate"],
            duplicate_of=row.get("duplicate_of"),
            duplicate_reason=row.get("duplicate_reason"),
            geometry=geometry,
        )
        db.add(poi)
        count += 1

        if count % 5000 == 0:
            db.commit()
            logger.info(f"Loaded {count:,} records...")

    db.commit()

    # Summary
    unique_count = len(df[~df["is_duplicate"]])
    dup_count = len(df[df["is_duplicate"]])
    logger.info(f"Loaded {count:,} OSM POIs total")
    logger.info(f"  - Unique (will be included in views): {unique_count:,}")
    logger.info(f"  - Duplicates (flagged, excluded from views): {dup_count:,}")


def export_duplicates_to_csv(output_path: Path | None = None):
    """Export flagged duplicates to CSV for manual review."""
    if output_path is None:
        output_path = DATA_DIR / "osm_poi_duplicates.csv"

    logger.info(f"Exporting duplicates to {output_path}")

    df = pd.read_sql(
        """
        SELECT 
            o.id,
            o.osm_id,
            o.name,
            o.name_en,
            o.poi_type,
            o.brand,
            o.duplicate_of,
            o.duplicate_reason,
            ST_X(o.geometry::geometry) as lon,
            ST_Y(o.geometry::geometry) as lat
        FROM osm_pois o
        WHERE o.is_duplicate = TRUE
        ORDER BY o.poi_type, o.name
        """,
        engine,
    )

    df.to_csv(output_path, index=False)
    logger.info(f"Exported {len(df):,} duplicates to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Load OSM POIs with deduplication")
    parser.add_argument(
        "--skip-dedup",
        action="store_true",
        help="Skip deduplication step",
    )
    parser.add_argument(
        "--export-duplicates",
        action="store_true",
        help="Export flagged duplicates to CSV for review",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Don't clear existing OSM POIs before loading",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        load_osm_pois(
            db,
            skip_dedup=args.skip_dedup,
            clear_existing=not args.no_clear,
        )

        if args.export_duplicates:
            export_duplicates_to_csv()

    finally:
        db.close()


if __name__ == "__main__":
    main()
