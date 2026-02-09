"""
Team management API routes.
Provides endpoints for managing teams within organizations.
"""

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
    TeamContext,
    get_org_context,
    get_team_context,
    require_org_admin,
    require_org_member,
    require_team_admin,
    require_team_member,
)
from src.models.membership import (
    OrganizationMember,
    OrganizationRole,
    TeamMember,
    TeamRole,
)
from src.models.organization import Organization
from src.models.team import Team
from src.models.user import User

router = APIRouter(prefix="/teams", tags=["Teams"])


# ============= Request/Response Schemas =============


class CreateTeamRequest(BaseModel):
    """Request body for creating a new team."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class UpdateTeamRequest(BaseModel):
    """Request body for updating a team."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    settings: dict | None = None


class TeamResponse(BaseModel):
    """Response schema for a team."""

    id: str
    organization_id: str
    name: str
    description: str | None
    is_active: bool
    created_at: str | None
    updated_at: str | None
    member_count: int = 0


class TeamMemberResponse(BaseModel):
    """Response schema for a team member."""

    id: str
    user_id: str
    email: str
    name: str | None
    role: str
    joined_at: str | None


class TeamListResponse(BaseModel):
    """Response schema for listing teams."""

    items: list[TeamResponse]
    total: int


class AddTeamMemberRequest(BaseModel):
    """Request body for adding a member to a team."""

    user_id: str = Field(..., description="UUID of the user to add")
    role: TeamRole = TeamRole.MEMBER


class UpdateTeamMemberRoleRequest(BaseModel):
    """Request body for updating a team member's role."""

    role: TeamRole


# ============= Helper Functions =============


def team_to_response(team: Team, db: Session) -> TeamResponse:
    """Convert a Team model to a response schema."""
    member_count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()

    return TeamResponse(
        id=str(team.id),
        organization_id=str(team.organization_id),
        name=team.name,
        description=team.description,
        is_active=team.is_active,
        created_at=team.created_at.isoformat() if team.created_at else None,
        updated_at=team.updated_at.isoformat() if team.updated_at else None,
        member_count=member_count,
    )


# ============= Team CRUD Endpoints =============


