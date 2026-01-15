"""
Build POI Tier Classification for S2-HGT Anchor Nodes.

Classifies POIs into tiers based on brand/chain recognition:
- Tier 1: International chains (Starbucks, BTS, Central, etc.) -> Anchor Nodes
- Tier 2: Thai national chains (Cafe Amazon, MK, etc.)
- Tier 3: Local/independent businesses

Uses exact substring matching for MVP (fast, deterministic).
Thai/English brand variations handled via lookup dictionary.

Usage:
    python -m scripts.build_poi_tiers --output data/poi_tiers.parquet
"""

import argparse
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from src.config.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# TIER 1: High-signal international/premium brands -> Anchor Nodes
# These have strong price correlation and consistent quality signaling
# =============================================================================
TIER_1_BRANDS = {
    # Transit (highest signal)
    "transit": [
        ("bts", "บีทีเอส"),
        ("mrt", "เอ็มอาร์ที"),
        ("arl", "airport rail link", "แอร์พอร์ตลิงก์"),
    ],
    # Premium retail/malls
    "retail": [
        ("central", "เซ็นทรัล"),
        ("siam paragon", "สยามพารากอน"),
        ("emporium", "เอ็มโพเรียม"),
        ("emquartier", "เอ็มควอเทียร์"),
        ("iconsiam", "ไอคอนสยาม"),
        ("the mall", "เดอะมอลล์"),
        ("mega bangna", "เมกาบางนา"),
        ("centralworld", "เซ็นทรัลเวิลด์"),
        ("terminal 21", "เทอร์มินอล 21"),
        ("robinson", "โรบินสัน"),
    ],
    # Premium cafes (lifestyle indicator)
    "cafe": [
        ("starbucks", "สตาร์บัคส์"),
        ("costa coffee", "คอสตา"),
        ("dean & deluca", "ดีน แอนด์ เดลูก้า"),
        ("blue bottle", "บลูบอทเทิล"),
    ],
    # International F&B chains
    "restaurant": [
        ("mcdonald", "แมคโดนัลด์"),
        ("kfc", "เคเอฟซี"),
        ("burger king", "เบอร์เกอร์คิง"),
        ("pizza hut", "พิซซ่าฮัท"),
        ("sizzler", "ซิซซ์เลอร์"),
        ("swensen", "สเวนเซ่นส์"),
        ("haagen-dazs", "ฮาเก้น-ดาส"),
        ("au bon pain", "โอ บอง แปง"),
    ],
    # Healthcare (premium)
    "hospital": [
        ("bumrungrad", "บำรุงราษฎร์"),
        ("samitivej", "สมิติเวช"),
        ("bangkok hospital", "โรงพยาบาลกรุงเทพ"),
        ("bnh", "บีเอ็นเอช"),
        ("thonburi", "ธนบุรี"),
        ("piyavate", "ปิยะเวท"),
    ],
    # Education (international)
    "education": [
        ("international school", "โรงเรียนนานาชาติ"),
        ("patana", "พัฒนา"),
        ("harrow", "แฮร์โรว์"),
        ("shrewsbury", "ชรูว์สเบอรี"),
        ("bangkok prep", "บางกอกเพรพ"),
        ("concordian", "คอนคอร์เดียน"),
    ],
    # Banks (ATM accessibility proxy)
    "bank": [
        ("scb", "ไทยพาณิชย์", "siam commercial"),
        ("kbank", "กสิกร", "kasikorn"),
        ("bangkok bank", "กรุงเทพ"),
        ("ktb", "กรุงไทย"),
        ("krungsri", "กรุงศรี"),
    ],
    # Fitness (lifestyle)
    "fitness": [
        ("fitness first", "ฟิตเนสเฟิร์ส"),
        ("virgin active", "เวอร์จิน แอคทีฟ"),
        ("jetts", "เจ็ตส์"),
    ],
}

