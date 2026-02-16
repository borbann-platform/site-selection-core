from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
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


class ScrapedListing(Base):
    """
    Normalized listing metadata loaded from scraped JSONL files.
    Image binaries are stored in object storage and linked via ScrapedListingImage.
    """

    __tablename__ = "scraped_listings"
    __table_args__ = (
        UniqueConstraint(
            "source", "source_listing_id", name="uq_scraped_listings_source_listing"
        ),
        Index("idx_scraped_listings_source", "source"),
        Index("idx_scraped_listings_scraped_at", "scraped_at"),
        Index("idx_scraped_listings_geometry", "geometry", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_listing_id: Mapped[str] = mapped_column(Text, nullable=False)

    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_search_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    title_th: Mapped[str | None] = mapped_column(Text, nullable=True)
    title_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    property_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    property_types: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    province_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    province: Mapped[str | None] = mapped_column(String(128), nullable=True)
    district_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    district: Mapped[str | None] = mapped_column(String(128), nullable=True)
    subdistrict_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subdistrict: Mapped[str | None] = mapped_column(String(128), nullable=True)

    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    price_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_end: Mapped[float | None] = mapped_column(Float, nullable=True)

    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry = mapped_column(Geometry("POINT", srid=4326), nullable=True)

    main_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ScrapedListingImage(Base):
    """
    Listing image catalog and object-storage sync metadata.
    """

    __tablename__ = "scraped_listing_images"
    __table_args__ = (
        UniqueConstraint(
            "listing_id", "source_url", name="uq_scraped_listing_images_listing_url"
        ),
        Index(
            "idx_scraped_listing_images_fetch_status",
            "fetch_status",
        ),
        Index("idx_scraped_listing_images_sha256", "checksum_sha256"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("scraped_listings.id", ondelete="CASCADE"),
        nullable=False,
    )

    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    image_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    storage_bucket: Mapped[str | None] = mapped_column(String(128), nullable=True)
    object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_uri: Mapped[str | None] = mapped_column(Text, nullable=True)

    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    fetch_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    last_http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetch_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
