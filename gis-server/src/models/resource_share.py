"""
Resource sharing model for ACL (Access Control Lists).

Allows resources to be shared with specific users or teams
beyond the default visibility settings.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.config.database import Base


class ShareLevel(str, enum.Enum):
    """Level of access granted by the share."""

    VIEW = "view"  # Can view the resource
    EDIT = "edit"  # Can view and edit the resource
    ADMIN = "admin"  # Can view, edit, and manage sharing


class Visibility(str, enum.Enum):
    """Default visibility level for a resource."""

    PRIVATE = "private"  # Only owner can access
    TEAM = "team"  # Team members can access
    ORGANIZATION = "organization"  # All org members can access


class ResourceShare(Base):
    """
    Resource share entry - grants access to a resource.

    Can share with either a user or a team (not both).
    """

    __tablename__ = "resource_shares"
    __table_args__ = (
        # Ensure a resource can only be shared once to the same user/team
        UniqueConstraint(
            "resource_type",
            "resource_id",
            "shared_with_user_id",
            name="uq_resource_share_user",
        ),
        UniqueConstraint(
            "resource_type",
            "resource_id",
            "shared_with_team_id",
            name="uq_resource_share_team",
        ),
        # Index for finding all shares for a resource
        Index("ix_resource_shares_resource", "resource_type", "resource_id"),
        # Index for finding all shares for a user
        Index("ix_resource_shares_user", "shared_with_user_id"),
        # Index for finding all shares for a team
        Index("ix_resource_shares_team", "shared_with_team_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # What type of resource is being shared (e.g., "chat_session", "valuation")
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # ID of the resource being shared
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Who the resource is shared with (one of these must be set)
    shared_with_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    shared_with_team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=True,
    )

    # What level of access is granted
    permission_level: Mapped[ShareLevel] = mapped_column(
        Enum(ShareLevel), nullable=False, default=ShareLevel.VIEW
    )

    # Who shared the resource
    shared_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # When the resource was shared
    shared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Optional expiry for the share
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    shared_with_user = relationship("User", foreign_keys=[shared_with_user_id])
    shared_with_team = relationship("Team")
    sharer = relationship("User", foreign_keys=[shared_by])

    @property
    def is_expired(self) -> bool:
        """Check if the share has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(tz=self.expires_at.tzinfo) > self.expires_at

    def __repr__(self) -> str:
        target = (
            f"user={self.shared_with_user_id}"
            if self.shared_with_user_id
            else f"team={self.shared_with_team_id}"
        )
        return f"<ResourceShare(resource={self.resource_type}:{self.resource_id}, {target})>"
