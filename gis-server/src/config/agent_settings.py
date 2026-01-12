"""
Agent configuration settings.
Centralizes all LangGraph agent and RAG parameters.
"""

from pydantic_settings import BaseSettings


class AgentSettings(BaseSettings):
    """Configuration for the LangGraph agent with Gemini."""

    # Google API
    GOOGLE_API_KEY: str = ""

    # Model configuration
    AGENT_MODEL: str = "gemini-2.0-flash"
    EMBEDDING_MODEL: str = "models/text-embedding-004"

    # Agent safety limits
    AGENT_MAX_ITERATIONS: int = 5
    AGENT_TOOL_TIMEOUT_SECONDS: int = 30
    AGENT_MAX_TOKENS_PER_TURN: int = 4096

    # RAG retrieval settings
    RAG_RETRIEVAL_TOP_K: int = 5
    RAG_CHUNK_SIZE: int = 512
    RAG_CHUNK_OVERLAP: int = 50

    # Embedding dimensions for Gemini text-embedding-004
    EMBEDDING_DIMENSIONS: int = 768

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def is_configured(self) -> bool:
        """Check if agent is properly configured with API key."""
        return bool(
            self.GOOGLE_API_KEY and self.GOOGLE_API_KEY != "your-google-api-key-here"
        )


agent_settings = AgentSettings()
