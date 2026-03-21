"""
Chat sessions API routes.
Provides endpoints for managing chat sessions and their messages.
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.config.database import SessionLocal, get_db_session
from src.dependencies.auth import get_current_user
from src.models.user import User
from src.services.chat_service import ChatService

router = APIRouter(prefix="/chat/sessions", tags=["Chat Sessions"])
logger = logging.getLogger(__name__)


# ============= Request/Response Schemas =============


class CreateSessionRequest(BaseModel):
    """Request body for creating a new session."""

    title: str | None = None


class UpdateSessionRequest(BaseModel):
    """Request body for updating a session."""

    title: str | None = None
    is_archived: bool | None = None


class SessionResponse(BaseModel):
    """Response schema for a chat session."""

    id: str
    title: str | None
    created_at: str | None
    updated_at: str | None
    last_message_at: str | None
    message_count: int
    is_archived: bool
    preview: str | None = None


class MessageResponse(BaseModel):
    """Response schema for a chat message."""

    id: str
    role: str
    content: str
    attachments: list[dict[str, Any]] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    created_at: str | None


class SessionWithMessagesResponse(BaseModel):
    """Response schema for a session with its messages."""

    id: str
    title: str | None
    created_at: str | None
    updated_at: str | None
    last_message_at: str | None
    message_count: int
    is_archived: bool
    messages: list[MessageResponse]


class SessionListResponse(BaseModel):
    """Response schema for listing sessions."""

    items: list[SessionResponse]
    total: int
    has_more: bool


class GenerateTitleResponse(BaseModel):
    """Response schema for title generation."""

    title: str | None
    success: bool


# ============= Endpoints =============


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, max_length=200),
    include_archived: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    List chat sessions for the current user.

    - Sorted by last message time (most recent first)
    - Supports pagination and search
    - Can include/exclude archived sessions
    """
    service = ChatService(db)
    sessions, total = service.list_sessions(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        search=search,
        include_archived=include_archived,
    )

    items = []
    for session in sessions:
        preview = service.get_session_preview(session)
        items.append(
            SessionResponse(
                id=str(session.id),
                title=session.title,
                created_at=session.created_at.isoformat()
                if session.created_at
                else None,
                updated_at=session.updated_at.isoformat()
                if session.updated_at
                else None,
                last_message_at=(
                    session.last_message_at.isoformat()
                    if session.last_message_at
                    else None
                ),
                message_count=session.message_count,
                is_archived=session.is_archived,
                preview=preview,
            )
        )

    return SessionListResponse(
        items=items,
        total=total,
        has_more=(offset + limit) < total,
    )


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    request: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Create a new chat session."""
    service = ChatService(db)
    session = service.create_session(
        user_id=current_user.id,
        title=request.title,
    )

    return SessionResponse(
        id=str(session.id),
        title=session.title,
        created_at=session.created_at.isoformat() if session.created_at else None,
        updated_at=session.updated_at.isoformat() if session.updated_at else None,
        last_message_at=None,
        message_count=0,
        is_archived=False,
        preview=None,
    )


@router.get("/{session_id}", response_model=SessionWithMessagesResponse)
async def get_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get a chat session with all its messages."""
    service = ChatService(db)
    session = service.get_session(
        session_id=session_id,
        user_id=current_user.id,
        include_messages=True,
    )

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = [
        MessageResponse(
            id=str(msg.id),
            role=msg.role,
            content=msg.content,
            attachments=msg.attachments,
            tool_calls=msg.tool_calls,
            created_at=msg.created_at.isoformat() if msg.created_at else None,
        )
        for msg in session.messages
    ]

    return SessionWithMessagesResponse(
        id=str(session.id),
        title=session.title,
        created_at=session.created_at.isoformat() if session.created_at else None,
        updated_at=session.updated_at.isoformat() if session.updated_at else None,
        last_message_at=(
            session.last_message_at.isoformat() if session.last_message_at else None
        ),
        message_count=session.message_count,
        is_archived=session.is_archived,
        messages=messages,
    )


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: uuid.UUID,
    request: UpdateSessionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Update a chat session (rename or archive)."""
    service = ChatService(db)
    session = service.update_session(
        session_id=session_id,
        user_id=current_user.id,
        title=request.title,
        is_archived=request.is_archived,
    )

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if request.is_archived is True:

        async def refresh_summary_background() -> None:
            try:
                with SessionLocal() as background_db:
                    background_service = ChatService(background_db)
                    await background_service.refresh_rolling_summary(
                        session_id=session_id,
                        user_id=current_user.id,
                        force=True,
                    )
            except Exception as exc:
                logger.warning(
                    "Failed to finalize rolling summary for archived session %s: %s",
                    session_id,
                    exc,
                )

        background_tasks.add_task(refresh_summary_background)

    return SessionResponse(
        id=str(session.id),
        title=session.title,
        created_at=session.created_at.isoformat() if session.created_at else None,
        updated_at=session.updated_at.isoformat() if session.updated_at else None,
        last_message_at=(
            session.last_message_at.isoformat() if session.last_message_at else None
        ),
        message_count=session.message_count,
        is_archived=session.is_archived,
        preview=None,
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Delete a chat session and all its messages."""
    service = ChatService(db)
    deleted = service.delete_session(
        session_id=session_id,
        user_id=current_user.id,
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return None


@router.post("/{session_id}/generate-title", response_model=GenerateTitleResponse)
async def generate_session_title(
    session_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    Generate an AI-powered title for a session based on its messages.
    This is typically called after the first exchange.
    """
    service = ChatService(db)
    session = service.get_session(
        session_id=session_id,
        user_id=current_user.id,
        include_messages=False,
    )

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Generate title (this is async but we want immediate response)
    try:
        title = await service.generate_title(session_id, current_user.id)
        return GenerateTitleResponse(title=title, success=title is not None)
    except Exception as e:
        logger.error(f"Failed to generate title: {e}")
        return GenerateTitleResponse(title=None, success=False)
