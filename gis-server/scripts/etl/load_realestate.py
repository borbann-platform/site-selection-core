import csv
import glob
import json
import logging
import os
import sys

from geoalchemy2.shape import from_shape
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from scripts.etl.utils import clean_float, clean_int
from shapely.geometry import Point
from src.config.database import SessionLocal
from src.models.realestate import CondoProject, RealEstateListing

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
)


def load_condo_projects(db: Session):
    file_path = os.path.join(DATA_DIR, "hipflat-scrape", "condos_data_bangkok.json")
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    logger.info("Loading Condo Projects (Hipflat)...")
    count = 0
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
        for item in data:
            lat = clean_float(item.get("latitude"))
            lon = clean_float(item.get("longitude"))

            geometry = None
            if lat and lon:
                point = Point(lon, lat)
                geometry = from_shape(point, srid=4326)

            # Check if exists
            existing = (
                db.query(CondoProject)
                .filter(CondoProject.project_base_url == item.get("project_base_url"))
                .first()
            )
            if existing:
                continue

            project = CondoProject(
                project_base_url=item.get("project_base_url"),
                name=item.get("name"),
                location=item.get("location"),
                completed_date=item.get("completed_date"),
                floors=item.get("floors"),
                units=item.get("units"),
                buildings=item.get("buildings"),
                price_sale=item.get("price_sale"),
                sale_units=item.get("sale_units"),
                price_rent=item.get("price_rent"),
                rent_units=item.get("rent_units"),
                description=item.get("description"),
                facilities=item.get("facilities"),
                nearby_projects=item.get("nearby_projects"),
                images=item.get("images"),
                units_for_sale=item.get("units_for_sale"),
                units_for_rent=item.get("units_for_rent"),
                market_stats=item.get("market_stats"),
                geometry=geometry,
            )
            db.add(project)
            count += 1

            if count % 100 == 0:
                db.commit()

    db.commit()
    logger.info(f"Loaded {count} Condo Projects.")


def load_real_estate_listings(db: Session):
    bania_dir = os.path.join(DATA_DIR, "bania-scrape", "Data")
    if not os.path.exists(bania_dir):
        logger.warning(f"Directory not found: {bania_dir}")
        return

    csv_files = glob.glob(os.path.join(bania_dir, "*.csv"))

    for file_path in csv_files:
        filename = os.path.basename(file_path)
        logger.info(f"Loading Real Estate Listings from {filename}...")
        count = 0

        with open(file_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                lat = clean_float(row.get("latitude"))
                lon = clean_float(row.get("longitude"))

                geometry = None
                if lat and lon:
                    point = Point(lon, lat)
                    geometry = from_shape(point, srid=4326)

                listing = RealEstateListing(
                    source_file=filename,
                    title=row.get("title"),
                    property_type=row.get("property_type"),
                    price=row.get("price"),
                    description=row.get("description"),
                    location=row.get("location"),
                    bathrooms=row.get("bathrooms"),
                    bedrooms=row.get("bedrooms"),
                    floors=row.get("floors"),
                    total_floors=row.get("total_floors"),
                    usable_area_sqm=row.get("usable_area_sqm"),
                    land_size_sqw=row.get("land_size_sqw"),
                    facilities=row.get("facilities"),
                    highlights=row.get("highlights"),
                    furniture_status=row.get("furniture_status"),
                    developer=row.get("developer"),
                    completion_date=row.get("completion_date"),
                    status=row.get("status"),
                    images=row.get("images"),
                    image_count=clean_int(row.get("image_count")),
                    last_updated=row.get("last_updated"),
                    geometry=geometry,
                )
                db.add(listing)
                count += 1

                if count % 1000 == 0:
                    db.commit()
                    logger.info(f"Processed {count} rows in {filename}")

        db.commit()
        logger.info(f"Loaded {count} listings from {filename}.")


def main():
    db = SessionLocal()
    try:
        load_condo_projects(db)
        load_real_estate_listings(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
