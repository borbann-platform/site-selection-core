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

from scripts.etl.utils import clean_float, clean_int, parse_lat_lon_string
from shapely.geometry import Point
from src.config.database import SessionLocal
from src.models.places import (
    BusShelter,
    GasStation,
    Museum,
    PoliceStation,
    School,
    TouristAttraction,
    TrafficPoint,
    WaterTransport,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
)


def load_bus_shelters(db: Session):
    file_path = os.path.join(DATA_DIR, "bus-shelter.csv")
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    logger.info("Loading Bus Shelters...")
    count = 0
    with open(file_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            point = parse_lat_lon_string(row.get("coordinates"))
            if point:
                shelter = BusShelter(
                    contract_number=row.get("Contract_number"),
                    project_name=row.get("Project_name"),
                    location_name=row.get("Location"),
                    code_shelter=row.get("Code_shelter"),
                    asset_code=row.get("Asset_Code"),
                    district=row.get("District"),
                    shelter_type=row.get("Type"),
                    status=row.get("Status"),
                    geometry=from_shape(point, srid=4326),
                )
                db.add(shelter)
                count += 1
    db.commit()
    logger.info(f"Loaded {count} Bus Shelters.")


def load_schools(db: Session):
    file_path = os.path.join(DATA_DIR, "school-bma.csv")
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    logger.info("Loading Schools...")
    count = 0
    with open(file_path, encoding="utf-8-sig") as f:
        # Skip the first line (Thai header)
        next(f)
        reader = csv.DictReader(f)
        for row in reader:
            lat = clean_float(row.get("LATITUDE"))
            lon = clean_float(row.get("LONGITUDE"))
            if lat and lon:
                point = Point(lon, lat)
                school = School(
                    id=row.get("IDSCHOOL"),
                    name=row.get("SCHOOLNAME"),
                    address=row.get("ADDRESS"),
                    district=row.get("DIST"),
                    subdistrict=row.get("TUM"),
                    level=row.get("LEVEL"),
                    phone=row.get("TEL"),
                    geometry=from_shape(point, srid=4326),
                )
                db.add(school)
                count += 1
    db.commit()
    logger.info(f"Loaded {count} Schools.")


def load_police_stations(db: Session):
    file_path = os.path.join(DATA_DIR, "police_station.csv")
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    logger.info("Loading Police Stations...")
    count = 0
    with open(file_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lat = clean_float(row.get("lat"))
            lon = clean_float(row.get("lng"))
            if lat and lon:
                point = Point(lon, lat)
                station = PoliceStation(
                    id=clean_int(row.get("id_police")),
                    name=row.get("name"),
                    address=row.get("address"),
                    phone=row.get("tel"),
                    district=row.get("dname"),
                    division=row.get("division"),
                    geometry=from_shape(point, srid=4326),
                )
                db.add(station)
                count += 1
    db.commit()
    logger.info(f"Loaded {count} Police Stations.")


def load_museums(db: Session):
    file_path = os.path.join(DATA_DIR, "local_museum.csv")
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    logger.info("Loading Museums...")
    count = 0
    with open(file_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lat = clean_float(row.get("lat"))
            lon = clean_float(row.get("lng"))
            if lat and lon:
                point = Point(lon, lat)
                museum = Museum(
                    id=clean_int(row.get("id_local")),
                    name=row.get("name"),
                    district=row.get("dname"),
                    address=row.get("address"),
                    phone=row.get("tel"),
                    geometry=from_shape(point, srid=4326),
                )
                db.add(museum)
                count += 1
    db.commit()
    logger.info(f"Loaded {count} Museums.")


def load_gas_stations(db: Session):
    file_path = os.path.join(DATA_DIR, "gasstation.csv")
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    logger.info("Loading Gas Stations...")
    count = 0
    with open(file_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lat = clean_float(row.get("lat"))
            lon = clean_float(row.get("lng"))
            if lat and lon:
                point = Point(lon, lat)
                station = GasStation(
                    id=clean_int(row.get("id")),
                    name=row.get("name"),
                    address=row.get("address"),
                    district=row.get("dname"),
                    brand_type=row.get("type"),
                    geometry=from_shape(point, srid=4326),
                )
                db.add(station)
                count += 1
    db.commit()
    logger.info(f"Loaded {count} Gas Stations.")


def load_traffic_points(db: Session):
    file_path = os.path.join(DATA_DIR, "traffic-manage.csv")
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    logger.info("Loading Traffic Points...")
    count = 0
    with open(file_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lat = clean_float(row.get("latitude"))
            lon = clean_float(row.get("longitude"))
            if lat and lon:
                point = Point(lon, lat)
                tp = TrafficPoint(
                    id=clean_int(row.get("id")),
                    name=row.get("place"),
                    morning_time=row.get("morning_t"),
                    afternoon_time=row.get("afternoon_t"),
                    geometry=from_shape(point, srid=4326),
                )
                db.add(tp)
                count += 1
    db.commit()
    logger.info(f"Loaded {count} Traffic Points.")


def load_water_transport(db: Session):
    file_path = os.path.join(DATA_DIR, "water-transportation.csv")
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    logger.info("Loading Water Transport Piers...")
    count = 0
    with open(file_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lat = clean_float(row.get("latitude"))
            lon = clean_float(row.get("longitude"))
            if lat and lon:
                point = Point(lon, lat)
                pier = WaterTransport(
                    name=row.get("place_name"),
                    address=row.get("place"),
                    geometry=from_shape(point, srid=4326),
                )
                db.add(pier)
                count += 1
    db.commit()
    logger.info(f"Loaded {count} Water Transport Piers.")


def load_tourist_attractions(db: Session):
    file_path = os.path.join(DATA_DIR, "china-town-data.csv")
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    logger.info("Loading Tourist Attractions (China Town)...")
    count = 0
    with open(file_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lat = clean_float(row.get("latitude"))
            lon = clean_float(row.get("longitude"))
            if lat and lon:
                point = Point(lon, lat)
                attraction = TouristAttraction(
                    id=clean_int(row.get("idx")),
                    name=row.get("nname"),
                    description=row.get("history") or row.get("activity"),
                    address=row.get("address"),
                    travel_info=row.get("travel"),
                    open_time=row.get("oc_time"),
                    geometry=from_shape(point, srid=4326),
                )
                db.add(attraction)
                count += 1
    db.commit()
    logger.info(f"Loaded {count} Tourist Attractions.")


def main():
    db = SessionLocal()
    try:
        load_bus_shelters(db)
        load_schools(db)
        load_police_stations(db)
        load_museums(db)
        load_gas_stations(db)
        load_traffic_points(db)
        load_water_transport(db)
        load_tourist_attractions(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
