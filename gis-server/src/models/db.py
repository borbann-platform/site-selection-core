import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.config.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    sites = relationship("SavedSite", back_populates="project")


class SavedSite(Base):
    __tablename__ = "saved_sites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False)
    location = Column(Geometry("POINT", srid=4326))
    score = Column(Float)
    notes = Column(String)
    analysis_data = Column(JSON)  # Store the full analysis result
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="sites")