# =============================================================================
# TIER 2: Thai national chains (moderate signal)
# =============================================================================
TIER_2_BRANDS = {
    "cafe": [
        ("cafe amazon", "คาเฟ่ อเมซอน", "amazon"),
        ("inthanin", "อินทนิล"),
        ("wawee", "วาวี"),
        ("black canyon", "แบล็คแคนยอน"),
        ("true coffee", "ทรู คอฟฟี่"),
    ],
    "restaurant": [
        ("mk restaurant", "เอ็มเค"),
        ("shabushi", "ชาบูชิ"),
        ("fuji", "ฟูจิ"),
        ("s&p", "เอสแอนด์พี"),
        ("bar b q plaza", "บาร์บีคิว พลาซ่า"),
        ("hot pot", "ฮอทพอท"),
        ("oishi", "โออิชิ"),
        ("yayoi", "ยาโยอิ"),
        ("bonchon", "บอนชอน"),
        ("mos burger", "มอส เบอร์เกอร์"),
    ],
    "retail": [
        ("big c", "บิ๊กซี"),
        ("tesco", "เทสโก้"),
        ("lotus", "โลตัส"),
        ("makro", "แม็คโคร"),
        ("tops", "ท็อปส์"),
    ],
    "convenience": [
        ("7-eleven", "เซเว่น", "7-11", "seven eleven"),
        ("family mart", "แฟมิลี่มาร์ท"),
        ("lawson", "ลอว์สัน"),
        ("mini big c", "มินิบิ๊กซี"),
    ],
}

# Brand -> (tier, category, embedding_idx) mapping
# embedding_idx is unique per brand for learned embeddings
BRAND_REGISTRY: dict[str, tuple[int, str, int]] = {}


def _build_brand_registry():
    """Build flat registry from tier dictionaries."""
    idx = 0
    for category, brand_list in TIER_1_BRANDS.items():
        for brand_tuple in brand_list:
            for variant in brand_tuple:
                BRAND_REGISTRY[variant.lower()] = (1, category, idx)
            idx += 1

    for category, brand_list in TIER_2_BRANDS.items():
        for brand_tuple in brand_list:
            for variant in brand_tuple:
                BRAND_REGISTRY[variant.lower()] = (2, category, idx)
            idx += 1

    logger.info(
        f"Built brand registry: {len(BRAND_REGISTRY)} variants, {idx} unique brands"
    )


_build_brand_registry()


def classify_poi(name_th: str | None, name_en: str | None) -> tuple[int, str, int]:
    """
    Classify a POI by tier using exact substring matching.

    Returns:
        (tier, category, embedding_idx)
        tier=0 means no match (Tier 3 / local)

    """
    import pandas as pd

    # Combine names for matching (handle NaN values)
    search_text = ""
    if name_th and pd.notna(name_th):
        search_text += str(name_th).lower() + " "
    if name_en and pd.notna(name_en):
        search_text += str(name_en).lower()

    if not search_text.strip():
        return (0, "unknown", -1)

    # Check each brand variant (exact substring match)
    for brand_key, (tier, category, emb_idx) in BRAND_REGISTRY.items():
        if brand_key in search_text:
            return (tier, category, emb_idx)

    return (0, "local", -1)


def fetch_pois_from_db(engine) -> pd.DataFrame:
    """Fetch POIs from database (unified view)."""
    query = """
    SELECT 
        id,
        name_th,
        name_en,
        poi_type,
        ST_X(geometry::geometry) as lon,
        ST_Y(geometry::geometry) as lat
    FROM longdo_pois
    WHERE geometry IS NOT NULL
    """
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
        logger.info(f"Fetched {len(df)} POIs from database")
        return df
    except Exception as e:
        logger.warning(f"Database fetch failed: {e}, falling back to CSV")
        return pd.DataFrame()


def load_pois_from_csv(csv_path: Path) -> pd.DataFrame:
    """Load POIs from CSV file."""
    if not csv_path.exists():
        raise FileNotFoundError(f"POI CSV not found: {csv_path}")

    df = pd.read_csv(
        csv_path,
        usecols=["id", "name_th", "name_en", "latitude", "longitude", "poi_type"],
        dtype={"id": str, "name_th": str, "name_en": str, "poi_type": str},
    )
    df = df.rename(columns={"latitude": "lat", "longitude": "lon"})
    df = df.dropna(subset=["lat", "lon"])

    logger.info(f"Loaded {len(df)} POIs from CSV")
    return df


