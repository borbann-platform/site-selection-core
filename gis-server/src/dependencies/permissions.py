"""
Permission checking dependencies for enterprise RBAC.

Provides FastAPI dependencies for:
- Requiring specific permissions
- Requiring organization roles
- Requiring team roles
- System admin checks
- Organization context
"""

import uuid
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from src.config.database import get_db_session
from src.dependencies.auth import get_current_active_user
from src.models.membership import (
    OrganizationMember,
    OrganizationRole,
    TeamMember,
    TeamRole,
)
from src.models.organization import Organization
from src.models.permission import Permission, Role
from src.models.team import Team
from src.models.user import User


class PermissionDenied(HTTPException):
    """Exception raised when user lacks required permission."""

    def __init__(self, detail: str = "Permission denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class OrganizationContext:
    """
    Context containing organization and user's membership/role.

    This is passed to route handlers that need to know the
    organization context.
    """

    def __init__(
        self,
        organization: Organization,
        membership: OrganizationMember | None,
        user: User,
    ):
        self.organization = organization
        self.membership = membership
        self.user = user

    @property
    def org_id(self) -> uuid.UUID:
        return self.organization.id

    @property
    def role(self) -> OrganizationRole | None:
        return self.membership.role if self.membership else None

    @property
    def is_owner(self) -> bool:
        return (
            self.membership is not None
            and self.membership.role == OrganizationRole.OWNER
        )

    @property
    def is_admin(self) -> bool:
        return self.membership is not None and self.membership.role in (
            OrganizationRole.OWNER,
            OrganizationRole.ADMIN,
        )

    @property
    def is_member(self) -> bool:
        return self.membership is not None


class TeamContext:
    """
    Context containing team, organization, and user's role.
    """

    def __init__(
        self,
        team: Team,
        organization: Organization,
        team_membership: TeamMember | None,
        org_membership: OrganizationMember | None,
        user: User,
    ):
        self.team = team
        self.organization = organization
        self.team_membership = team_membership
        self.org_membership = org_membership
        self.user = user

    @property
    def team_id(self) -> uuid.UUID:
        return self.team.id

    @property
    def team_role(self) -> TeamRole | None:
        return self.team_membership.role if self.team_membership else None

    @property
    def is_team_admin(self) -> bool:
        return (
            self.team_membership is not None
            and self.team_membership.role == TeamRole.ADMIN
        )

    @property
    def is_team_member(self) -> bool:
        return self.team_membership is not None


def require_system_admin(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    Dependency that requires the user to be a system admin.

    Usage:
        @router.get("/admin/...")
        def admin_endpoint(user: User = Depends(require_system_admin)):
            ...
    """
    if not current_user.is_system_admin:
        raise PermissionDenied("System administrator access required")
    return current_user


def get_org_context(
    organization_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> OrganizationContext:
    """
    Get organization context for the current user.

    This checks that the organization exists and returns the user's
    membership in that organization (if any).

    Usage:
        @router.get("/orgs/{organization_id}/...")
        def org_endpoint(org_ctx: OrganizationContext = Depends(get_org_context)):
            if not org_ctx.is_member:
                raise HTTPException(403, "Not a member of this organization")
    """
    organization = (
        db.query(Organization).filter(Organization.id == organization_id).first()
    )
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # System admins can access any organization
    if current_user.is_system_admin:
        # Create a virtual owner membership for system admins
        return OrganizationContext(
            organization=organization,
            membership=None,  # They're not a real member
            user=current_user,
        )

    # Get user's membership in this organization
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == current_user.id,
        )
        .first()
    )

    return OrganizationContext(
        organization=organization,
        membership=membership,
        user=current_user,
    )


def require_org_member(
    org_ctx: Annotated[OrganizationContext, Depends(get_org_context)],
) -> OrganizationContext:
    """
    Dependency that requires the user to be a member of the organization.
    """
    if not org_ctx.is_member and not org_ctx.user.is_system_admin:
        raise PermissionDenied("You are not a member of this organization")
    return org_ctx


def require_org_admin(
    org_ctx: Annotated[OrganizationContext, Depends(get_org_context)],
) -> OrganizationContext:
    """
    Dependency that requires the user to be an admin of the organization.
    """
    if not org_ctx.is_admin and not org_ctx.user.is_system_admin:
        raise PermissionDenied("Organization admin access required")
    return org_ctx


def require_org_owner(
    org_ctx: Annotated[OrganizationContext, Depends(get_org_context)],
) -> OrganizationContext:
    """
    Dependency that requires the user to be the owner of the organization.
    """
    if not org_ctx.is_owner and not org_ctx.user.is_system_admin:
        raise PermissionDenied("Organization owner access required")
    return org_ctx


def get_team_context(
    team_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> TeamContext:
    """
    Get team context for the current user.
    """
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    organization = (
        db.query(Organization).filter(Organization.id == team.organization_id).first()
    )
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team's organization not found",
        )

    # Get memberships
    team_membership = (
        db.query(TeamMember)
        .filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == current_user.id,
        )
        .first()
    )

    org_membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == team.organization_id,
            OrganizationMember.user_id == current_user.id,
        )
        .first()
    )

    # organization is guaranteed non-None after the check above
    assert organization is not None
    return TeamContext(
        team=team,
        organization=organization,
        team_membership=team_membership,
        org_membership=org_membership,
        user=current_user,
    )


def require_team_member(
    team_ctx: Annotated[TeamContext, Depends(get_team_context)],
) -> TeamContext:
    """
    Dependency that requires the user to be a member of the team.
    """
    # System admins and org admins can access any team
    if team_ctx.user.is_system_admin:
        return team_ctx
    if team_ctx.org_membership and team_ctx.org_membership.role in (
        OrganizationRole.OWNER,
        OrganizationRole.ADMIN,
    ):
        return team_ctx
    if not team_ctx.is_team_member:
        raise PermissionDenied("You are not a member of this team")
    return team_ctx


def require_team_admin(
    team_ctx: Annotated[TeamContext, Depends(get_team_context)],
) -> TeamContext:
    """
    Dependency that requires the user to be an admin of the team.
    """
    # System admins and org admins can manage any team
    if team_ctx.user.is_system_admin:
        return team_ctx
    if team_ctx.org_membership and team_ctx.org_membership.role in (
        OrganizationRole.OWNER,
        OrganizationRole.ADMIN,
    ):
        return team_ctx
    if not team_ctx.is_team_admin:
        raise PermissionDenied("Team admin access required")
    return team_ctx


def require_org_role(*roles: OrganizationRole) -> Callable:
    """
    Factory for creating a dependency that requires specific org roles.

    Usage:
        @router.post("/orgs/{organization_id}/settings")
        def update_settings(
            org_ctx: OrganizationContext = Depends(
                require_org_role(OrganizationRole.OWNER, OrganizationRole.ADMIN)
            )
        ):
            ...
    """

    def dependency(
        org_ctx: Annotated[OrganizationContext, Depends(get_org_context)],
    ) -> OrganizationContext:
        if org_ctx.user.is_system_admin:
            return org_ctx
        if not org_ctx.membership or org_ctx.membership.role not in roles:
            role_names = ", ".join(r.value for r in roles)
            raise PermissionDenied(f"Required organization role: {role_names}")
        return org_ctx

    return dependency


def require_team_role(*roles: TeamRole) -> Callable:
    """
    Factory for creating a dependency that requires specific team roles.
    """

    def dependency(
        team_ctx: Annotated[TeamContext, Depends(get_team_context)],
    ) -> TeamContext:
        # System admins bypass all checks
        if team_ctx.user.is_system_admin:
            return team_ctx
        # Org admins have full team access
        if team_ctx.org_membership and team_ctx.org_membership.role in (
            OrganizationRole.OWNER,
            OrganizationRole.ADMIN,
        ):
            return team_ctx
        if not team_ctx.team_membership or team_ctx.team_membership.role not in roles:
            role_names = ", ".join(r.value for r in roles)
            raise PermissionDenied(f"Required team role: {role_names}")
        return team_ctx

    return dependency


def get_user_permissions(
    user_id: uuid.UUID,
    organization_id: uuid.UUID | None,
    db: Session,
) -> set[str]:
    """
    Get all permission codes for a user in an organization.

    Permissions come from:
    1. System admin status (has all permissions)
    2. Organization membership role
    3. Team membership roles

    Note: This is a simplified implementation. A full implementation would
    query the role_permissions table and compute effective permissions.
    """
    permissions: set[str] = set()

    # Check if user is system admin
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.is_system_admin:
        # System admin has all permissions
        return {"*"}  # Wildcard for all permissions

    if not organization_id:
        return permissions

    # Get org membership and derive permissions from role
    org_membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == organization_id,
        )
        .first()
    )

    if org_membership:
        # Map organization roles to base permissions
        # This is a simplified mapping - full implementation would use the Role model
        if org_membership.role == OrganizationRole.OWNER:
            permissions.update(
                [
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
                ]
            )
        elif org_membership.role == OrganizationRole.ADMIN:
            permissions.update(
                [
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
                ]
            )
        elif org_membership.role == OrganizationRole.MEMBER:
            permissions.update(
                [
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
                ]
            )

    return permissions


def require_permission(*permission_codes: str) -> Callable:
    """
    Factory for creating a dependency that requires specific permissions.

    Usage:
        @router.post("/analytics/export")
        def export_analytics(
            user: User = Depends(require_permission("analytics.export", "data.export"))
        ):
            ...
    """

    def dependency(
        current_user: Annotated[User, Depends(get_current_active_user)],
        db: Annotated[Session, Depends(get_db_session)],
        x_organization_id: uuid.UUID | None = Header(None, alias="X-Organization-ID"),
    ) -> User:
        # System admins have all permissions
        if current_user.is_system_admin:
            return current_user

        # Get user's permissions
        org_id = x_organization_id or current_user.default_organization_id
        user_permissions = get_user_permissions(current_user.id, org_id, db)

        # Check if user has any of the required permissions
        required = set(permission_codes)
        if not required.intersection(user_permissions):
            raise PermissionDenied(
                f"Missing required permission: {', '.join(required)}"
            )

        return current_user

    return dependency
