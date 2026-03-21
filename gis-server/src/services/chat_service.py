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

from src.models.chat import ChatMessage, ChatSession
from src.services.model_provider import get_model_provider, resolve_runtime_config

logger = logging.getLogger(__name__)


def _llm_response_to_text(response: Any) -> str:
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content)


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

    def get_messages_for_agent_context(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        recent_limit: int = 10,
    ) -> list[dict[str, str]]:
        """
        Build hybrid context for the agent: rolling summary + recent messages.
        """
        session = self.get_session(session_id, user_id, include_messages=False)
        if not session:
            return []

        payload: list[dict[str, str]] = []
        metadata = session.extra_data or {}
        rolling_summary_raw = metadata.get("rolling_summary")
        rolling_summary = (
            rolling_summary_raw.strip() if isinstance(rolling_summary_raw, str) else ""
        )
        if rolling_summary:
            payload.append(
                {
                    "role": "system",
                    "content": (
                        "[SESSION SUMMARY]\n"
                        f"{rolling_summary}\n"
                        "Use this as high-level memory; prefer recent messages for immediate intent."
                    ),
                }
            )

        payload.extend(self.get_messages_for_agent(session_id, limit=recent_limit))
        return payload

    def _heuristic_rolling_summary(
        self,
        existing_summary: str,
        messages: list[ChatMessage],
    ) -> str:
        user_lines = [
            m.content.strip() for m in messages if m.role == "user" and m.content
        ]
        recent_user_lines = user_lines[-6:]
        if not recent_user_lines and existing_summary:
            return existing_summary
        summary_bits = []
        if existing_summary:
            summary_bits.append(existing_summary.strip())
        if recent_user_lines:
            summary_bits.append(
                "Recent user constraints: "
                + " | ".join(line[:180] for line in recent_user_lines)
            )
        return "\n".join(summary_bits)[:2000]

    async def refresh_rolling_summary(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        force: bool = False,
        every_n_user_turns: int = 4,
    ) -> bool:
        """
        Refresh rolling summary every N user turns (or when forced).
        Returns True when summary is updated.
        """
        session = self.get_session(session_id, user_id, include_messages=True)
        if not session:
            return False

        metadata = dict(session.extra_data or {})
        messages = session.messages or []
        user_turns = sum(1 for m in messages if m.role == "user")
        summarized_user_turns = int(metadata.get("summarized_user_turns") or 0)

        should_update = (
            force or (user_turns - summarized_user_turns) >= every_n_user_turns
        )
        if not should_update:
            return False

        existing_summary = str(metadata.get("rolling_summary") or "").strip()
        new_summary: str | None = None

        try:
            resolved = resolve_runtime_config()
            if resolved.is_configured:
                provider = get_model_provider(resolved.provider)
                llm = provider.create_chat_model(
                    resolved,
                    temperature=0.1,
                    max_tokens=220,
                )

                transcript = "\n".join(
                    f"{m.role}: {m.content[:300]}" for m in messages[-20:] if m.content
                )
                prompt = (
                    "Summarize this property-search conversation memory in <= 8 bullet points. "
                    "Keep stable preferences and constraints (budget, area, type, exclusions, goals). "
                    "Avoid temporary filler. Keep user language.\n\n"
                    f"Previous summary:\n{existing_summary or '(none)'}\n\n"
                    f"Recent transcript:\n{transcript}\n\n"
                    "Return plain text bullets only."
                )
                response = await llm.ainvoke(prompt)
                content = _llm_response_to_text(response).strip()
                if content:
                    new_summary = content[:2000]
        except Exception as exc:
            logger.warning(
                "LLM rolling summary failed, falling back to heuristic: %s", exc
            )

        if not new_summary:
            new_summary = self._heuristic_rolling_summary(existing_summary, messages)

        metadata["rolling_summary"] = new_summary
        metadata["summarized_user_turns"] = user_turns
        metadata["summary_updated_at"] = datetime.now(timezone.utc).isoformat()
        session.extra_data = metadata
        self.db.commit()
        return True

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
            resolved = resolve_runtime_config()
            if not resolved.is_configured:
                return None

            provider = get_model_provider(resolved.provider)
            llm = provider.create_chat_model(
                resolved,
                temperature=0.2,
                max_tokens=80,
            )

            prompt = f"""Generate a very short title (3-6 words, max 50 characters) for this chat conversation.
The title should summarize the user's main intent or topic.
Only return the title text, no quotes, no explanation.

User's first message: {first_user_msg.content[:500]}

Title:"""

            response = await llm.ainvoke(prompt)
            title_text = _llm_response_to_text(response).strip()
            title = title_text[:50] if title_text else None

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
