"""
ETL script for loading Bangkok house price data from parquet into PostGIS.
Data source: Treasury Department (กรมธนารักษ์)
"""

import logging
import os
import sys
from datetime import datetime

import pandas as pd
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.config.database import SessionLocal
from src.models.realestate import HousePrice

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
)


def parse_date(date_str: str):
    """Parse YYYYMMDD string to date object."""
    if not date_str:
        return None
    try:
        return datetime.strptime(str(date_str), "%Y%m%d").date()
    except (ValueError, TypeError):
        logger.warning(f"Failed to parse date: {date_str}")
        return None


def load_house_prices(db: Session, clear_existing: bool = True):
    """
    Load house price data from parquet file.

    Args:
        db: Database session
        clear_existing: If True, clears existing data before loading

    """
    file_path = os.path.join(DATA_DIR, "bkk_house_price.parquet")
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    logger.info("Loading House Prices from parquet...")

    # Read parquet file
    df = pd.read_parquet(file_path)
    logger.info(f"Read {len(df)} records from parquet")

    if clear_existing:
        logger.info("Clearing existing house price data...")
        db.query(HousePrice).delete()
        db.commit()

    count = 0
    skipped = 0

    for _, row in df.iterrows():
        lat = row.get("latitude")
        lon = row.get("longtitude")  # Note: typo in source data

        # Skip records without valid coordinates
        if pd.isna(lat) or pd.isna(lon):
            skipped += 1
            continue

        geometry = from_shape(Point(lon, lat), srid=4326)

        house_price = HousePrice(
            updated_date=parse_date(row.get("updated_datetime")),
            land_type_desc=row.get("land_type_desc"),
            building_style_desc=row.get("building_style_desc"),
            tumbon=row.get("tumbon"),
            amphur=row.get("amphur"),
            province=row.get("province"),
            village=row.get("village") if pd.notna(row.get("village")) else None,
            building_age=row.get("building_age")
            if pd.notna(row.get("building_age"))
            else None,
            land_area=row.get("land_area") if pd.notna(row.get("land_area")) else None,
            building_area=row.get("building_area")
            if pd.notna(row.get("building_area"))
            else None,
            no_of_floor=row.get("no_of_floor")
            if pd.notna(row.get("no_of_floor"))
            else None,
            total_price=row.get("total_price")
            if pd.notna(row.get("total_price"))
            else None,
            geometry=geometry,
        )
        db.add(house_price)
        count += 1

        if count % 1000 == 0:
            db.commit()
            logger.info(f"Loaded {count} records...")

    db.commit()
    logger.info(
        f"Loaded {count} House Price records. Skipped {skipped} without coordinates."
    )


def main():
    """Run standalone ETL."""
    db = SessionLocal()
    try:
        load_house_prices(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
