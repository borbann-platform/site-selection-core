import csv
import logging
import os
import sys

from geoalchemy2.shape import from_shape
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from scripts.etl.utils import clean_float
from shapely.geometry import Point
from src.config.database import SessionLocal
from src.models.places import ContributedPOI

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
)


def load_contributed_pois(db: Session):
    file_path = os.path.join(DATA_DIR, "longdomap-contributed-pois.csv")
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    logger.info("Loading Contributed POIs...")
    count = 0

    # Increase field size limit just in case
    csv.field_size_limit(sys.maxsize)

    with open(file_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lat = clean_float(row.get("latitude"))
            lon = clean_float(row.get("longitude"))

            geometry = None
            if lat and lon:
                point = Point(lon, lat)
                geometry = from_shape(point, srid=4326)

            # Check if exists (optional, might be slow for large dataset)
            # For speed, we might skip check or use bulk insert.
            # Let's try simple insert first.

            poi = ContributedPOI(
                id=row.get("id"),
                name_th=row.get("name_th"),
                name_en=row.get("name_en"),
                address_th=row.get("address_th"),
                address_en=row.get("address_en"),
                telephone=row.get("telephone"),
                website=row.get("website"),
                lastupdate=row.get("lastupdate"),
                poi_type=row.get("poi_type"),
                username=row.get("username"),
                geometry=geometry,
            )
            db.add(poi)
            count += 1

            if count % 5000 == 0:
                db.commit()
                logger.info(f"Processed {count} POIs...")

    db.commit()
    logger.info(f"Loaded {count} Contributed POIs.")


def main():
    db = SessionLocal()
    try:
        load_contributed_pois(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
