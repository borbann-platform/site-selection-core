"""
Invitation management API routes.
Provides endpoints for inviting users to organizations and teams.
"""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from src.config.database import get_db_session
from src.dependencies.auth import get_current_active_user
from src.dependencies.permissions import (
    OrganizationContext,
    PermissionDenied,
    get_org_context,
    require_org_admin,
    require_org_member,
)
from src.models.invitation import Invitation
from src.models.membership import (
    OrganizationMember,
    OrganizationRole,
    TeamMember,
    TeamRole,
)
from src.models.organization import Organization
from src.models.team import Team
from src.models.user import User

router = APIRouter(prefix="/invitations", tags=["Invitations"])


# ============= Request/Response Schemas =============


class CreateInvitationRequest(BaseModel):
    """Request body for creating an invitation."""

    email: EmailStr = Field(..., description="Email address to invite")
    organization_id: str = Field(..., description="UUID of the organization")
    team_id: str | None = Field(None, description="Optional team UUID to also join")
    org_role: OrganizationRole = OrganizationRole.MEMBER
    team_role: TeamRole | None = None


class InvitationResponse(BaseModel):
    """Response schema for an invitation."""

    id: str
    email: str
    organization_id: str
    organization_name: str
    team_id: str | None
    team_name: str | None
    org_role: str
    team_role: str | None
    invited_by_email: str
    token: str
    expires_at: str
    is_expired: bool
    is_accepted: bool
    created_at: str | None


class InvitationListResponse(BaseModel):
    """Response schema for listing invitations."""

    items: list[InvitationResponse]
    total: int


class AcceptInvitationRequest(BaseModel):
    """Request body for accepting an invitation."""

    token: str = Field(..., description="Invitation token")


# ============= Helper Functions =============


def invitation_to_response(invitation: Invitation, db: Session) -> InvitationResponse:
    """Convert an Invitation model to a response schema."""
    org = (
        db.query(Organization)
        .filter(Organization.id == invitation.organization_id)
        .first()
    )
    team = None
    if invitation.team_id:
        team = db.query(Team).filter(Team.id == invitation.team_id).first()

    inviter = db.query(User).filter(User.id == invitation.invited_by).first()

    return InvitationResponse(
        id=str(invitation.id),
        email=invitation.email,
        organization_id=str(invitation.organization_id),
        organization_name=org.name if org else "Unknown",
        team_id=str(invitation.team_id) if invitation.team_id else None,
        team_name=team.name if team else None,
        org_role=invitation.org_role.value,
        team_role=invitation.team_role.value if invitation.team_role else None,
        invited_by_email=inviter.email if inviter else "Unknown",
        token=invitation.token,
        expires_at=invitation.expires_at.isoformat(),
        is_expired=invitation.is_expired,
        is_accepted=invitation.is_accepted,
        created_at=invitation.created_at.isoformat() if invitation.created_at else None,
    )


# ============= Endpoints =============


