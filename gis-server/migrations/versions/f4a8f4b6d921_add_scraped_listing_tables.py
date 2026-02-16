"""add scraped listing tables

Revision ID: f4a8f4b6d921
Revises: ba57660e028f
Create Date: 2026-02-13 12:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
from geoalchemy2 import Geometry
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f4a8f4b6d921"
down_revision: Union[str, Sequence[str], None] = "ba57660e028f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create normalized scraped listing + image metadata tables."""

    op.create_table(
        "scraped_listings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_listing_id", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("detail_url", sa.Text(), nullable=True),
        sa.Column("source_search_url", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("title_th", sa.Text(), nullable=True),
        sa.Column("title_en", sa.Text(), nullable=True),
        sa.Column("property_type", sa.String(length=128), nullable=True),
        sa.Column("property_types", sa.JSON(), nullable=True),
        sa.Column("province_id", sa.Integer(), nullable=True),
        sa.Column("province", sa.String(length=128), nullable=True),
        sa.Column("district_id", sa.Integer(), nullable=True),
        sa.Column("district", sa.String(length=128), nullable=True),
        sa.Column("subdistrict_id", sa.Integer(), nullable=True),
        sa.Column("subdistrict", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("price_start", sa.Float(), nullable=True),
        sa.Column("price_end", sa.Float(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("geometry", Geometry("POINT", srid=4326), nullable=True),
        sa.Column("main_image_url", sa.Text(), nullable=True),
        sa.Column("image_count", sa.Integer(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "source", "source_listing_id", name="uq_scraped_listings_source_listing"
        ),
    )
    op.create_index(
        "idx_scraped_listings_source", "scraped_listings", ["source"], unique=False
    )
    op.create_index(
        "idx_scraped_listings_scraped_at",
        "scraped_listings",
        ["scraped_at"],
        unique=False,
    )
    op.create_index(
        "idx_scraped_listings_geometry",
        "scraped_listings",
        ["geometry"],
        unique=False,
        postgresql_using="gist",
    )

    op.create_table(
        "scraped_listing_images",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("listing_id", sa.BigInteger(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_host", sa.String(length=255), nullable=True),
        sa.Column("image_role", sa.String(length=32), nullable=True),
        sa.Column("image_order", sa.Integer(), nullable=True),
        sa.Column(
            "is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("storage_bucket", sa.String(length=128), nullable=True),
        sa.Column("object_key", sa.Text(), nullable=True),
        sa.Column("object_uri", sa.Text(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column(
            "fetch_status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("last_http_status", sa.Integer(), nullable=True),
        sa.Column("fetch_error", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"], ["scraped_listings.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "listing_id",
            "source_url",
            name="uq_scraped_listing_images_listing_url",
        ),
    )
    op.create_index(
        "idx_scraped_listing_images_fetch_status",
        "scraped_listing_images",
        ["fetch_status"],
        unique=False,
    )
    op.create_index(
        "idx_scraped_listing_images_sha256",
        "scraped_listing_images",
        ["checksum_sha256"],
        unique=False,
    )


def downgrade() -> None:
    """Drop normalized scraped listing + image metadata tables."""

    op.drop_index(
        "idx_scraped_listing_images_sha256", table_name="scraped_listing_images"
    )
    op.drop_index(
        "idx_scraped_listing_images_fetch_status", table_name="scraped_listing_images"
    )
    op.drop_table("scraped_listing_images")

    op.drop_index("idx_scraped_listings_geometry", table_name="scraped_listings")
    op.drop_index("idx_scraped_listings_scraped_at", table_name="scraped_listings")
    op.drop_index("idx_scraped_listings_source", table_name="scraped_listings")
    op.drop_table("scraped_listings")
