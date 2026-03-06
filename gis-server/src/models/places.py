from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base


class BusShelter(Base):
    __tablename__ = "bus_shelters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contract_number: Mapped[str | None] = mapped_column(String, nullable=True)
    project_name: Mapped[str | None] = mapped_column(String, nullable=True)
    location_name: Mapped[str | None] = mapped_column(String, nullable=True)
    code_shelter: Mapped[str | None] = mapped_column(String, nullable=True)
    asset_code: Mapped[str | None] = mapped_column(String, nullable=True)
    district: Mapped[str | None] = mapped_column(String, nullable=True)
    shelter_type: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=True
    )

    __table_args__ = (
        Index("idx_bus_shelters_geometry", "geometry", postgresql_using="gist"),
    )


class School(Base):
    __tablename__ = "schools"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # IDSCHOOL
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    district: Mapped[str | None] = mapped_column(String, nullable=True)
    subdistrict: Mapped[str | None] = mapped_column(String, nullable=True)
    level: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=True
    )

    __table_args__ = (
        Index("idx_schools_geometry", "geometry", postgresql_using="gist"),
    )


class PoliceStation(Base):
    __tablename__ = "police_stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    district: Mapped[str | None] = mapped_column(String, nullable=True)
    division: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=True
    )

    __table_args__ = (
        Index("idx_police_stations_geometry", "geometry", postgresql_using="gist"),
    )


class Museum(Base):
    __tablename__ = "museums"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    district: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=True
    )

    __table_args__ = (
        Index("idx_museums_geometry", "geometry", postgresql_using="gist"),
    )


class GasStation(Base):
    __tablename__ = "gas_stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    district: Mapped[str | None] = mapped_column(String, nullable=True)
    brand_type: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=True
    )

    __table_args__ = (
        Index("idx_gas_stations_geometry", "geometry", postgresql_using="gist"),
    )


class TrafficPoint(Base):
    __tablename__ = "traffic_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    morning_time: Mapped[str | None] = mapped_column(String, nullable=True)
    afternoon_time: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=True
    )

    __table_args__ = (
        Index("idx_traffic_points_geometry", "geometry", postgresql_using="gist"),
    )


class WaterTransport(Base):
    __tablename__ = "water_transport_piers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    geometry = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=True
    )

    __table_args__ = (
        Index(
            "idx_water_transport_piers_geometry", "geometry", postgresql_using="gist"
        ),
    )


class TouristAttraction(Base):
    __tablename__ = "tourist_attractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    travel_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    open_time: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=True
    )

    __table_args__ = (
        Index("idx_tourist_attractions_geometry", "geometry", postgresql_using="gist"),
    )


class ContributedPOI(Base):
    __tablename__ = "contributed_pois"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name_th: Mapped[str | None] = mapped_column(String, nullable=True)
    name_en: Mapped[str | None] = mapped_column(String, nullable=True)
    address_th: Mapped[str | None] = mapped_column(Text, nullable=True)
    address_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    telephone: Mapped[str | None] = mapped_column(String, nullable=True)
    website: Mapped[str | None] = mapped_column(String, nullable=True)
    lastupdate: Mapped[str | None] = mapped_column(String, nullable=True)
    poi_type: Mapped[str | None] = mapped_column(String, nullable=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=True
    )

    __table_args__ = (
        Index("idx_contributed_pois_geometry", "geometry", postgresql_using="gist"),
    )


class OsmPOI(Base):
    """
    POIs extracted from OpenStreetMap thailand-260111.osm.pbf.
    Extends coverage beyond Bangkok-only datasets to match housing data extent.
    """

    __tablename__ = "osm_pois"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    osm_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    osm_type: Mapped[str | None] = mapped_column(String, nullable=True)  # node/way
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    name_en: Mapped[str | None] = mapped_column(String, nullable=True)
    name_th: Mapped[str | None] = mapped_column(String, nullable=True)
    poi_type: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    amenity: Mapped[str | None] = mapped_column(String, nullable=True)
    shop: Mapped[str | None] = mapped_column(String, nullable=True)
    brand: Mapped[str | None] = mapped_column(String, nullable=True)
    operator: Mapped[str | None] = mapped_column(String, nullable=True)
    # Dedup tracking
    is_duplicate: Mapped[bool] = mapped_column(default=False, nullable=False)
    duplicate_of: Mapped[str | None] = mapped_column(String, nullable=True)
    duplicate_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=True
    )

    __table_args__ = (
        Index("idx_osm_pois_geometry", "geometry", postgresql_using="gist"),
        Index("idx_osm_pois_poi_type", "poi_type"),
        Index("idx_osm_pois_is_duplicate", "is_duplicate"),
    )
