"""
Provider-agnostic model factory for agent execution and planning.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal, Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai import ChatVertexAI
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from src.config.agent_settings import agent_settings

ProviderName = Literal["gemini", "openai_compatible"]
ReasoningMode = Literal["react", "cot", "hybrid"]


class RuntimeModelConfig(BaseModel):
    """
    Per-request model configuration.
    Used by BYOK to avoid persisting sensitive keys server-side.
    """

    model_config = ConfigDict(extra="ignore")

    provider: ProviderName = "gemini"
    model: str | None = None
    api_key: SecretStr | None = None
    base_url: str | None = None
    organization: str | None = None
    use_vertex_ai: bool = False
    vertex_project: str | None = None
    vertex_location: str | None = None
    reasoning_mode: ReasoningMode | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=64, le=32768)

    @field_validator("base_url")
    @classmethod
    def _strip_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized.rstrip("/") if normalized else None


@dataclass(frozen=True)
class ResolvedModelConfig:
    """Resolved model configuration after defaults and runtime overrides."""

    provider: ProviderName
    model: str
    reasoning_mode: ReasoningMode
    temperature: float
    max_tokens: int
    use_vertex_ai: bool
    api_key: str
    base_url: str
    organization: str
    vertex_project: str
    vertex_location: str

    def cache_key(self) -> str:
        """Stable cache key without exposing the plaintext API key."""
        api_key_hash = (
            hashlib.sha256(self.api_key.encode("utf-8")).hexdigest()[:16]
            if self.api_key
            else ""
        )
        payload = {
            "provider": self.provider,
            "model": self.model,
            "reasoning_mode": self.reasoning_mode,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "use_vertex_ai": self.use_vertex_ai,
            "base_url": self.base_url,
            "organization": self.organization,
            "vertex_project": self.vertex_project,
            "vertex_location": self.vertex_location,
            "api_key_hash": api_key_hash,
        }
        return json.dumps(payload, sort_keys=True)

    @property
    def is_configured(self) -> bool:
        """Whether the config contains enough credentials to run."""
        if self.provider == "openai_compatible":
            return bool(self.api_key and self.base_url)
        if self.use_vertex_ai:
            return bool(self.vertex_project and self.vertex_location)
        return bool(self.api_key)


def resolve_runtime_config(
    runtime_config: RuntimeModelConfig | None = None,
) -> ResolvedModelConfig:
    """Merge runtime overrides with environment defaults."""
    runtime = runtime_config or RuntimeModelConfig(provider=agent_settings.AGENT_PROVIDER)
    provider = runtime.provider or agent_settings.AGENT_PROVIDER

    if provider == "openai_compatible":
        model = runtime.model or agent_settings.OPENAI_MODEL
        api_key = (
            runtime.api_key.get_secret_value()
            if runtime.api_key is not None
            else agent_settings.OPENAI_API_KEY
        )
        base_url = runtime.base_url or agent_settings.OPENAI_BASE_URL
        organization = runtime.organization or agent_settings.OPENAI_ORG_ID
    else:
        model = runtime.model or agent_settings.AGENT_MODEL
        api_key = (
            runtime.api_key.get_secret_value()
            if runtime.api_key is not None
            else agent_settings.GOOGLE_API_KEY
        )
        base_url = ""
        organization = ""

    use_vertex_ai = runtime.use_vertex_ai or (
        provider == "gemini" and agent_settings.GEMINI_USE_VERTEX_AI
    )

    return ResolvedModelConfig(
        provider=provider,
        model=model,
        reasoning_mode=runtime.reasoning_mode or agent_settings.AGENT_REASONING_MODE,
        temperature=runtime.temperature
        if runtime.temperature is not None
        else 0.7,
        max_tokens=runtime.max_tokens
        if runtime.max_tokens is not None
        else agent_settings.AGENT_MAX_TOKENS_PER_TURN,
        use_vertex_ai=use_vertex_ai,
        api_key=api_key,
        base_url=base_url,
        organization=organization,
        vertex_project=runtime.vertex_project or agent_settings.GOOGLE_CLOUD_PROJECT,
        vertex_location=runtime.vertex_location or agent_settings.GOOGLE_CLOUD_LOCATION,
    )


def is_runtime_model_configured(runtime_config: RuntimeModelConfig | None = None) -> bool:
    """Check whether either default or runtime config is executable."""
    return resolve_runtime_config(runtime_config).is_configured


class ModelProvider(Protocol):
    """Provider interface to decouple agent orchestration from model SDKs."""

    name: ProviderName

    def create_chat_model(
        self,
        config: ResolvedModelConfig,
        *,
        temperature: float,
        max_tokens: int,
    ) -> BaseChatModel: ...


class GeminiModelProvider:
    """Gemini provider supporting both AI Studio and Vertex AI runtimes."""

    name: ProviderName = "gemini"

    def create_chat_model(
        self,
        config: ResolvedModelConfig,
        *,
        temperature: float,
        max_tokens: int,
    ) -> BaseChatModel:
        if config.use_vertex_ai:
            return ChatVertexAI(
                model_name=config.model,
                project=config.vertex_project,
                location=config.vertex_location,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

        return ChatGoogleGenerativeAI(
            model=config.model,
            google_api_key=config.api_key,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )


class OpenAICompatibleModelProvider:
    """
    OpenAI-compatible provider for hosted OpenAI and compatible endpoints
    (for example: Ollama, vLLM, Groq, or DeepSeek-compatible gateways).
    """

    name: ProviderName = "openai_compatible"

    def create_chat_model(
        self,
        config: ResolvedModelConfig,
        *,
        temperature: float,
        max_tokens: int,
    ) -> BaseChatModel:
        return ChatOpenAI(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            organization=config.organization or None,
            temperature=temperature,
            max_tokens=max_tokens,
        )


_PROVIDERS: dict[ProviderName, ModelProvider] = {
    "gemini": GeminiModelProvider(),
    "openai_compatible": OpenAICompatibleModelProvider(),
}


def get_model_provider(name: ProviderName) -> ModelProvider:
    """Return provider implementation by name."""
    return _PROVIDERS[name]


def list_supported_providers() -> list[dict[str, object]]:
    """Provider metadata for frontend configuration UI."""
    return [
        {
            "id": "gemini",
            "label": "Google Gemini",
            "supports_vertex_ai": True,
            "supports_multimodal": True,
            "supports_function_calling": True,
        },
        {
            "id": "openai_compatible",
            "label": "OpenAI-Compatible",
            "supports_vertex_ai": False,
            "supports_multimodal": True,
            "supports_function_calling": True,
        },
    ]
