from geoalchemy2 import Geometry
from sqlalchemy import Column, Float, Integer, String
from src.config.database import Base


class SuitabilityGrid(Base):
    __tablename__ = "suitability_grid"

    h3_index = Column(String, primary_key=True)
    score = Column(Float, nullable=False)
    population = Column(Float)
    poi_count = Column(Integer)
    geometry = Column(Geometry("POLYGON", srid=4326))
