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

from scripts.etl.utils import clean_float, clean_int, parse_wkt_geometry
from src.config.database import SessionLocal
from src.models.demographics import PopulationGrid

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
)


def load_population(db: Session):
    file_path = os.path.join(DATA_DIR, "bangkok-population.csv")
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    logger.info("Loading Population Grid...")
    count = 0
    with open(file_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            wkt_str = row.get("WKT")
            if wkt_str:
                poly = parse_wkt_geometry(wkt_str)
                if poly:
                    # The CSV has MULTIPOLYGON but our model says POLYGON?
                    # Actually GeoAlchemy2 Geometry("POLYGON") can often accept MULTIPOLYGON if SRID matches,
                    # but strictly it should be Geometry("MULTIPOLYGON") or generic Geometry.
                    # Let's check if we need to handle MultiPolygon.
                    # If the WKT is MULTIPOLYGON, shapely returns a MultiPolygon.
                    # We should probably update the model to be generic Geometry or MultiPolygon if all are Multi.
                    # For now, let's try inserting.

                    grid = PopulationGrid(
                        grid_id=clean_int(row.get("id")),
                        population_density=clean_float(row.get("Min_Pop/RA")),
                        geometry=from_shape(poly, srid=4326),
                    )
                    db.add(grid)
                    count += 1
    db.commit()
    logger.info(f"Loaded {count} Population Grids.")


def main():
    db = SessionLocal()
    try:
        load_population(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
