"""
Agent configuration settings.
Centralizes all LangGraph agent and RAG parameters.
"""

from typing import Literal

from pydantic_settings import BaseSettings


class AgentSettings(BaseSettings):
    """Configuration for the LangGraph agent and model providers."""

    # Provider selection
    AGENT_PROVIDER: Literal["gemini", "openai_compatible"] = "openai_compatible"
    AGENT_REASONING_MODE: Literal["react", "cot", "hybrid"] = "hybrid"
    AGENT_ENABLE_CLARIFICATION_LOOP: bool = True
    AGENT_DECOMPOSITION_MAX_NODES: int = 6

    # Google API
    GOOGLE_API_KEY: str = ""
    GEMINI_USE_VERTEX_AI: bool = False
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_CLOUD_LOCATION: str = "us-central1"

    # Model configuration
    AGENT_MODEL: str = "gemini-2.5-flash-lite"
    OPENAI_MODEL: str = "deepseek-chat"
    OPENAI_BASE_URL: str = "https://api.deepseek.com/v1"
    OPENAI_API_KEY: str = ""
    OPENAI_ORG_ID: str = ""
    AGENT_CREDENTIALS_ENCRYPTION_KEY: str = ""
    EMBEDDING_MODEL: str = "models/text-embedding-004"

    # Agent safety limits
    AGENT_MAX_ITERATIONS: int = 12
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

    def is_provider_configured(self, provider: str | None = None) -> bool:
        """Check if a given provider has enough credentials to run."""
        target = provider or self.AGENT_PROVIDER

        if target == "openai_compatible":
            return bool(self.OPENAI_API_KEY)

        if target == "gemini":
            if self.GEMINI_USE_VERTEX_AI:
                return bool(self.GOOGLE_CLOUD_PROJECT and self.GOOGLE_CLOUD_LOCATION)
            return bool(
                self.GOOGLE_API_KEY and self.GOOGLE_API_KEY != "your-google-api-key-here"
            )

        return False

    @property
    def is_configured(self) -> bool:
        """Check if the default configured provider is ready."""
        return self.is_provider_configured()


agent_settings = AgentSettings()
