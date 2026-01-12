"""
RAG (Retrieval-Augmented Generation) service.
Uses pgvector for semantic search over knowledge base documents.
"""

import logging

from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector
from sqlalchemy import text
from src.config.agent_settings import agent_settings
from src.config.settings import settings

logger = logging.getLogger(__name__)


class RagService:
    """Service for RAG retrieval using pgvector."""

    def __init__(self):
        self._vector_store: PGVector | None = None
        self._embeddings: GoogleGenerativeAIEmbeddings | None = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of embeddings and vector store."""
        if self._initialized:
            return

        if not agent_settings.is_configured:
            raise ValueError("Agent not configured. Set GOOGLE_API_KEY in .env file.")

        # Initialize Gemini embeddings
        self._embeddings = GoogleGenerativeAIEmbeddings(
            model=agent_settings.EMBEDDING_MODEL,
            google_api_key=agent_settings.GOOGLE_API_KEY,
        )

        # Initialize PGVector store
        # Convert DATABASE_URL to async format if needed
        connection_string = settings.DATABASE_URL
        if connection_string.startswith("postgresql://"):
            connection_string = connection_string.replace(
                "postgresql://", "postgresql+psycopg://", 1
            )

        self._vector_store = PGVector(
            embeddings=self._embeddings,
            collection_name="knowledge_chunks",
            connection=connection_string,
            use_jsonb=True,
        )

        self._initialized = True
        logger.info("RAG service initialized with pgvector")

    def add_documents(self, documents: list[Document]) -> list[str]:
        """
        Add documents to the vector store.

        Args:
            documents: List of LangChain Document objects with page_content and metadata

        Returns:
            List of document IDs

        """
        self._ensure_initialized()
        if self._vector_store is None:
            raise RuntimeError("Vector store not initialized")

        ids = self._vector_store.add_documents(documents)
        logger.info(f"Added {len(documents)} documents to knowledge base")
        return ids

    def similarity_search(
        self,
        query: str,
        k: int | None = None,
    ) -> list[Document]:
        """
        Search for similar documents.

        Args:
            query: Search query
            k: Number of results (defaults to RAG_RETRIEVAL_TOP_K)

        Returns:
            List of matching documents

        """
        self._ensure_initialized()
        if self._vector_store is None:
            raise RuntimeError("Vector store not initialized")

        k = k or agent_settings.RAG_RETRIEVAL_TOP_K
        return self._vector_store.similarity_search(query, k=k)

    def similarity_search_with_score(
        self,
        query: str,
        k: int | None = None,
    ) -> list[tuple[Document, float]]:
        """
        Search with relevance scores.

        Args:
            query: Search query
            k: Number of results

        Returns:
            List of (document, score) tuples

        """
        self._ensure_initialized()
        if self._vector_store is None:
            raise RuntimeError("Vector store not initialized")

        k = k or agent_settings.RAG_RETRIEVAL_TOP_K
        return self._vector_store.similarity_search_with_score(query, k=k)

    def get_document_count(self) -> int:
        """Get total number of documents in the knowledge base."""
        from src.config.database import SessionLocal

        with SessionLocal() as db:
            result = db.execute(
                text(
                    "SELECT COUNT(*) FROM langchain_pg_embedding WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = 'knowledge_chunks')"
                )
            ).scalar()
            return result or 0

    def clear_collection(self):
        """Clear all documents from the knowledge base."""
        from src.config.database import SessionLocal

        with SessionLocal() as db:
            db.execute(
                text(
                    "DELETE FROM langchain_pg_embedding WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = 'knowledge_chunks')"
                )
            )
            db.commit()
            logger.info("Cleared knowledge base collection")


# Singleton instance
rag_service = RagService()


# =============================================================================
# RAG Tool for Agent
# =============================================================================


@tool
def retrieve_knowledge(query: str) -> str:
    """
    Search the knowledge base for relevant documentation and information.

    Use this when you need background information about the system,
    data sources, API capabilities, or terminology.

    Args:
        query: Natural language search query

    Returns:
        Relevant documentation excerpts

    """
    try:
        results = rag_service.similarity_search_with_score(query, k=3)

        if not results:
            return "No relevant documentation found in the knowledge base."

        # Format results with sources
        formatted = []
        for doc, score in results:
            source = doc.metadata.get("source", "unknown")
            section = doc.metadata.get("section", "")
            formatted.append(
                f"[Source: {source}{' - ' + section if section else ''}]\n{doc.page_content}"
            )

        return "\n\n---\n\n".join(formatted)

    except Exception as e:
        logger.error(f"Knowledge retrieval failed: {e}")
        return f"Error retrieving knowledge: {e}"


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """
    Split text into chunks for embedding.

    Args:
        text: Text to split
        chunk_size: Max characters per chunk
        chunk_overlap: Overlap between chunks

    Returns:
        List of text chunks

    """
    chunk_size = chunk_size or agent_settings.RAG_CHUNK_SIZE
    chunk_overlap = chunk_overlap or agent_settings.RAG_CHUNK_OVERLAP

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size

        # Try to break at paragraph or sentence boundary
        if end < len(text):
            # Look for paragraph break
            para_break = text.rfind("\n\n", start, end)
            if para_break > start + chunk_size // 2:
                end = para_break + 2
            else:
                # Look for sentence break
                sent_break = max(
                    text.rfind(". ", start, end),
                    text.rfind("。", start, end),
                    text.rfind("\n", start, end),
                )
                if sent_break > start + chunk_size // 2:
                    end = sent_break + 1

        chunks.append(text[start:end].strip())
        start = end - chunk_overlap

    return [c for c in chunks if c]  # Filter empty chunks
