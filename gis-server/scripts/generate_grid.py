import logging
import os
import sys

# Add the parent directory to sys.path to allow imports from src
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import h3
from geoalchemy2 import WKTElement
from shapely.geometry import Polygon
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config.database import Base, settings
from src.models.grid import SuitabilityGrid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_grid():
    logger.info("Connecting to database...")
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Create table if not exists
    logger.info("Creating tables...")
    Base.metadata.create_all(engine)

    # 2. Define Bangkok Bounds (approximate box)
    # Center: 13.7563, 100.5018
    # ~10km radius box
    lat_min, lat_max = 13.65, 13.85
    lon_min, lon_max = 100.40, 100.65

    # h3 expects (lat, lon) for Polygon
    boundary_coords = [
        (lat_min, lon_min),
        (lat_max, lon_min),
        (lat_max, lon_max),
        (lat_min, lon_max),
        (lat_min, lon_min),
    ]

    # 3. Generate H3 Cells
    resolution = 8
    logger.info(f"Generating H3 cells at resolution {resolution}...")

    try:
        # Create h3.LatLngPoly from (lat, lon) tuples
        # h3-py v4 uses LatLngPoly instead of Polygon
        polygon = h3.LatLngPoly(boundary_coords)
        hex_indexes = h3.polygon_to_cells(polygon, resolution)
    except Exception as e:
        logger.exception(f"Error generating H3 cells: {e}")
        return

    logger.info(f"Generated {len(hex_indexes)} hexagons.")

    # 4. Prepare Data
    grid_data = []
    center_lat, center_lon = 13.7563, 100.5018

    for h3_index in hex_indexes:
        # Get boundary for geometry
        # h3.cell_to_boundary returns tuple of (lat, lon)
        boundary = h3.cell_to_boundary(h3_index)
        # Swap to (lon, lat) for Shapely/PostGIS
        poly_coords = [(p[1], p[0]) for p in boundary]
        # Close the loop
        poly_coords.append(poly_coords[0])

        poly = Polygon(poly_coords)
        wkt_geom = WKTElement(poly.wkt, srid=4326)

        # Calculate simple distance-based score (Mock Suitability)
        # Distance from center
        lat, lon = h3.cell_to_latlng(h3_index)
        dist_sq = (lat - center_lat) ** 2 + (lon - center_lon) ** 2
        # Simple decay function
        score = max(0, 1.0 - (dist_sq * 100))

        # Add some noise/randomness to make it look realistic
        import random

        score = score * (0.8 + random.random() * 0.4)
        score = min(max(score, 0), 1)

        grid_data.append(
            {
                "h3_index": h3_index,
                "score": score,
                "population": 0,  # Placeholder
                "poi_count": 0,  # Placeholder
                "geometry": wkt_geom,
            }
        )

    # 5. Bulk Insert
    logger.info("Inserting data into database...")

    # Clear existing data
    session.query(SuitabilityGrid).delete()

    # Insert in chunks
    chunk_size = 1000
    for i in range(0, len(grid_data), chunk_size):
        chunk = grid_data[i : i + chunk_size]
        session.bulk_insert_mappings(SuitabilityGrid, chunk)
        session.commit()
        logger.info(
            f"Inserted {min(i + chunk_size, len(grid_data))} / {len(grid_data)}"
        )

    logger.info("Grid generation complete.")
    session.close()


if __name__ == "__main__":
    generate_grid()
