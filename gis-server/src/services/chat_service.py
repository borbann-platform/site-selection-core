"""
Chat service for managing chat sessions and messages.
Provides business logic for session CRUD, message persistence, and title generation.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session, joinedload

from src.config.agent_settings import agent_settings
from src.models.chat import ChatMessage, ChatSession

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing chat sessions and messages."""

    def __init__(self, db: Session):
        self.db = db

    # ============= Session Operations =============

    def create_session(
        self,
        user_id: uuid.UUID,
        title: str | None = None,
    ) -> ChatSession:
        """Create a new chat session for a user."""
        session = ChatSession(
            user_id=user_id,
            title=title,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        logger.info(f"Created chat session {session.id} for user {user_id}")
        return session

    def get_session(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        include_messages: bool = True,
    ) -> ChatSession | None:
        """Get a session by ID, ensuring it belongs to the user."""
        query = self.db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
        if include_messages:
            query = query.options(joinedload(ChatSession.messages))
        return query.first()

    def list_sessions(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        include_archived: bool = False,
    ) -> tuple[list[ChatSession], int]:
        """
        List chat sessions for a user with pagination and search.
        Returns (sessions, total_count).
        """
        query = self.db.query(ChatSession).filter(ChatSession.user_id == user_id)

        if not include_archived:
            query = query.filter(ChatSession.is_archived == False)  # noqa: E712

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    ChatSession.title.ilike(search_pattern),
                    # Search in first message content via subquery
                    ChatSession.id.in_(
                        self.db.query(ChatMessage.session_id)
                        .filter(ChatMessage.content.ilike(search_pattern))
                        .distinct()
                    ),
                )
            )

        total = query.count()

        sessions = (
            query.order_by(ChatSession.last_message_at.desc().nullslast())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return sessions, total

    def update_session(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str | None = None,
        is_archived: bool | None = None,
    ) -> ChatSession | None:
        """Update session properties (title, archived status)."""
        session = self.get_session(session_id, user_id, include_messages=False)
        if not session:
            return None

        if title is not None:
            session.title = title
        if is_archived is not None:
            session.is_archived = is_archived

        self.db.commit()
        self.db.refresh(session)
        logger.info(f"Updated chat session {session_id}")
        return session

    def delete_session(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Delete a session and all its messages."""
        session = self.get_session(session_id, user_id, include_messages=False)
        if not session:
            return False

        self.db.delete(session)
        self.db.commit()
        logger.info(f"Deleted chat session {session_id}")
        return True

    # ============= Message Operations =============

    def add_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
        attachments: list[dict[str, Any]] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        """Add a message to a session."""
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            attachments=attachments,
            tool_calls=tool_calls,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_messages(
        self,
        session_id: uuid.UUID,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[ChatMessage]:
        """Get messages from a session with optional pagination."""
        query = self.db.query(ChatMessage).filter(ChatMessage.session_id == session_id)

        if before:
            query = query.filter(ChatMessage.created_at < before)

        return query.order_by(ChatMessage.created_at).limit(limit).all()

    def get_messages_for_agent(
        self,
        session_id: uuid.UUID,
        limit: int = 20,
    ) -> list[dict[str, str]]:
        """Get messages formatted for the agent (role + content only)."""
        messages = self.get_messages(session_id, limit)
        return [{"role": m.role, "content": m.content} for m in messages]

    # ============= Title Generation =============

    async def generate_title(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> str | None:
        """
        Generate a title for a session based on its first user message.
        Uses LLM to create a concise, descriptive title.
        """
        session = self.get_session(session_id, user_id, include_messages=True)
        if not session or not session.messages:
            return None

        # Find first user message
        first_user_msg = next((m for m in session.messages if m.role == "user"), None)
        if not first_user_msg:
            return None

        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            llm = ChatGoogleGenerativeAI(
                model=agent_settings.AGENT_MODEL,
                google_api_key=agent_settings.GOOGLE_API_KEY,
                temperature=0.3,
                max_output_tokens=50,
            )

            prompt = f"""Generate a very short title (3-6 words, max 50 characters) for this chat conversation.
The title should summarize the user's main intent or topic.
Only return the title text, no quotes, no explanation.

User's first message: {first_user_msg.content[:500]}

Title:"""

            response = await llm.ainvoke(prompt)
            title = response.content.strip()[:50] if response.content else None

            if title:
                session.title = title
                self.db.commit()
                logger.info(f"Generated title for session {session_id}: {title}")
                return title

        except Exception as e:
            logger.warning(f"Failed to generate title: {e}")

        return None

    def get_session_preview(self, session: ChatSession) -> str | None:
        """Get a preview string (first user message truncated)."""
        if not session.messages:
            # Fetch first message if not loaded
            first_msg = (
                self.db.query(ChatMessage)
                .filter(
                    ChatMessage.session_id == session.id,
                    ChatMessage.role == "user",
                )
                .order_by(ChatMessage.created_at)
                .first()
            )
            if first_msg:
                return first_msg.content[:100] + (
                    "..." if len(first_msg.content) > 100 else ""
                )
        else:
            first_user = next((m for m in session.messages if m.role == "user"), None)
            if first_user:
                return first_user.content[:100] + (
                    "..." if len(first_user.content) > 100 else ""
                )
        return None


def get_chat_service(db: Session) -> ChatService:
    """Factory function to create a ChatService instance."""
    return ChatService(db)
