from geoalchemy2 import Geometry
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base


class TransitStop(Base):
    __tablename__ = "transit_stops"

    stop_id: Mapped[str] = mapped_column(String, primary_key=True)
    stop_name: Mapped[str | None] = mapped_column(String, nullable=True)
    zone_id: Mapped[str | None] = mapped_column(String, nullable=True)
    wheelchair_boarding: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry = mapped_column(Geometry("POINT", srid=4326), nullable=True)


class TransitShape(Base):
    __tablename__ = "transit_shapes"

    shape_id: Mapped[str] = mapped_column(String, primary_key=True)
    geometry = mapped_column(Geometry("LINESTRING", srid=4326), nullable=True)
