from geoalchemy2 import Geometry
from sqlalchemy import Column, String
from src.config.database import Base


class TransitStop(Base):
    __tablename__ = "transit_stops"

    stop_id = Column(String, primary_key=True)
    stop_name = Column(String)
    zone_id = Column(String, nullable=True)
    wheelchair_boarding = Column(String, nullable=True)
    source = Column(String, nullable=True)  # Added source column
    geometry = Column(Geometry("POINT", srid=4326))


class TransitShape(Base):
    __tablename__ = "transit_shapes"

    shape_id = Column(String, primary_key=True)
    geometry = Column(Geometry("LINESTRING", srid=4326))
