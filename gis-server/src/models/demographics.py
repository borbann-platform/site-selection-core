from geoalchemy2 import Geometry
from sqlalchemy import Float, Integer
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base


class PopulationGrid(Base):
    __tablename__ = "population_grid"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grid_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    population_density: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)
