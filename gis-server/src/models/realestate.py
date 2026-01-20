from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
import uuid


class CondoProject(Base):
    __tablename__ = "condo_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_base_url: Mapped[str | None] = mapped_column(
        String, unique=True, nullable=True
    )
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_date: Mapped[str | None] = mapped_column(String, nullable=True)
    floors: Mapped[str | None] = mapped_column(String, nullable=True)
    units: Mapped[str | None] = mapped_column(String, nullable=True)
    buildings: Mapped[str | None] = mapped_column(String, nullable=True)
    price_sale: Mapped[str | None] = mapped_column(String, nullable=True)
    sale_units: Mapped[str | None] = mapped_column(String, nullable=True)
    price_rent: Mapped[str | None] = mapped_column(String, nullable=True)
    rent_units: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    facilities: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    nearby_projects: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    images: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    units_for_sale: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    units_for_rent: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    market_stats: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    geometry = mapped_column(Geometry("POINT", srid=4326), nullable=True)


class RealEstateListing(Base):
    __tablename__ = "real_estate_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_file: Mapped[str | None] = mapped_column(String, nullable=True)

    title: Mapped[str | None] = mapped_column(String, nullable=True)
    property_type: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)

    bathrooms: Mapped[str | None] = mapped_column(String, nullable=True)
    bedrooms: Mapped[str | None] = mapped_column(String, nullable=True)
    floors: Mapped[str | None] = mapped_column(String, nullable=True)
    total_floors: Mapped[str | None] = mapped_column(String, nullable=True)
    usable_area_sqm: Mapped[str | None] = mapped_column(String, nullable=True)
    land_size_sqw: Mapped[str | None] = mapped_column(String, nullable=True)

    facilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    highlights: Mapped[str | None] = mapped_column(Text, nullable=True)
    furniture_status: Mapped[str | None] = mapped_column(String, nullable=True)
    developer: Mapped[str | None] = mapped_column(String, nullable=True)
    completion_date: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)

    images: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    last_updated: Mapped[str | None] = mapped_column(String, nullable=True)

    geometry = mapped_column(Geometry("POINT", srid=4326), nullable=True)


class HousePrice(Base):
    """
    House price data from Treasury Department (กรมธนารักษ์).
    Contains appraised values for houses/townhouses in Bangkok.
    """

    __tablename__ = "house_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    updated_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    land_type_desc: Mapped[str | None] = mapped_column(String, nullable=True)
    building_style_desc: Mapped[str | None] = mapped_column(String, nullable=True)
    tumbon: Mapped[str | None] = mapped_column(String, nullable=True)
    amphur: Mapped[str | None] = mapped_column(String, nullable=True)
    province: Mapped[str | None] = mapped_column(String, nullable=True)
    village: Mapped[str | None] = mapped_column(String, nullable=True)

    building_age: Mapped[float | None] = mapped_column(Float, nullable=True)
    land_area: Mapped[float | None] = mapped_column(Float, nullable=True)
    building_area: Mapped[float | None] = mapped_column(Float, nullable=True)
    no_of_floor: Mapped[float | None] = mapped_column(Float, nullable=True)

    total_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    geometry = mapped_column(Geometry("POINT", srid=4326), nullable=True)


class UserProperty(Base):
    """
    User-submitted properties for AI valuation.
    Stores property details and valuation history.
    """

    __tablename__ = "user_properties"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # User info (optional - can be linked to auth system later)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    # Property details
    building_style: Mapped[str | None] = mapped_column(String, nullable=True)
    building_area: Mapped[float | None] = mapped_column(Float, nullable=True)
    land_area: Mapped[float | None] = mapped_column(Float, nullable=True)
    no_of_floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    building_age: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Location
    amphur: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    tumbon: Mapped[str | None] = mapped_column(String, nullable=True)
    village: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # User-provided price (for comparison)
    asking_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    # AI Valuation results
    estimated_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_type: Mapped[str | None] = mapped_column(String, nullable=True)
    h3_index: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    is_cold_start: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Valuation metadata (stored as JSON for flexibility)
    valuation_factors: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    market_insights: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Geometry
    geometry = mapped_column(Geometry("POINT", srid=4326), nullable=True)
