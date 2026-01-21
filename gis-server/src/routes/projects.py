from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.shape import from_shape
from shapely.geometry import shape
from sqlalchemy.orm import Session

from src.config.database import get_db_session
from src.dependencies.auth import get_current_active_user
from src.models.db import Project, SavedSite
from src.models.project import (
    ProjectCreate,
    ProjectResponse,
    SavedSiteCreate,
    SavedSiteResponse,
)
from src.models.user import User

router = APIRouter()


@router.post(
    "/projects", response_model=ProjectResponse, summary="Create a new project"
)
def create_project(
    payload: ProjectCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    project = Project(name=payload.name, description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get(
    "/projects", response_model=list[ProjectResponse], summary="List all projects"
)
def list_projects(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    return db.query(Project).all()


@router.post(
    "/projects/{project_id}/sites",
    response_model=SavedSiteResponse,
    summary="Save a site to a project",
)
def save_site(
    project_id: UUID,
    payload: SavedSiteCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Convert GeoJSON to WKT/WKB
    try:
        geom = from_shape(shape(payload.location), srid=4326)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid geometry: {e}")

    site = SavedSite(
        project_id=project_id,
        name=payload.name,
        location=geom,
        score=payload.score,
        notes=payload.notes,
        analysis_data=payload.analysis_data,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.get(
    "/projects/{project_id}/dashboard",
    response_model=list[SavedSiteResponse],
    summary="Get all saved sites for a project",
)
def get_project_sites(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    sites = db.query(SavedSite).filter(SavedSite.project_id == project_id).all()
    return sites