def fetch_transit_as_tier1(engine) -> pd.DataFrame:
    """
    Fetch transit stops and mark as Tier 1 anchors.

    Transit stops (BTS/MRT/ARL) are always Tier 1 regardless of name matching.
    """
    query = """
    SELECT 
        stop_id as id,
        stop_name as name_th,
        stop_name as name_en,
        source as poi_type,
        ST_X(geometry::geometry) as lon,
        ST_Y(geometry::geometry) as lat
    FROM transit_stops
    WHERE geometry IS NOT NULL
      AND source IN ('bts', 'mrt', 'arl')
    """
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
        df["tier"] = 1
        df["category"] = "transit"
        df["embedding_idx"] = 0  # Transit shares embedding idx 0
        logger.info(f"Fetched {len(df)} transit stops as Tier 1")
        return df
    except Exception as e:
        logger.warning(f"Transit fetch failed: {e}")
        return pd.DataFrame()


def classify_all_pois(pois_df: pd.DataFrame) -> pd.DataFrame:
    """Classify all POIs and add tier columns."""
    results = []
    tier_counts = {0: 0, 1: 0, 2: 0}

    for _, row in pois_df.iterrows():
        tier, category, emb_idx = classify_poi(row.get("name_th"), row.get("name_en"))
        tier_counts[tier] += 1
        results.append(
            {
                "id": row["id"],
                "name_th": row.get("name_th"),
                "name_en": row.get("name_en"),
                "lat": row["lat"],
                "lon": row["lon"],
                "poi_type": row.get("poi_type"),
                "tier": tier,
                "category": category,
                "embedding_idx": emb_idx,
            }
        )

    df = pd.DataFrame(results)

    logger.info("Classification complete:")
    logger.info(f"  Tier 1 (Anchors): {tier_counts[1]:,}")
    logger.info(f"  Tier 2 (National): {tier_counts[2]:,}")
    logger.info(f"  Tier 3 (Local): {tier_counts[0]:,}")

    return df


def main():
    parser = argparse.ArgumentParser(description="Build POI tier classification")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/poi_tiers.parquet"),
        help="Output parquet file path",
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=Path("data/longdomap-contributed-pois.csv"),
        help="Fallback CSV if database unavailable",
    )
    parser.add_argument(
        "--anchors-only",
        action="store_true",
        help="Output only Tier 1 anchors (for graph building)",
    )
    args = parser.parse_args()

    # Try database first, fall back to CSV
    pois_df = fetch_pois_from_db(engine)
    if pois_df.empty:
        pois_df = load_pois_from_csv(args.csv_path)

    # Classify POIs
    classified_df = classify_all_pois(pois_df)

    # Add transit stops as guaranteed Tier 1
    transit_df = fetch_transit_as_tier1(engine)
    if not transit_df.empty:
        classified_df = pd.concat([classified_df, transit_df], ignore_index=True)
        classified_df = classified_df.drop_duplicates(
            subset=["lat", "lon"], keep="first"
        )

    # Filter to anchors only if requested
    if args.anchors_only:
        classified_df = classified_df[classified_df["tier"] == 1]
        logger.info(f"Filtered to {len(classified_df)} Tier 1 anchors")

    # Save output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    classified_df.to_parquet(args.output, index=False)
    logger.info(f"Saved to {args.output}")

    # Also save anchors-only file for graph building
    anchors_path = args.output.parent / "anchor_nodes.parquet"
    anchors_df = classified_df[classified_df["tier"] == 1]
    anchors_df.to_parquet(anchors_path, index=False)
    logger.info(f"Saved {len(anchors_df)} anchors to {anchors_path}")


if __name__ == "__main__":
    main()
