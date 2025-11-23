from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class SavedSiteCreate(BaseModel):
    name: str
    location: dict  # GeoJSON Point
    score: float
    notes: str | None = None
    analysis_data: dict


class SavedSiteResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    # location will be handled separately or we need a custom serializer for WKB
    # For simplicity, we'll skip returning location in this response or handle it in the route
    score: float
    notes: str | None
    analysis_data: dict
    created_at: datetime

    class Config:
        from_attributes = True