@router.get("/by-org/{organization_id}", response_model=TeamListResponse)
async def list_organization_teams(
    org_ctx: Annotated[OrganizationContext, Depends(require_org_member)],
    db: Session = Depends(get_db_session),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    List all teams in an organization.
    Requires membership in the organization.
    """
    query = db.query(Team).filter(
        Team.organization_id == org_ctx.org_id,
        Team.is_active == True,
    )

    total = query.count()
    teams = query.offset(offset).limit(limit).all()

    return TeamListResponse(
        items=[team_to_response(team, db) for team in teams],
        total=total,
    )


@router.post("/by-org/{organization_id}", response_model=TeamResponse, status_code=201)
async def create_team(
    request: CreateTeamRequest,
    org_ctx: Annotated[OrganizationContext, Depends(require_org_admin)],
    db: Session = Depends(get_db_session),
):
    """
    Create a new team in an organization.
    Requires admin role in the organization.
    The creating user becomes the team admin.
    """
    team = Team(
        organization_id=org_ctx.org_id,
        name=request.name,
        description=request.description,
    )
    db.add(team)
    db.flush()  # Get the ID

    # Add creator as team admin
    membership = TeamMember(
        user_id=org_ctx.user.id,
        team_id=team.id,
        role=TeamRole.ADMIN,
    )
    db.add(membership)

    db.commit()
    db.refresh(team)

    return team_to_response(team, db)


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_ctx: Annotated[TeamContext, Depends(require_team_member)],
    db: Session = Depends(get_db_session),
):
    """
    Get team details.
    Requires membership in the team or admin role in the organization.
    """
    return team_to_response(team_ctx.team, db)


@router.patch("/{team_id}", response_model=TeamResponse)
async def update_team(
    request: UpdateTeamRequest,
    team_ctx: Annotated[TeamContext, Depends(require_team_admin)],
    db: Session = Depends(get_db_session),
):
    """
    Update team details.
    Requires admin role in the team or organization.
    """
    team = team_ctx.team

    if request.name is not None:
        team.name = request.name
    if request.description is not None:
        team.description = request.description
    if request.settings is not None:
        team.settings = request.settings

    db.commit()
    db.refresh(team)

    return team_to_response(team, db)


@router.delete("/{team_id}", status_code=204)
async def delete_team(
    team_ctx: Annotated[TeamContext, Depends(require_team_admin)],
    db: Session = Depends(get_db_session),
):
    """
    Delete a team (soft delete).
    Requires admin role in the team or organization.
    """
    team = team_ctx.team
    team.is_active = False
    db.commit()
    return None


# ============= Team Member Management =============


@router.get("/{team_id}/members", response_model=list[TeamMemberResponse])
async def list_team_members(
    team_ctx: Annotated[TeamContext, Depends(require_team_member)],
    db: Session = Depends(get_db_session),
):
    """
    List all members of a team.
    Requires membership in the team or admin role in the organization.
    """
    members = db.query(TeamMember).filter(TeamMember.team_id == team_ctx.team_id).all()

    result = []
    for member in members:
        user = db.query(User).filter(User.id == member.user_id).first()
        if user:
            result.append(
                TeamMemberResponse(
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


@router.post("/{team_id}/members", response_model=TeamMemberResponse, status_code=201)
async def add_team_member(
    request: AddTeamMemberRequest,
    team_ctx: Annotated[TeamContext, Depends(require_team_admin)],
    db: Session = Depends(get_db_session),
):
    """
    Add a member to a team.
    Requires admin role in the team or organization.
    The user must be a member of the organization.
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

    # Check if user is a member of the organization
    org_membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == team_ctx.organization.id,
            OrganizationMember.user_id == user_id,
        )
        .first()
    )
    if not org_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be a member of the organization to join a team",
        )

    # Check if already a team member
    existing = (
        db.query(TeamMember)
        .filter(
            TeamMember.team_id == team_ctx.team_id,
            TeamMember.user_id == user_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this team",
        )

    # Create team membership
    membership = TeamMember(
        user_id=user_id,
        team_id=team_ctx.team_id,
        role=request.role,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)

    return TeamMemberResponse(
        id=str(membership.id),
        user_id=str(user.id),
        email=user.email,
        name=user.full_name,
        role=membership.role.value,
        joined_at=membership.joined_at.isoformat() if membership.joined_at else None,
    )


@router.patch("/{team_id}/members/{member_id}")
async def update_team_member_role(
    member_id: uuid.UUID,
    request: UpdateTeamMemberRoleRequest,
    team_ctx: Annotated[TeamContext, Depends(require_team_admin)],
    db: Session = Depends(get_db_session),
):
    """
    Update a team member's role.
    Requires admin role in the team or organization.
    """
    membership = (
        db.query(TeamMember)
        .filter(
            TeamMember.id == member_id,
            TeamMember.team_id == team_ctx.team_id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    # Prevent removing the last admin
    if membership.role == TeamRole.ADMIN and request.role != TeamRole.ADMIN:
        admin_count = (
            db.query(TeamMember)
            .filter(
                TeamMember.team_id == team_ctx.team_id,
                TeamMember.role == TeamRole.ADMIN,
            )
            .count()
        )
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last team admin",
            )

    membership.role = request.role
    db.commit()

    user = db.query(User).filter(User.id == membership.user_id).first()
    return TeamMemberResponse(
        id=str(membership.id),
        user_id=str(membership.user_id),
        email=user.email if user else "",
        name=user.full_name if user else None,
        role=membership.role.value,
        joined_at=membership.joined_at.isoformat() if membership.joined_at else None,
    )


@router.delete("/{team_id}/members/{member_id}", status_code=204)
async def remove_team_member(
    member_id: uuid.UUID,
    team_ctx: Annotated[TeamContext, Depends(require_team_admin)],
    db: Session = Depends(get_db_session),
):
    """
    Remove a member from the team.
    Requires admin role in the team or organization.
    """
    membership = (
        db.query(TeamMember)
        .filter(
            TeamMember.id == member_id,
            TeamMember.team_id == team_ctx.team_id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    # Prevent removing the last admin
    if membership.role == TeamRole.ADMIN:
        admin_count = (
            db.query(TeamMember)
            .filter(
                TeamMember.team_id == team_ctx.team_id,
                TeamMember.role == TeamRole.ADMIN,
            )
            .count()
        )
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last team admin",
            )

    db.delete(membership)
    db.commit()
    return None


@router.post("/{team_id}/leave", status_code=204)
async def leave_team(
    team_ctx: Annotated[TeamContext, Depends(require_team_member)],
    db: Session = Depends(get_db_session),
):
    """
    Leave a team.
    Team admins cannot leave if they are the last admin.
    """
    if not team_ctx.team_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not a member of this team",
        )

    # Prevent last admin from leaving
    if team_ctx.is_team_admin:
        admin_count = (
            db.query(TeamMember)
            .filter(
                TeamMember.team_id == team_ctx.team_id,
                TeamMember.role == TeamRole.ADMIN,
            )
            .count()
        )
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot leave as the last admin. Promote another member first.",
            )

    db.delete(team_ctx.team_membership)
    db.commit()
    return None
