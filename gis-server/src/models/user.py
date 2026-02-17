"""
User model with enterprise authentication support.

Extends basic user with system admin flag and organization relationships.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.config.database import Base

if TYPE_CHECKING:
    from src.models.agent_runtime_credential import AgentRuntimeCredential
    from src.models.membership import OrganizationMember, TeamMember
    from src.models.organization import Organization


class User(Base):
    """
    User model with enterprise authentication support.

    Attributes:
        is_system_admin: System-level admin (can manage all organizations)
        default_organization_id: User's default/primary organization
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Enterprise auth fields
    is_system_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    default_organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    default_organization: Mapped["Organization | None"] = relationship(
        "Organization", foreign_keys=[default_organization_id]
    )
    organization_memberships: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember",
        foreign_keys="OrganizationMember.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    team_memberships: Mapped[list["TeamMember"]] = relationship(
        "TeamMember",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    agent_runtime_credential: Mapped["AgentRuntimeCredential | None"] = relationship(
        "AgentRuntimeCredential",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )

    @property
    def full_name(self) -> str:
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
