"""
Audit Log model for tracking all significant actions in the system.

Used for compliance, security monitoring, and debugging.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.config.database import Base


class AuditAction(str, enum.Enum):
    """Types of actions that are logged."""

    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"
    TOKEN_REFRESH = "token_refresh"

    # CRUD operations
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"

    # Permission changes
    PERMISSION_GRANT = "permission_grant"
    PERMISSION_REVOKE = "permission_revoke"
    ROLE_CHANGE = "role_change"

    # Membership changes
    ORG_JOIN = "org_join"
    ORG_LEAVE = "org_leave"
    TEAM_JOIN = "team_join"
    TEAM_LEAVE = "team_leave"
    INVITE_SENT = "invite_sent"
    INVITE_ACCEPTED = "invite_accepted"
    INVITE_REVOKED = "invite_revoked"

    # Organization management
    ORG_CREATED = "org_created"
    ORG_UPDATED = "org_updated"
    ORG_DELETED = "org_deleted"
    TEAM_CREATED = "team_created"
    TEAM_UPDATED = "team_updated"
    TEAM_DELETED = "team_deleted"

    # Resource access
    RESOURCE_ACCESSED = "resource_accessed"
    RESOURCE_SHARED = "resource_shared"
    RESOURCE_UNSHARED = "resource_unshared"

    # Export actions
    DATA_EXPORTED = "data_exported"

    # Admin actions
    SYSTEM_SETTING_CHANGED = "system_setting_changed"


class AuditLog(Base):
    """
    Audit log entry - records a single action in the system.

    All significant actions should be logged here for compliance
    and security monitoring purposes.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        # Index for efficient querying by time range
        Index("ix_audit_logs_timestamp", "timestamp"),
        # Index for querying by organization
        Index("ix_audit_logs_organization_id", "organization_id"),
        # Index for querying by user
        Index("ix_audit_logs_user_id", "user_id"),
        # Composite index for common query pattern
        Index("ix_audit_logs_org_timestamp", "organization_id", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # When the action occurred
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Who performed the action (null for system actions or failed logins)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # What action was performed
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction), nullable=False, index=True
    )

    # What type of resource was affected (e.g., "user", "organization", "property")
    resource_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )

    # ID of the affected resource
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Previous state of the resource (for updates)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # New state of the resource (for creates/updates)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Request metadata
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Organization context (for multi-tenant filtering)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Additional metadata
    metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    user = relationship("User")
    organization = relationship("Organization")

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, user_id={self.user_id})>"
