"""
Organization management API routes.
Provides endpoints for managing organizations and their members.
"""

import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.config.database import get_db_session
from src.dependencies.auth import get_current_active_user
from src.dependencies.permissions import (
    OrganizationContext,
    PermissionDenied,
    get_org_context,
    require_org_admin,
    require_org_member,
    require_org_owner,
    require_system_admin,
)
from src.models.membership import OrganizationMember, OrganizationRole
from src.models.organization import Organization
from src.models.user import User

router = APIRouter(prefix="/organizations", tags=["Organizations"])


# ============= Request/Response Schemas =============


class CreateOrganizationRequest(BaseModel):
    """Request body for creating a new organization."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str | None = Field(
        None,
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$",
        description="URL-friendly identifier. Auto-generated from name if not provided.",
    )
    description: str | None = None
    allow_open_signup: bool = False


class UpdateOrganizationRequest(BaseModel):
    """Request body for updating an organization."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    allow_open_signup: bool | None = None
    settings: dict | None = None


class OrganizationResponse(BaseModel):
    """Response schema for an organization."""

    id: str
    name: str
    slug: str
    description: str | None
    is_active: bool
    allow_open_signup: bool
    created_at: str | None
    updated_at: str | None
    member_count: int = 0
    team_count: int = 0


class OrganizationMemberResponse(BaseModel):
    """Response schema for an organization member."""

    id: str
    user_id: str
    email: str
    name: str | None
    role: str
    joined_at: str | None


class OrganizationListResponse(BaseModel):
    """Response schema for listing organizations."""

    items: list[OrganizationResponse]
    total: int


class AddMemberRequest(BaseModel):
    """Request body for adding a member to an organization."""

    user_id: str = Field(..., description="UUID of the user to add")
    role: OrganizationRole = OrganizationRole.MEMBER


class UpdateMemberRoleRequest(BaseModel):
    """Request body for updating a member's role."""

    role: OrganizationRole


# ============= Helper Functions =============


def generate_slug(name: str) -> str:
    """Generate a URL-friendly slug from a name."""
    # Convert to lowercase, replace spaces with hyphens, remove special chars
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    slug = slug.strip("-")
    return slug[:100] if slug else "org"


def org_to_response(org: Organization, db: Session) -> OrganizationResponse:
    """Convert an Organization model to a response schema."""
    member_count = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == org.id)
        .count()
    )
    team_count = len(org.teams) if org.teams else 0

    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        description=org.description,
        is_active=org.is_active,
        allow_open_signup=org.allow_open_signup,
        created_at=org.created_at.isoformat() if org.created_at else None,
        updated_at=org.updated_at.isoformat() if org.updated_at else None,
        member_count=member_count,
        team_count=team_count,
    )


# ============= Endpoints =============


