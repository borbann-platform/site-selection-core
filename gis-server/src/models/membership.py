"""
Membership models for organization and team membership.

Defines the relationship between users, organizations, and teams,
including their roles within each.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.config.database import Base

if TYPE_CHECKING:
    from src.models.organization import Organization
    from src.models.team import Team
    from src.models.user import User


class OrganizationRole(str, enum.Enum):
    """Roles for organization membership."""

    OWNER = "owner"  # Full control, billing, can delete org
    ADMIN = "admin"  # Manage teams, users, settings
    MEMBER = "member"  # Basic org access


class TeamRole(str, enum.Enum):
    """Roles for team membership."""

    ADMIN = "admin"  # Manage team, invite users
    MEMBER = "member"  # Full access to team resources
    VIEWER = "viewer"  # Read-only access to team resources


class OrganizationMember(Base):
    """
    Organization membership - links users to organizations with roles.
    """

    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_org_member"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[OrganizationRole] = mapped_column(
        Enum(OrganizationRole), nullable=False, default=OrganizationRole.MEMBER
    )

    # Who invited this user (null if they created the org or self-joined)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User", foreign_keys=[user_id], back_populates="organization_memberships"
    )
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="members"
    )
    inviter: Mapped["User | None"] = relationship("User", foreign_keys=[invited_by])

    def __repr__(self) -> str:
        return f"<OrganizationMember(user_id={self.user_id}, org_id={self.organization_id}, role={self.role})>"


class TeamMember(Base):
    """
    Team membership - links users to teams with roles.
    """

    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("user_id", "team_id", name="uq_team_member"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[TeamRole] = mapped_column(
        Enum(TeamRole), nullable=False, default=TeamRole.MEMBER
    )

    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="team_memberships")
    team: Mapped["Team"] = relationship("Team", back_populates="members")

    def __repr__(self) -> str:
        return f"<TeamMember(user_id={self.user_id}, team_id={self.team_id}, role={self.role})>"
