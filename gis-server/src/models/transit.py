from geoalchemy2 import Geometry
from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base


class TransitStop(Base):
    __tablename__ = "transit_stops"

    stop_id: Mapped[str] = mapped_column(String, primary_key=True)
    stop_name: Mapped[str | None] = mapped_column(String, nullable=True)
    zone_id: Mapped[str | None] = mapped_column(String, nullable=True)
    wheelchair_boarding: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry = mapped_column(Geometry("POINT", srid=4326, spatial_index=False), nullable=True)

    __table_args__ = (
        Index("idx_transit_stops_geometry", "geometry", postgresql_using="gist"),
    )


class TransitShape(Base):
    __tablename__ = "transit_shapes"

    shape_id: Mapped[str] = mapped_column(String, primary_key=True)
    geometry = mapped_column(Geometry("LINESTRING", srid=4326), nullable=True)


class TransitRoute(Base):
    """GTFS routes table - defines transit lines (BTS, MRT, buses, etc.)"""

    __tablename__ = "transit_routes"

    route_id: Mapped[str] = mapped_column(String, primary_key=True)
    agency_id: Mapped[str | None] = mapped_column(String, nullable=True)
    route_short_name: Mapped[str | None] = mapped_column(String, nullable=True)
    route_long_name: Mapped[str | None] = mapped_column(String, nullable=True)
    route_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    route_color: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)


class TransitTrip(Base):
    """GTFS trips table - links routes to shapes"""

    __tablename__ = "transit_trips"

    trip_id: Mapped[str] = mapped_column(String, primary_key=True)
    route_id: Mapped[str | None] = mapped_column(String, nullable=True)
    shape_id: Mapped[str | None] = mapped_column(String, nullable=True)
    trip_headsign: Mapped[str | None] = mapped_column(String, nullable=True)
    direction_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