@router.get("", response_model=OrganizationListResponse)
async def list_organizations(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    List organizations the current user is a member of.
    System admins can see all organizations.
    """
    if current_user.is_system_admin:
        # System admins see all organizations
        query = db.query(Organization).filter(Organization.is_active == True)
    else:
        # Regular users only see orgs they're members of
        query = (
            db.query(Organization)
            .join(
                OrganizationMember,
                OrganizationMember.organization_id == Organization.id,
            )
            .filter(
                OrganizationMember.user_id == current_user.id,
                Organization.is_active == True,
            )
        )

    total = query.count()
    organizations = query.offset(offset).limit(limit).all()

    return OrganizationListResponse(
        items=[org_to_response(org, db) for org in organizations],
        total=total,
    )


@router.post("", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    request: CreateOrganizationRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """
    Create a new organization.
    The creating user becomes the owner.
    """
    # Generate slug if not provided
    slug = request.slug or generate_slug(request.name)

    # Check if slug already exists
    existing = db.query(Organization).filter(Organization.slug == slug).first()
    if existing:
        # Try to make it unique
        base_slug = slug
        counter = 1
        while existing:
            slug = f"{base_slug}-{counter}"
            existing = db.query(Organization).filter(Organization.slug == slug).first()
            counter += 1
            if counter > 100:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Could not generate unique slug",
                )

    # Create organization
    organization = Organization(
        name=request.name,
        slug=slug,
        description=request.description,
        allow_open_signup=request.allow_open_signup,
    )
    db.add(organization)
    db.flush()  # Get the ID

    # Add creator as owner
    membership = OrganizationMember(
        user_id=current_user.id,
        organization_id=organization.id,
        role=OrganizationRole.OWNER,
    )
    db.add(membership)

    # Set as user's default org if they don't have one
    if current_user.default_organization_id is None:
        current_user.default_organization_id = organization.id

    db.commit()
    db.refresh(organization)

    return org_to_response(organization, db)


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    org_ctx: Annotated[OrganizationContext, Depends(require_org_member)],
    db: Session = Depends(get_db_session),
):
    """
    Get organization details.
    Requires membership in the organization.
    """
    return org_to_response(org_ctx.organization, db)


@router.patch("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    request: UpdateOrganizationRequest,
    org_ctx: Annotated[OrganizationContext, Depends(require_org_admin)],
    db: Session = Depends(get_db_session),
):
    """
    Update organization details.
    Requires admin role in the organization.
    """
    org = org_ctx.organization

    if request.name is not None:
        org.name = request.name
    if request.description is not None:
        org.description = request.description
    if request.allow_open_signup is not None:
        org.allow_open_signup = request.allow_open_signup
    if request.settings is not None:
        org.settings = request.settings

    db.commit()
    db.refresh(org)

    return org_to_response(org, db)


@router.delete("/{organization_id}", status_code=204)
async def delete_organization(
    org_ctx: Annotated[OrganizationContext, Depends(require_org_owner)],
    db: Session = Depends(get_db_session),
):
    """
    Delete an organization.
    Requires owner role in the organization.
    This is a soft delete (sets is_active to False).
    """
    org = org_ctx.organization
    org.is_active = False
    db.commit()
    return None


# ============= Member Management =============


@router.get(
    "/{organization_id}/members", response_model=list[OrganizationMemberResponse]
)
async def list_organization_members(
    org_ctx: Annotated[OrganizationContext, Depends(require_org_member)],
    db: Session = Depends(get_db_session),
):
    """
    List all members of an organization.
    Requires membership in the organization.
    """
    members = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == org_ctx.org_id)
        .all()
    )

    result = []
    for member in members:
        user = db.query(User).filter(User.id == member.user_id).first()
        if user:
            result.append(
                OrganizationMemberResponse(
                    id=str(member.id),
                    user_id=str(member.user_id),
                    email=user.email,
                    name=user.full_name,
                    role=member.role.value,
                    joined_at=member.joined_at.isoformat()
                    if member.joined_at
                    else None,
                )
            )

    return result


@router.post(
    "/{organization_id}/members",
    response_model=OrganizationMemberResponse,
    status_code=201,
)
async def add_organization_member(
    request: AddMemberRequest,
    org_ctx: Annotated[OrganizationContext, Depends(require_org_admin)],
    db: Session = Depends(get_db_session),
):
    """
    Add a member to an organization.
    Requires admin role in the organization.
    """
    try:
        user_id = uuid.UUID(request.user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        )

    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if already a member
    existing = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_ctx.org_id,
            OrganizationMember.user_id == user_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this organization",
        )

    # Cannot add as owner unless you're the owner
    if request.role == OrganizationRole.OWNER and not org_ctx.is_owner:
        raise PermissionDenied("Only owners can add other owners")

    # Create membership
    membership = OrganizationMember(
        user_id=user_id,
        organization_id=org_ctx.org_id,
        role=request.role,
        invited_by=org_ctx.user.id,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)

    return OrganizationMemberResponse(
        id=str(membership.id),
        user_id=str(user.id),
        email=user.email,
        name=user.full_name,
        role=membership.role.value,
        joined_at=membership.joined_at.isoformat() if membership.joined_at else None,
    )


@router.patch("/{organization_id}/members/{member_id}")
async def update_member_role(
    member_id: uuid.UUID,
    request: UpdateMemberRoleRequest,
    org_ctx: Annotated[OrganizationContext, Depends(require_org_admin)],
    db: Session = Depends(get_db_session),
):
    """
    Update a member's role in the organization.
    Requires admin role. Only owners can promote to owner or demote owners.
    """
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.id == member_id,
            OrganizationMember.organization_id == org_ctx.org_id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    # Check permissions for owner operations
    if membership.role == OrganizationRole.OWNER and not org_ctx.is_owner:
        raise PermissionDenied("Only owners can modify owner roles")
    if request.role == OrganizationRole.OWNER and not org_ctx.is_owner:
        raise PermissionDenied("Only owners can promote to owner")

    # Prevent removing the last owner
    if (
        membership.role == OrganizationRole.OWNER
        and request.role != OrganizationRole.OWNER
    ):
        owner_count = (
            db.query(OrganizationMember)
            .filter(
                OrganizationMember.organization_id == org_ctx.org_id,
                OrganizationMember.role == OrganizationRole.OWNER,
            )
            .count()
        )
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last owner",
            )

    membership.role = request.role
    db.commit()

    user = db.query(User).filter(User.id == membership.user_id).first()
    return OrganizationMemberResponse(
        id=str(membership.id),
        user_id=str(membership.user_id),
        email=user.email if user else "",
        name=user.full_name if user else None,
        role=membership.role.value,
        joined_at=membership.joined_at.isoformat() if membership.joined_at else None,
    )


@router.delete("/{organization_id}/members/{member_id}", status_code=204)
async def remove_organization_member(
    member_id: uuid.UUID,
    org_ctx: Annotated[OrganizationContext, Depends(require_org_admin)],
    db: Session = Depends(get_db_session),
):
    """
    Remove a member from the organization.
    Requires admin role. Only owners can remove other owners.
    Members can remove themselves.
    """
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.id == member_id,
            OrganizationMember.organization_id == org_ctx.org_id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    # Check if trying to remove an owner
    if membership.role == OrganizationRole.OWNER:
        if not org_ctx.is_owner:
            raise PermissionDenied("Only owners can remove owners")
        # Prevent removing the last owner
        owner_count = (
            db.query(OrganizationMember)
            .filter(
                OrganizationMember.organization_id == org_ctx.org_id,
                OrganizationMember.role == OrganizationRole.OWNER,
            )
            .count()
        )
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last owner",
            )

    db.delete(membership)
    db.commit()
    return None


@router.post("/{organization_id}/leave", status_code=204)
async def leave_organization(
    org_ctx: Annotated[OrganizationContext, Depends(require_org_member)],
    db: Session = Depends(get_db_session),
):
    """
    Leave an organization.
    Owners cannot leave if they are the last owner.
    """
    if not org_ctx.membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not a member of this organization",
        )

    # Prevent last owner from leaving
    if org_ctx.is_owner:
        owner_count = (
            db.query(OrganizationMember)
            .filter(
                OrganizationMember.organization_id == org_ctx.org_id,
                OrganizationMember.role == OrganizationRole.OWNER,
            )
            .count()
        )
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot leave as the last owner. Transfer ownership first.",
            )

    db.delete(org_ctx.membership)
    db.commit()
    return None
