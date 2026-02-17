"""
Encrypted per-user runtime model credentials for BYOK provider access.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.config.database import Base

if TYPE_CHECKING:
    from src.models.user import User


class AgentRuntimeCredential(Base):
    """Stores one runtime provider configuration per user."""

    __tablename__ = "agent_runtime_credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_last4: Mapped[str | None] = mapped_column(String(8), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(128), nullable=True)
    use_vertex_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vertex_project: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vertex_location: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reasoning_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="agent_runtime_credential")
