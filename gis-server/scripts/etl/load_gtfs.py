import csv
import logging
import os
import sys

from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, Point
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from scripts.etl.utils import clean_float
from src.config.database import SessionLocal
from src.models.transit import TransitRoute, TransitShape, TransitStop, TransitTrip

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DATA_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
)

GTFS_SOURCES = [
    {"folder": "bangkok-gtfs", "source_name": "bangkok_gtfs"},
    {"folder": "longdomap-bus-gtfs", "source_name": "longdomap_bus"},
]


def load_stops(db: Session, data_dir: str, source_name: str):
    file_path = os.path.join(data_dir, "stops.txt")
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    logger.info(f"Loading GTFS Stops from {source_name}...")
    count = 0
    with open(file_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lat = clean_float(row.get("stop_lat"))
            lon = clean_float(row.get("stop_lon"))
            if lat and lon:
                point = Point(lon, lat)

                stop = TransitStop(
                    stop_id=row.get("stop_id"),
                    stop_name=row.get("stop_name"),
                    zone_id=row.get("zone_id"),
                    wheelchair_boarding=row.get("wheelchair_boarding"),
                    source=source_name,
                    geometry=from_shape(point, srid=4326),
                )
                db.merge(stop)
                count += 1
    db.commit()
    logger.info(f"Loaded {count} GTFS Stops from {source_name}.")


def load_shapes(db: Session, data_dir: str, source_name: str):
    file_path = os.path.join(data_dir, "shapes.txt")
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    logger.info(f"Loading GTFS Shapes from {source_name}...")

    # Group points by shape_id
    shapes_data = {}
    with open(file_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            shape_id = row.get("shape_id")
            lat = clean_float(row.get("shape_pt_lat"))
            lon = clean_float(row.get("shape_pt_lon"))
            seq = int(row.get("shape_pt_sequence"))

            if shape_id and lat and lon:
                if shape_id not in shapes_data:
                    shapes_data[shape_id] = []
                shapes_data[shape_id].append((seq, lon, lat))

    count = 0
    for shape_id, points in shapes_data.items():
        # Sort by sequence
        points.sort(key=lambda x: x[0])
        # Extract coordinates
        coords = [(p[1], p[2]) for p in points]

        if len(coords) >= 2:
            line = LineString(coords)
            shape = TransitShape(
                shape_id=shape_id, geometry=from_shape(line, srid=4326)
            )
            db.merge(shape)
            count += 1

    db.commit()
    logger.info(f"Loaded {count} GTFS Shapes from {source_name}.")


def load_routes(db: Session, data_dir: str, source_name: str):
    """Load GTFS routes.txt - transit line definitions with colors."""
    file_path = os.path.join(data_dir, "routes.txt")
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    logger.info(f"Loading GTFS Routes from {source_name}...")
    count = 0
    with open(file_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            route_type_str = row.get("route_type", "")
            route_type = int(route_type_str) if route_type_str.isdigit() else None

            route = TransitRoute(
                route_id=row.get("route_id"),
                agency_id=row.get("agency_id"),
                route_short_name=row.get("route_short_name"),
                route_long_name=row.get("route_long_name"),
                route_type=route_type,
                route_color=row.get("route_color"),
                source=source_name,
            )
            db.merge(route)
            count += 1
    db.commit()
    logger.info(f"Loaded {count} GTFS Routes from {source_name}.")


def load_trips(db: Session, data_dir: str, source_name: str):
    """Load GTFS trips.txt - links routes to shapes."""
    file_path = os.path.join(data_dir, "trips.txt")
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    logger.info(f"Loading GTFS Trips from {source_name}...")
    count = 0
    with open(file_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            direction_str = row.get("direction_id", "")
            direction_id = int(direction_str) if direction_str.isdigit() else None

            trip = TransitTrip(
                trip_id=row.get("trip_id"),
                route_id=row.get("route_id"),
                shape_id=row.get("shape_id"),
                trip_headsign=row.get("trip_headsign"),
                direction_id=direction_id,
                source=source_name,
            )
            db.merge(trip)
            count += 1
    db.commit()
    logger.info(f"Loaded {count} GTFS Trips from {source_name}.")


def main():
    db = SessionLocal()
    try:
        for source in GTFS_SOURCES:
            data_dir = os.path.join(DATA_ROOT, source["folder"])
            load_stops(db, data_dir, source["source_name"])
            load_shapes(db, data_dir, source["source_name"])
            load_routes(db, data_dir, source["source_name"])
            load_trips(db, data_dir, source["source_name"])
    finally:
        db.close()


if __name__ == "__main__":
    main()
