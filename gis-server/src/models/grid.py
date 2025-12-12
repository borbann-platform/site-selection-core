from geoalchemy2 import Geometry
from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base


class SuitabilityGrid(Base):
    __tablename__ = "suitability_grid"

    h3_index: Mapped[str] = mapped_column(String, primary_key=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    population: Mapped[float | None] = mapped_column(Float, nullable=True)
    poi_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    geometry = mapped_column(Geometry("POLYGON", srid=4326), nullable=True)
