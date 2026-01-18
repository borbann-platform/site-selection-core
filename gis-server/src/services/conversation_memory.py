"""
Conversation memory service for maintaining chat history across sessions.
Uses in-memory cache with optional PostgreSQL persistence.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    Manages conversation history with in-memory cache and database persistence.

    Features:
    - Session-based conversation tracking
    - In-memory caching for fast access
    - Database persistence for durability (optional)
    - Automatic cleanup of old sessions
    """

    def __init__(self):
        self._sessions: dict[str, list[dict[str, Any]]] = {}
        self._session_metadata: dict[str, dict[str, Any]] = {}

    def create_session(self) -> str:
        """
        Create a new conversation session.

        Returns:
            session_id: Unique identifier for the session
        """
        session_id = uuid.uuid4().hex[:12]
        self._sessions[session_id] = []
        self._session_metadata[session_id] = {
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
        }
        logger.info(f"Created new conversation session: {session_id}")
        return session_id

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Add a message to a session.

        Args:
            session_id: Session identifier
            role: Message role ("user" or "assistant")
            content: Message content
            metadata: Optional metadata (tool calls, etc.)
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = []
            self._session_metadata[session_id] = {
                "created_at": datetime.utcnow().isoformat(),
            }

        message = {
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._sessions[session_id].append(message)

        # Update last activity
        if session_id in self._session_metadata:
            self._session_metadata[session_id]["last_activity"] = (
                datetime.utcnow().isoformat()
            )

        # Persist to database (async, best-effort)
        self._persist_message_async(session_id, message)

    def get_history(
        self,
        session_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Get conversation history for a session.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return

        Returns:
            List of message dicts with role, content, timestamp
        """
        if session_id not in self._sessions:
            # Try loading from database
            history = self._load_from_db(session_id, limit)
            if history:
                self._sessions[session_id] = history
            return history

        # Return last N messages
        return self._sessions[session_id][-limit:]

    def get_messages_for_agent(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list[dict[str, str]]:
        """
        Get messages formatted for the agent (role + content only).

        Args:
            session_id: Session identifier
            limit: Maximum number of messages

        Returns:
            List of {"role": str, "content": str} dicts
        """
        history = self.get_history(session_id, limit)
        return [{"role": m["role"], "content": m["content"]} for m in history]

    def clear_session(self, session_id: str) -> None:
        """Clear all messages from a session."""
        if session_id in self._sessions:
            self._sessions[session_id] = []
            logger.info(f"Cleared session: {session_id}")

        # Also clear from database
        self._clear_from_db(session_id)

    def delete_session(self, session_id: str) -> None:
        """Completely delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
        if session_id in self._session_metadata:
            del self._session_metadata[session_id]

        self._delete_from_db(session_id)
        logger.info(f"Deleted session: {session_id}")

    def get_session_info(self, session_id: str) -> dict[str, Any] | None:
        """Get metadata about a session."""
        if session_id in self._session_metadata:
            return {
                **self._session_metadata[session_id],
                "message_count": len(self._sessions.get(session_id, [])),
            }
        return None

    def _persist_message_async(self, session_id: str, message: dict) -> None:
        """
        Persist message to database (best-effort, non-blocking).
        Failures are logged but don't affect operation.
        """
        try:
            from src.config.database import SessionLocal

            with SessionLocal() as db:
                from sqlalchemy import text

                db.execute(
                    text("""
                        INSERT INTO conversation_memory 
                        (session_id, role, content, metadata, created_at)
                        VALUES (:session_id, :role, :content, :metadata::jsonb, NOW())
                    """),
                    {
                        "session_id": session_id,
                        "role": message["role"],
                        "content": message["content"],
                        "metadata": json.dumps(message.get("metadata", {})),
                    },
                )
                db.commit()
        except Exception as e:
            # Log but don't fail - in-memory cache is primary
            logger.debug(f"Failed to persist message to DB: {e}")

    def _load_from_db(self, session_id: str, limit: int) -> list[dict[str, Any]]:
        """Load conversation history from database."""
        try:
            from src.config.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as db:
                results = db.execute(
                    text("""
                        SELECT role, content, metadata, created_at
                        FROM conversation_memory
                        WHERE session_id = :session_id
                        ORDER BY created_at ASC
                        LIMIT :limit
                    """),
                    {"session_id": session_id, "limit": limit},
                ).fetchall()

                return [
                    {
                        "role": r.role,
                        "content": r.content,
                        "metadata": json.loads(r.metadata) if r.metadata else {},
                        "timestamp": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in results
                ]
        except Exception as e:
            logger.debug(f"Failed to load from DB: {e}")
            return []

    def _clear_from_db(self, session_id: str) -> None:
        """Clear session messages from database."""
        try:
            from src.config.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as db:
                db.execute(
                    text(
                        "DELETE FROM conversation_memory WHERE session_id = :session_id"
                    ),
                    {"session_id": session_id},
                )
                db.commit()
        except Exception as e:
            logger.debug(f"Failed to clear from DB: {e}")

    def _delete_from_db(self, session_id: str) -> None:
        """Delete session from database."""
        self._clear_from_db(session_id)

    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """
        Remove sessions older than max_age_hours.

        Args:
            max_age_hours: Maximum age of sessions to keep

        Returns:
            Number of sessions removed
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        sessions_to_remove = []

        for session_id, metadata in self._session_metadata.items():
            last_activity = metadata.get("last_activity")
            if last_activity:
                try:
                    activity_time = datetime.fromisoformat(last_activity)
                    if activity_time < cutoff:
                        sessions_to_remove.append(session_id)
                except ValueError:
                    pass

        for session_id in sessions_to_remove:
            self.delete_session(session_id)

        if sessions_to_remove:
            logger.info(f"Cleaned up {len(sessions_to_remove)} old sessions")

        return len(sessions_to_remove)


# Singleton instance
conversation_memory = ConversationMemory()
