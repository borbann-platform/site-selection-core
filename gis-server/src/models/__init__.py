"""
SQLAlchemy models for the application.
"""

from src.models.audit_log import AuditAction, AuditLog
from src.models.chat import ChatMessage, ChatSession
from src.models.invitation import Invitation
from src.models.membership import (
    OrganizationMember,
    OrganizationRole,
    TeamMember,
    TeamRole,
)
from src.models.organization import Organization
from src.models.permission import (
    DEFAULT_PERMISSIONS,
    DEFAULT_ROLES,
    Permission,
    Role,
    RoleScope,
    role_permissions,
)
from src.models.resource_share import ResourceShare, ShareLevel, Visibility
from src.models.team import Team
from src.models.user import User

__all__ = [
    # User
    "User",
    # Chat
    "ChatSession",
    "ChatMessage",
    # Organization hierarchy
    "Organization",
    "Team",
    # Membership
    "OrganizationMember",
    "TeamMember",
    "OrganizationRole",
    "TeamRole",
    # Invitations
    "Invitation",
    # Permissions/RBAC
    "Permission",
    "Role",
    "RoleScope",
    "role_permissions",
    "DEFAULT_PERMISSIONS",
    "DEFAULT_ROLES",
    # Audit
    "AuditLog",
    "AuditAction",
    # Resource sharing/ACL
    "ResourceShare",
    "ShareLevel",
    "Visibility",
]