@router.get("/pending", response_model=InvitationListResponse)
async def list_pending_invitations(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """
    List pending invitations for the current user's email.
    """
    invitations = (
        db.query(Invitation)
        .filter(
            Invitation.email == current_user.email,
            Invitation.accepted_at == None,
        )
        .all()
    )

    # Filter out expired invitations
    valid_invitations = [inv for inv in invitations if not inv.is_expired]

    return InvitationListResponse(
        items=[invitation_to_response(inv, db) for inv in valid_invitations],
        total=len(valid_invitations),
    )


@router.get("/by-org/{organization_id}", response_model=InvitationListResponse)
async def list_organization_invitations(
    org_ctx: Annotated[OrganizationContext, Depends(require_org_admin)],
    db: Session = Depends(get_db_session),
    include_expired: bool = Query(False, description="Include expired invitations"),
    include_accepted: bool = Query(False, description="Include accepted invitations"),
):
    """
    List invitations for an organization.
    Requires admin role in the organization.
    """
    query = db.query(Invitation).filter(
        Invitation.organization_id == org_ctx.org_id,
    )

    if not include_accepted:
        query = query.filter(Invitation.accepted_at == None)

    invitations = query.all()

    # Filter expired unless requested
    if not include_expired:
        invitations = [inv for inv in invitations if not inv.is_expired]

    return InvitationListResponse(
        items=[invitation_to_response(inv, db) for inv in invitations],
        total=len(invitations),
    )


@router.post("", response_model=InvitationResponse, status_code=201)
async def create_invitation(
    request: CreateInvitationRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """
    Create an invitation to join an organization (and optionally a team).
    Requires admin role in the organization.
    """
    try:
        organization_id = uuid.UUID(request.organization_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid organization ID format",
        )

    # Check organization exists and user has permission
    organization = (
        db.query(Organization).filter(Organization.id == organization_id).first()
    )
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check user's role in the organization
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == current_user.id,
        )
        .first()
    )
    if not membership or membership.role not in (
        OrganizationRole.OWNER,
        OrganizationRole.ADMIN,
    ):
        if not current_user.is_system_admin:
            raise PermissionDenied("Organization admin access required to invite users")

    # Only owners can invite as owner or admin
    if request.org_role in (OrganizationRole.OWNER, OrganizationRole.ADMIN):
        if membership and membership.role != OrganizationRole.OWNER:
            if not current_user.is_system_admin:
                raise PermissionDenied("Only owners can invite admins or owners")

    # Validate team if provided
    team_id = None
    if request.team_id:
        try:
            team_id = uuid.UUID(request.team_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid team ID format",
            )

        team = db.query(Team).filter(Team.id == team_id).first()
        if not team or team.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found in this organization",
            )

    # Check if user is already a member
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        existing_membership = (
            db.query(OrganizationMember)
            .filter(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == existing_user.id,
            )
            .first()
        )
        if existing_membership:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this organization",
            )

    # Check for existing valid invitation
    existing_invitation = (
        db.query(Invitation)
        .filter(
            Invitation.email == request.email,
            Invitation.organization_id == organization_id,
            Invitation.accepted_at == None,
        )
        .first()
    )
    if existing_invitation and not existing_invitation.is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pending invitation already exists for this email",
        )

    # Delete any expired invitations for this email/org
    if existing_invitation:
        db.delete(existing_invitation)

    # Create the invitation
    invitation = Invitation(
        email=request.email,
        organization_id=organization_id,
        team_id=team_id,
        org_role=request.org_role,
        team_role=request.team_role,
        invited_by=current_user.id,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    return invitation_to_response(invitation, db)


@router.post("/accept", status_code=200)
async def accept_invitation(
    request: AcceptInvitationRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """
    Accept an invitation using its token.
    The invitation must be for the current user's email.
    """
    invitation = db.query(Invitation).filter(Invitation.token == request.token).first()
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    if invitation.is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation has expired",
        )

    if invitation.is_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation has already been accepted",
        )

    if invitation.email.lower() != current_user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This invitation is for a different email address",
        )

    # Check if already a member (might have been added directly)
    existing_membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == invitation.organization_id,
            OrganizationMember.user_id == current_user.id,
        )
        .first()
    )
    if existing_membership:
        # Just mark invitation as accepted
        invitation.accepted_at = datetime.now(timezone.utc)
        db.commit()
        return {"message": "You are already a member of this organization"}

    # Create organization membership
    org_membership = OrganizationMember(
        user_id=current_user.id,
        organization_id=invitation.organization_id,
        role=invitation.org_role,
        invited_by=invitation.invited_by,
    )
    db.add(org_membership)

    # Create team membership if specified
    if invitation.team_id and invitation.team_role:
        team_membership = TeamMember(
            user_id=current_user.id,
            team_id=invitation.team_id,
            role=invitation.team_role,
        )
        db.add(team_membership)

    # Set as default organization if user doesn't have one
    if current_user.default_organization_id is None:
        current_user.default_organization_id = invitation.organization_id

    # Mark invitation as accepted
    invitation.accepted_at = datetime.now(timezone.utc)

    db.commit()

    org = (
        db.query(Organization)
        .filter(Organization.id == invitation.organization_id)
        .first()
    )

    return {
        "message": f"Successfully joined {org.name if org else 'organization'}",
        "organization_id": str(invitation.organization_id),
        "team_id": str(invitation.team_id) if invitation.team_id else None,
    }


@router.delete("/{invitation_id}", status_code=204)
async def revoke_invitation(
    invitation_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """
    Revoke/delete an invitation.
    Requires admin role in the organization.
    """
    invitation = db.query(Invitation).filter(Invitation.id == invitation_id).first()
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    # Check permissions
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == invitation.organization_id,
            OrganizationMember.user_id == current_user.id,
        )
        .first()
    )
    if not membership or membership.role not in (
        OrganizationRole.OWNER,
        OrganizationRole.ADMIN,
    ):
        if not current_user.is_system_admin:
            raise PermissionDenied("Organization admin access required")

    db.delete(invitation)
    db.commit()
    return None


@router.get("/validate/{token}")
async def validate_invitation_token(
    token: str,
    db: Session = Depends(get_db_session),
):
    """
    Validate an invitation token without requiring authentication.
    Used to show invitation details on the accept page.
    """
    invitation = db.query(Invitation).filter(Invitation.token == token).first()
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    org = (
        db.query(Organization)
        .filter(Organization.id == invitation.organization_id)
        .first()
    )
    team = None
    if invitation.team_id:
        team = db.query(Team).filter(Team.id == invitation.team_id).first()

    return {
        "valid": invitation.is_valid,
        "email": invitation.email,
        "organization_name": org.name if org else "Unknown",
        "team_name": team.name if team else None,
        "org_role": invitation.org_role.value,
        "team_role": invitation.team_role.value if invitation.team_role else None,
        "expires_at": invitation.expires_at.isoformat(),
        "is_expired": invitation.is_expired,
        "is_accepted": invitation.is_accepted,
    }
