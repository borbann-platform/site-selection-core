from geoalchemy2 import Geometry
from sqlalchemy import JSON, Column, Integer, String, Text
from src.config.database import Base


class CondoProject(Base):
    __tablename__ = "condo_projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_base_url = Column(String, unique=True)
    name = Column(String)
    location = Column(Text)
    completed_date = Column(String)  # Keeping as string as format might vary
    floors = Column(String)
    units = Column(String)
    buildings = Column(String)
    price_sale = Column(String)
    sale_units = Column(String)
    price_rent = Column(String)
    rent_units = Column(String)
    description = Column(Text)
    facilities = Column(JSON)  # Array of strings
    nearby_projects = Column(JSON)  # Array of objects
    images = Column(JSON)  # Array of strings
    units_for_sale = Column(JSON)
    units_for_rent = Column(JSON)
    market_stats = Column(JSON)

    geometry = Column(Geometry("POINT", srid=4326))


class RealEstateListing(Base):
    __tablename__ = "real_estate_listings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_file = Column(String)  # e.g. 'apartment_all.csv'

    title = Column(String)
    property_type = Column(String)
    price = Column(String)  # Some might be ranges or text
    description = Column(Text)
    location = Column(Text)

    bathrooms = Column(String)
    bedrooms = Column(String)
    floors = Column(String)
    total_floors = Column(String)
    usable_area_sqm = Column(String)
    land_size_sqw = Column(String)

    facilities = Column(Text)
    highlights = Column(Text)
    furniture_status = Column(String)
    developer = Column(String)
    completion_date = Column(String)
    status = Column(String)

    images = Column(Text)  # Looks like a string representation of list in CSV
    image_count = Column(Integer)

    last_updated = Column(String)

    geometry = Column(Geometry("POINT", srid=4326))
