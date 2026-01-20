"""
Create chat_sessions and chat_messages tables for persistent chat history.
Run this script to set up the chat persistence layer.
"""

import logging
from sqlalchemy import text
from src.config.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_users_table():
    """Create users table if it doesn't exist."""
    sql = """
    CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        first_name VARCHAR(100) NOT NULL,
        last_name VARCHAR(100) NOT NULL,
        is_active BOOLEAN DEFAULT TRUE NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    """
    with engine.connect() as conn:
        for stmt in [s.strip() for s in sql.strip().split(";") if s.strip()]:
            try:
                conn.execute(text(stmt))
                logger.info(f"Executed: {stmt[:50]}...")
            except Exception as e:
                logger.warning(f"Statement failed (may already exist): {e}")
        conn.commit()
    logger.info("Users table ready!")


def create_chat_tables():
    """Create chat_sessions and chat_messages tables."""

    # First ensure users table exists
    create_users_table()

    # Create tables
    tables_sql = """
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title VARCHAR(255),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        last_message_at TIMESTAMP WITH TIME ZONE,
        message_count INTEGER DEFAULT 0,
        is_archived BOOLEAN DEFAULT FALSE,
        session_metadata JSONB DEFAULT '{}'::jsonb
    );

    CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id 
        ON chat_sessions(user_id);
    CREATE INDEX IF NOT EXISTS idx_chat_sessions_last_message 
        ON chat_sessions(user_id, last_message_at DESC NULLS LAST);
    CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated 
        ON chat_sessions(user_id, updated_at DESC);

    CREATE TABLE IF NOT EXISTS chat_messages (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
        role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
        content TEXT NOT NULL,
        attachments JSONB,
        tool_calls JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        message_metadata JSONB DEFAULT '{}'::jsonb
    );

    CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id 
        ON chat_messages(session_id);
    CREATE INDEX IF NOT EXISTS idx_chat_messages_created 
        ON chat_messages(session_id, created_at);
    """

    with engine.connect() as conn:
        for stmt in [s.strip() for s in tables_sql.strip().split(";") if s.strip()]:
            try:
                conn.execute(text(stmt))
                logger.info(f"Executed: {stmt[:50]}...")
            except Exception as e:
                logger.warning(f"Statement failed (may already exist): {e}")
        conn.commit()

    # Create functions and triggers (these need to be executed as whole blocks)
    function_sql = """
    CREATE OR REPLACE FUNCTION update_session_on_message()
    RETURNS TRIGGER AS $func$
    BEGIN
        UPDATE chat_sessions
        SET 
            message_count = message_count + 1,
            last_message_at = NEW.created_at,
            updated_at = NOW()
        WHERE id = NEW.session_id;
        RETURN NEW;
    END;
    $func$ LANGUAGE plpgsql
    """

    trigger1_sql = """
    DROP TRIGGER IF EXISTS trg_update_session_on_message ON chat_messages
    """

    trigger1_create_sql = """
    CREATE TRIGGER trg_update_session_on_message
        AFTER INSERT ON chat_messages
        FOR EACH ROW
        EXECUTE FUNCTION update_session_on_message()
    """

    function2_sql = """
    CREATE OR REPLACE FUNCTION update_chat_session_timestamp()
    RETURNS TRIGGER AS $func$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $func$ LANGUAGE plpgsql
    """

    trigger2_sql = """
    DROP TRIGGER IF EXISTS trg_chat_session_updated ON chat_sessions
    """

    trigger2_create_sql = """
    CREATE TRIGGER trg_chat_session_updated
        BEFORE UPDATE ON chat_sessions
        FOR EACH ROW
        EXECUTE FUNCTION update_chat_session_timestamp()
    """

    with engine.connect() as conn:
        for sql in [
            function_sql,
            trigger1_sql,
            trigger1_create_sql,
            function2_sql,
            trigger2_sql,
            trigger2_create_sql,
        ]:
            try:
                conn.execute(text(sql))
                logger.info(f"Executed: {sql.strip()[:50]}...")
            except Exception as e:
                logger.warning(f"Failed: {e}")
        conn.commit()

    logger.info("Chat tables created successfully!")


def drop_chat_tables():
    """Drop chat tables (for development/reset)."""
    statements = [
        "DROP TRIGGER IF EXISTS trg_update_session_on_message ON chat_messages",
        "DROP TRIGGER IF EXISTS trg_chat_session_updated ON chat_sessions",
        "DROP FUNCTION IF EXISTS update_session_on_message()",
        "DROP FUNCTION IF EXISTS update_chat_session_timestamp()",
        "DROP TABLE IF EXISTS chat_messages",
        "DROP TABLE IF EXISTS chat_sessions",
    ]

    with engine.connect() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
                logger.info(f"Executed: {stmt[:50]}...")
            except Exception as e:
                logger.warning(f"Drop failed: {e}")
        conn.commit()

    logger.info("Chat tables dropped!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--drop":
        drop_chat_tables()
    else:
        create_chat_tables()
