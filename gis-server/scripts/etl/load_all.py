import logging
import os
import sys

# Add project root to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from scripts.etl.load_contributed_pois import load_contributed_pois
from scripts.etl.load_gtfs import DATA_ROOT as GTFS_DATA_ROOT
from scripts.etl.load_gtfs import GTFS_SOURCES, load_shapes, load_stops
from scripts.etl.load_places import (
    load_bus_shelters,
    load_gas_stations,
    load_museums,
    load_police_stations,
    load_schools,
    load_tourist_attractions,
    load_traffic_points,
    load_water_transport,
)
from scripts.etl.load_population import load_population
from scripts.etl.load_realestate import load_condo_projects, load_real_estate_listings
from src.config.database import SessionLocal

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting full data load...")
    db = SessionLocal()
    try:
        # Places
        load_bus_shelters(db)
        load_schools(db)
        load_police_stations(db)
        load_museums(db)
        load_gas_stations(db)
        load_traffic_points(db)
        load_water_transport(db)
        load_tourist_attractions(db)

        # Contributed POIs
        load_contributed_pois(db)

        # Transit
        for source in GTFS_SOURCES:
            data_dir = os.path.join(GTFS_DATA_ROOT, source["folder"])
            load_stops(db, data_dir, source["source_name"])
            load_shapes(db, data_dir, source["source_name"])

        # Demographics
        load_population(db)

        # Real Estate
        load_condo_projects(db)
        load_real_estate_listings(db)

    except Exception as e:
        logger.error(f"An error occurred during data loading: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()
    logger.info("Full data load completed.")


if __name__ == "__main__":
    main()
