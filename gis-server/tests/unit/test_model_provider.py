"""
Unit tests for provider-agnostic model runtime configuration.
"""

from src.services.model_provider import (
    RuntimeModelConfig,
    is_runtime_model_configured,
    resolve_runtime_config,
)


def test_resolve_runtime_openai_compatible_overrides_defaults():
    runtime = RuntimeModelConfig(
        provider="openai_compatible",
        model="deepseek-chat",
        api_key="test-key",
        base_url="https://api.deepseek.com/v1/",
        reasoning_mode="react",
    )

    resolved = resolve_runtime_config(runtime)

    assert resolved.provider == "openai_compatible"
    assert resolved.model == "deepseek-chat"
    assert resolved.base_url == "https://api.deepseek.com/v1"
    assert resolved.reasoning_mode == "react"
    assert resolved.is_configured is True


def test_resolve_runtime_gemini_vertex_configuration():
    runtime = RuntimeModelConfig(
        provider="gemini",
        model="gemini-2.5-pro",
        use_vertex_ai=True,
        vertex_project="project-ku",
        vertex_location="asia-southeast1",
    )

    resolved = resolve_runtime_config(runtime)

    assert resolved.provider == "gemini"
    assert resolved.use_vertex_ai is True
    assert resolved.vertex_project == "project-ku"
    assert resolved.vertex_location == "asia-southeast1"
    assert resolved.is_configured is True


def test_runtime_configured_false_when_credentials_missing():
    runtime = RuntimeModelConfig(
        provider="openai_compatible",
        model="deepseek-chat",
        api_key="",
        base_url="https://api.deepseek.com/v1",
    )

    assert is_runtime_model_configured(runtime) is False
