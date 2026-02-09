"""
Invitation model for inviting users to organizations and teams.
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.config.database import Base
from src.models.membership import OrganizationRole, TeamRole


def generate_invite_token() -> str:
    """Generate a secure random token for invitation links."""
    return secrets.token_urlsafe(32)


def default_expiry() -> datetime:
    """Default expiry time is 7 days from now."""
    return datetime.now(timezone.utc) + timedelta(days=7)


class Invitation(Base):
    """
    Invitation model for inviting users to organizations and teams.

    An invitation can be:
    - Organization-only: User joins the organization
    - Organization + Team: User joins both the organization and a specific team
    """

    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Email of the person being invited
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Organization to join
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Optional team to join
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Role in the organization
    org_role: Mapped[OrganizationRole] = mapped_column(
        Enum(OrganizationRole), nullable=False, default=OrganizationRole.MEMBER
    )

    # Role in the team (if team_id is set)
    team_role: Mapped[TeamRole | None] = mapped_column(Enum(TeamRole), nullable=True)

    # Who sent this invitation
    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Unique token for the invitation link
    token: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        default=generate_invite_token,
    )

    # When the invitation expires
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=default_expiry
    )

    # When the invitation was accepted (null if not yet accepted)
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    organization = relationship("Organization")
    team = relationship("Team")
    inviter = relationship("User")

    @property
    def is_expired(self) -> bool:
        """Check if the invitation has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_accepted(self) -> bool:
        """Check if the invitation has been accepted."""
        return self.accepted_at is not None

    @property
    def is_valid(self) -> bool:
        """Check if the invitation is still valid (not expired and not accepted)."""
        return not self.is_expired and not self.is_accepted

    def __repr__(self) -> str:
        return f"<Invitation(id={self.id}, email={self.email}, org_id={self.organization_id})>"
