"""
Script to create spatial indexes on all POI tables.
Run this once after initial database setup.
"""

import logging
import os
import sys

from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.database import SessionLocal

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_spatial_indexes():
    """Create GiST spatial indexes on all POI geometry columns."""
    db = SessionLocal()
    try:
        indexes = [
            ("bus_shelters", "idx_bus_shelters_geometry"),
            ("schools", "idx_schools_geometry"),
            ("police_stations", "idx_police_stations_geometry"),
            ("museums", "idx_museums_geometry"),
            ("gas_stations", "idx_gas_stations_geometry"),
            ("traffic_points", "idx_traffic_points_geometry"),
            ("water_transport_piers", "idx_water_transport_piers_geometry"),
            ("tourist_attractions", "idx_tourist_attractions_geometry"),
            ("contributed_pois", "idx_contributed_pois_geometry"),
            ("transit_stops", "idx_transit_stops_geometry"),
        ]

        for table, index_name in indexes:
            logger.info(f"Creating index {index_name} on {table}...")
            sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} USING GIST (geometry)"
            db.execute(text(sql))

        db.commit()
        logger.info("All spatial indexes created successfully!")

    except Exception as e:
        logger.error(f"Error creating indexes: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_spatial_indexes()
