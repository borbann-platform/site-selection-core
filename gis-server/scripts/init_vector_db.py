"""
Initialize vector database tables for RAG agent.
Creates knowledge_chunks table with pgvector embeddings.

Usage:
    python -m scripts.init_vector_db
"""

import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from src.config.agent_settings import agent_settings
from src.config.settings import settings


def init_vector_db():
    """Initialize pgvector tables for RAG knowledge base."""
    engine = create_engine(settings.DATABASE_URL)
    dims = agent_settings.EMBEDDING_DIMENSIONS

    with engine.connect() as conn:
        # Ensure pgvector extension is enabled
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()

        # Create knowledge_chunks table for RAG
        conn.execute(
            text(f"""
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                metadata JSONB DEFAULT '{{}}',
                source_file VARCHAR(255),
                chunk_index INTEGER,
                embedding vector({dims}),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        )
        conn.commit()

        # Create HNSW index for fast similarity search
        # Check if index exists first
        result = conn.execute(
            text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'knowledge_chunks'
            AND indexname = 'knowledge_chunks_embedding_idx';
        """)
        )
        if not result.fetchone():
            conn.execute(
                text("""
                CREATE INDEX knowledge_chunks_embedding_idx
                ON knowledge_chunks
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """)
            )
            conn.commit()
            print("Created HNSW index on knowledge_chunks.embedding")

        # Create conversation_memory table for multi-turn context
        conn.execute(
            text(f"""
            CREATE TABLE IF NOT EXISTS conversation_memory (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(64) NOT NULL,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                metadata JSONB DEFAULT '{{}}',
                embedding vector({dims}),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        )
        conn.commit()

        # Index for session lookups
        result = conn.execute(
            text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'conversation_memory'
            AND indexname = 'conversation_memory_session_idx';
        """)
        )
        if not result.fetchone():
            conn.execute(
                text("""
                CREATE INDEX conversation_memory_session_idx
                ON conversation_memory (session_id, created_at DESC);
            """)
            )
            conn.commit()
            print("Created index on conversation_memory.session_id")

        print("✓ Vector database tables initialized successfully")
        print(f"  - knowledge_chunks (embedding dim: {dims})")
        print(f"  - conversation_memory (embedding dim: {dims})")


if __name__ == "__main__":
    init_vector_db()
