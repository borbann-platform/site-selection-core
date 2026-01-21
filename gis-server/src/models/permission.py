"""
Permission and Role models for RBAC (Role-Based Access Control).

Permissions define what actions can be performed on which resources.
Roles group permissions together and can be assigned at different scopes
(system, organization, team).
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Table, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.config.database import Base


class RoleScope(str, enum.Enum):
    """Scope at which a role applies."""

    SYSTEM = "system"  # System-wide role (e.g., system admin)
    ORGANIZATION = "organization"  # Organization-level role
    TEAM = "team"  # Team-level role


# Association table for role-permission many-to-many relationship
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    mapped_column(
        "role_id",
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    mapped_column(
        "permission_id",
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Permission(Base):
    """
    Permission model - defines a specific action on a resource.

    Format: resource:action (e.g., "property:read", "valuation:run")
    """

    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    resource: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    roles: Mapped[list["Role"]] = relationship(
        "Role", secondary=role_permissions, back_populates="permissions"
    )

    def __repr__(self) -> str:
        return f"<Permission(name={self.name})>"


class Role(Base):
    """
    Role model - groups permissions together.

    Roles can be:
    - System default roles (built-in, cannot be deleted)
    - Custom organization roles (created by org admins)
    """

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[RoleScope] = mapped_column(
        Enum(RoleScope), nullable=False, default=RoleScope.ORGANIZATION
    )

    # If null, this is a system-wide role; otherwise, it's specific to an organization
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Whether this is a built-in system role
    is_system_default: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    permissions: Mapped[list[Permission]] = relationship(
        "Permission", secondary=role_permissions, back_populates="roles"
    )
    organization = relationship("Organization")

    def __repr__(self) -> str:
        return f"<Role(name={self.name}, scope={self.scope})>"


# Default permissions to seed in the database
DEFAULT_PERMISSIONS = [
    # Property
    ("property:read", "property", "read", "View properties"),
    ("property:write", "property", "write", "Create/edit properties"),
    ("property:delete", "property", "delete", "Delete properties"),
    ("property:export", "property", "export", "Export property data"),
    # Valuation
    ("valuation:run", "valuation", "run", "Run valuations"),
    ("valuation:export", "valuation", "export", "Export valuations"),
    # Analytics
    ("analytics:read", "analytics", "read", "View analytics"),
    ("analytics:export", "analytics", "export", "Export analytics"),
    # Chat
    ("chat:access", "chat", "access", "Use AI chat"),
    ("chat:export", "chat", "export", "Export chat history"),
    # Site Analysis
    ("site:analyze", "site", "analyze", "Run site analysis"),
    ("catchment:analyze", "catchment", "analyze", "Run catchment analysis"),
    # Location Intelligence
    ("location:read", "location", "read", "View location intelligence"),
    # Predictions
    ("prediction:run", "prediction", "run", "Run price predictions"),
    # Transit
    ("transit:read", "transit", "read", "View transit data"),
    # Projects
    ("project:read", "project", "read", "View projects"),
    ("project:write", "project", "write", "Create/edit projects"),
    ("project:delete", "project", "delete", "Delete projects"),
    # Team Management
    ("team:read", "team", "read", "View team info"),
    ("team:manage", "team", "manage", "Manage team settings"),
    ("team:invite", "team", "invite", "Invite team members"),
    # Organization Management
    ("org:read", "org", "read", "View org info"),
    ("org:manage", "org", "manage", "Manage org settings"),
    ("org:billing", "org", "billing", "Manage billing"),
    # System (super admin)
    ("system:admin", "system", "admin", "Full system access"),
    ("audit:read", "audit", "read", "View audit logs"),
]


# Default roles with their permissions
DEFAULT_ROLES = {
    "system_admin": {
        "scope": RoleScope.SYSTEM,
        "description": "System administrator with full access to all features",
        "permissions": ["system:admin"],  # Has all permissions implicitly
    },
    "org_owner": {
        "scope": RoleScope.ORGANIZATION,
        "description": "Organization owner with full control",
        "permissions": [
            "property:read",
            "property:write",
            "property:delete",
            "property:export",
            "valuation:run",
            "valuation:export",
            "analytics:read",
            "analytics:export",
            "chat:access",
            "chat:export",
            "site:analyze",
            "catchment:analyze",
            "location:read",
            "prediction:run",
            "transit:read",
            "project:read",
            "project:write",
            "project:delete",
            "team:read",
            "team:manage",
            "team:invite",
            "org:read",
            "org:manage",
            "org:billing",
            "audit:read",
        ],
    },
    "org_admin": {
        "scope": RoleScope.ORGANIZATION,
        "description": "Organization administrator",
        "permissions": [
            "property:read",
            "property:write",
            "property:delete",
            "property:export",
            "valuation:run",
            "valuation:export",
            "analytics:read",
            "analytics:export",
            "chat:access",
            "chat:export",
            "site:analyze",
            "catchment:analyze",
            "location:read",
            "prediction:run",
            "transit:read",
            "project:read",
            "project:write",
            "project:delete",
            "team:read",
            "team:manage",
            "team:invite",
            "org:read",
            "org:manage",
            "audit:read",
        ],
    },
    "org_member": {
        "scope": RoleScope.ORGANIZATION,
        "description": "Organization member with basic access",
        "permissions": [
            "property:read",
            "valuation:run",
            "analytics:read",
            "chat:access",
            "site:analyze",
            "catchment:analyze",
            "location:read",
            "prediction:run",
            "transit:read",
            "project:read",
            "team:read",
            "org:read",
        ],
    },
    "team_admin": {
        "scope": RoleScope.TEAM,
        "description": "Team administrator",
        "permissions": [
            "property:read",
            "property:write",
            "property:export",
            "valuation:run",
            "valuation:export",
            "analytics:read",
            "analytics:export",
            "chat:access",
            "chat:export",
            "site:analyze",
            "catchment:analyze",
            "location:read",
            "prediction:run",
            "transit:read",
            "project:read",
            "project:write",
            "team:read",
            "team:manage",
            "team:invite",
        ],
    },
    "team_member": {
        "scope": RoleScope.TEAM,
        "description": "Team member with full feature access",
        "permissions": [
            "property:read",
            "property:write",
            "valuation:run",
            "analytics:read",
            "chat:access",
            "site:analyze",
            "catchment:analyze",
            "location:read",
            "prediction:run",
            "transit:read",
            "project:read",
            "project:write",
            "team:read",
        ],
    },
    "viewer": {
        "scope": RoleScope.TEAM,
        "description": "Read-only access to team resources",
        "permissions": [
            "property:read",
            "analytics:read",
            "location:read",
            "transit:read",
            "project:read",
            "team:read",
        ],
    },
}
