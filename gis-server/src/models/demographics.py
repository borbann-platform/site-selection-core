from geoalchemy2 import Geometry
from sqlalchemy import Column, Float, Integer
from src.config.database import Base


class PopulationGrid(Base):
    __tablename__ = "population_grid"

    id = Column(Integer, primary_key=True)
    grid_id = Column(Integer)  # id column in csv
    population_density = Column(Float)  # Min_Pop/RA
    geometry = Column(Geometry("MULTIPOLYGON", srid=4326))
