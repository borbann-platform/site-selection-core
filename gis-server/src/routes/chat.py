"""
Chat API endpoints with provider-agnostic agent orchestration.
"""

import ast
import json
import logging
import math
import re
import time
import uuid as uuid_lib
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.config.agent_settings import agent_settings
from src.config.database import get_db_session
from src.dependencies.auth import get_current_active_user
from src.models.agent_runtime_credential import AgentRuntimeCredential
from src.models.user import User
from src.services.chat_service import ChatService
from src.services.model_provider import (
    RuntimeModelConfig,
    is_runtime_model_configured,
    list_supported_providers,
    resolve_runtime_config,
)
from src.services.secret_encryption import decrypt_secret, encrypt_secret, mask_secret

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)


def sanitize_json_value(obj):
    """
    Recursively sanitize a value for JSON serialization.
    Replaces NaN, Infinity, -Infinity with None.
    """
    if isinstance(obj, dict):
        return {k: sanitize_json_value(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_json_value(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


def is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def _is_valid_lat_lon(lat: Any, lon: Any) -> bool:
    return (
        is_finite_number(lat)
        and is_finite_number(lon)
        and -90 <= float(lat) <= 90
        and -180 <= float(lon) <= 180
    )


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class AttachmentData(BaseModel):
    """Attachment data from frontend map interactions."""

    id: str
    type: str  # "location" | "bbox" | "property"
    data: dict  # {lat, lon} for location, {corners, minLon, maxLon, minLat, maxLat} for bbox
    label: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    session_id: str | None = None  # Optional session for conversation memory
    attachments: list[AttachmentData] | None = None  # Optional spatial attachments
    runtime: RuntimeModelConfig | None = None  # Optional BYOK runtime model config


def build_spatial_context_message(attachments: list[AttachmentData]) -> str:
    """
    Build a context message from spatial attachments.
    This provides the agent with structured location information.
    """
    if not attachments:
        return ""

    parts = ["[SPATIAL CONTEXT FROM MAP]"]

    for attachment in attachments:
        # Sanitize attachment data to prevent NaN/Infinity issues
        sanitized_data = sanitize_json_value(attachment.data)

        if attachment.type == "location":
            lat = sanitized_data.get("lat")
            lon = sanitized_data.get("lon")
            if _is_valid_lat_lon(lat, lon):
                parts.append(
                    f"- PIN LOCATION: latitude={lat}, longitude={lon} (User has selected this specific point on the map)"
                )
            else:
                parts.append(
                    "- PIN LOCATION: ignored due to invalid coordinates (validation failed)"
                )

        elif attachment.type == "bbox":
            min_lon = sanitized_data.get("minLon")
            max_lon = sanitized_data.get("maxLon")
            min_lat = sanitized_data.get("minLat")
            max_lat = sanitized_data.get("maxLat")
            corners = sanitized_data.get("corners")

            if (
                min_lon is not None
                and max_lon is not None
                and min_lat is not None
                and max_lat is not None
            ):
                # Calculate center point
                center_lat = (float(min_lat) + float(max_lat)) / 2
                center_lon = (float(min_lon) + float(max_lon)) / 2

                parts.append(
                    f"- BOUNDING BOX AREA: The user has drawn an area on the map"
                )
                parts.append(
                    f"  - Bounds: west={min_lon}, south={min_lat}, east={max_lon}, north={max_lat}"
                )
                parts.append(
                    f"  - Center: latitude={center_lat}, longitude={center_lon}"
                )
                if corners:
                    parts.append(f"  - Polygon corners (4 points): {corners}")
                locator = sanitized_data.get("locator")
                if locator:
                    parts.append(f"  - Locator: {locator}")
                parts.append(
                    "  - USE THESE BOUNDS when searching for properties or analyzing this area"
                )
            else:
                parts.append(
                    "- BOUNDING BOX AREA: ignored due to invalid bounds (validation failed)"
                )

        elif attachment.type == "property":
            property_id = sanitized_data.get("id")
            property_data = sanitized_data

            if property_id:
                parts.append(f"- SELECTED PROPERTY: ID={property_id}")
                house_ref = property_data.get("house_ref")
                locator = property_data.get("locator")
                if house_ref:
                    parts.append(f"  House Reference: {house_ref}")
                if locator:
                    parts.append(f"  Locator: {locator}")
                # Include key property details if available
                details = []
                total_price = property_data.get("total_price")
                if is_finite_number(total_price):
                    details.append(f"Price: ฿{property_data['total_price']:,.0f}")
                if property_data.get("building_style_desc"):
                    details.append(f"Type: {property_data['building_style_desc']}")
                if property_data.get("amphur"):
                    details.append(f"District: {property_data['amphur']}")
                if property_data.get("building_area"):
                    details.append(
                        f"Building Area: {property_data['building_area']} sqm"
                    )
                if _is_valid_lat_lon(
                    property_data.get("lat"), property_data.get("lon")
                ):
                    details.append(
                        f"Location: ({property_data['lat']}, {property_data['lon']})"
                    )

                if details:
                    parts.append(f"  Details: {', '.join(details)}")

    parts.append(
        "\nWhen the user refers to 'this location', 'here', 'this area', or 'the selected area', "
        "use the coordinates/bounds provided above."
    )

    return "\n".join(parts)


def _extract_provider_error_payload(raw: str) -> tuple[int | None, str | None, str]:
    status_code: int | None = None
    provider_code: str | None = None
    message = raw

    status_match = re.search(r"Error code:\s*(\d{3})", raw)
    if not status_match:
        status_match = re.search(r"status(?:_code)?[=: ]+(\d{3})", raw, re.IGNORECASE)
    if status_match:
        status_code = int(status_match.group(1))

    payload_candidate = None
    if " - " in raw:
        payload_candidate = raw.split(" - ", 1)[1].strip()
    elif raw.startswith("{") and raw.endswith("}"):
        payload_candidate = raw

    if payload_candidate:
        parsed = None
        try:
            parsed = json.loads(payload_candidate)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(payload_candidate)
            except (SyntaxError, ValueError):
                parsed = None

        if isinstance(parsed, dict):
            maybe_error = parsed.get("error")
            payload = maybe_error if isinstance(maybe_error, dict) else parsed
            extracted_message = payload.get("message") or payload.get("detail")
            if isinstance(extracted_message, str):
                message = extracted_message
            extracted_code = payload.get("code")
            if extracted_code is not None:
                provider_code = str(extracted_code)

    return status_code, provider_code, message


def build_agent_error_payload(raw_error: Any) -> dict[str, Any]:
    raw = str(raw_error)
    status_code, provider_code, provider_message = _extract_provider_error_payload(raw)
    lowered = provider_message.lower()

    title = "Model request failed"
    user_message = "The provider request failed. Please retry or update provider settings."
    retryable = False

    if (
        status_code == 429
        or provider_code in {"1113"}
        or "insufficient balance" in lowered
        or "quota" in lowered
    ):
        title = "Provider quota exceeded"
        user_message = (
            "The provider rejected the request because quota or account balance is exhausted. "
            "Recharge or switch provider/model in Settings."
        )
        retryable = False
    elif status_code in {401, 403} or "invalid api key" in lowered:
        title = "Provider authentication failed"
        user_message = (
            "The provider key is invalid or unauthorized. Update your API key in Settings."
        )
    elif status_code == 404 or "model" in lowered and "not found" in lowered:
        title = "Model not found"
        user_message = (
            "The selected model is unavailable on this provider endpoint. Choose a valid model."
        )
    elif status_code in {408, 500, 502, 503, 504} or "timeout" in lowered:
        title = "Provider temporarily unavailable"
        user_message = "The provider is temporarily unavailable. Please retry in a moment."
        retryable = True

    return {
        "title": title,
        "message": user_message,
        "status_code": status_code,
        "provider_code": provider_code,
        "raw_message": provider_message,
        "retryable": retryable,
    }


def _build_agent_not_configured_error() -> dict[str, Any]:
    return {
        "title": "Model provider not configured",
        "message": (
            "No executable model configuration was found. Configure BYOK credentials in Settings."
        ),
        "status_code": None,
        "provider_code": None,
        "raw_message": "Missing model provider credentials",
        "retryable": False,
    }


async def generate_unconfigured_chat_stream():
    """Emit non-mock error for the legacy text stream endpoint."""
    payload = _build_agent_not_configured_error()
    yield f"data: {payload['title']}: {payload['message']}\n\n"
    yield "data: [DONE]\n\n"


async def generate_unconfigured_agent_stream_with_steps():
    """Emit structured error stream when model runtime is not configured."""
    payload = _build_agent_not_configured_error()
    yield f"data: {json.dumps({'event': 'thinking', 'data': {'thinking': False}})}\n\n"
    yield f"data: {json.dumps({'event': 'error', 'data': payload})}\n\n"
    yield f"data: {json.dumps({'event': 'done', 'data': None})}\n\n"


async def generate_agent_stream(
    messages: list[ChatMessage],
    debug: bool = False,
    runtime_config: RuntimeModelConfig | None = None,
):
    """Generate streaming response from the LangGraph agent."""
    from src.services.agent_graph import agent_service

    # Convert to dict format
    message_dicts = [{"role": m.role, "content": m.content} for m in messages]

    try:
        async for event in agent_service.astream(
            message_dicts, runtime_config=runtime_config
        ):
            event_type = event.get("type", "")
            content = event.get("content", "")

            if event_type == "token":
                # Stream text tokens
                yield f"data: {content}\n\n"

            elif event_type == "clarification":
                clarification = content.get("message", "")
                yield f"data: {clarification}\n\n"

            elif event_type == "final":
                yield f"data: {content}\n\n"

            elif event_type == "tool_call" and debug:
                # Include tool call info in debug mode
                tool_info = content
                name = tool_info.get("name", "unknown")
                yield f"data: \n[{name}]\n\n"

            elif event_type == "decomposition" and debug:
                yield "data: \n[Task decomposition created]\n\n"

            elif event_type == "tool_result" and debug:
                # Include truncated tool result in debug mode
                truncated = content[:200] + "..." if len(content) > 200 else content
                yield f"data: \n[-> {truncated}]\n\n"

            elif event_type == "error":
                payload = build_agent_error_payload(content)
                yield f"data: \n[{payload['title']}: {payload['message']}]\n\n"

        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Agent stream error: {e}", exc_info=True)
        payload = build_agent_error_payload(e)
        yield f"data: {payload['title']}: {payload['message']}\n\n"
        yield "data: [DONE]\n\n"


@router.post("")
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
    debug: bool = Query(False, description="Include tool call info in response"),
):
    """
    Stream chat responses from the AI agent.
    Returns Server-Sent Events (SSE) stream.

    Set debug=true to include tool call information in the stream.
    """
    runtime_config = _resolve_effective_runtime_config(
        request.runtime,
        db=db,
        user=current_user,
    )

    # Use real agent if configured; otherwise emit explicit configuration error.
    if is_runtime_model_configured(runtime_config):
        stream_generator = generate_agent_stream(
            request.messages,
            debug=debug,
            runtime_config=runtime_config,
        )
    else:
        logger.warning("Agent not configured for user=%s", current_user.id)
        stream_generator = generate_unconfigured_chat_stream()

    return StreamingResponse(
        stream_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/status")
async def chat_status():
    """Check if the chat agent is properly configured."""
    resolved = resolve_runtime_config()
    return {
        "agent_configured": resolved.is_configured,
        "provider": resolved.provider,
        "model": resolved.model if resolved.is_configured else None,
        "embedding_model": agent_settings.EMBEDDING_MODEL
        if resolved.is_configured
        else None,
        "max_iterations": agent_settings.AGENT_MAX_ITERATIONS,
        "reasoning_mode": agent_settings.AGENT_REASONING_MODE,
        "clarification_loop": agent_settings.AGENT_ENABLE_CLARIFICATION_LOOP,
        "supported_providers": list_supported_providers(),
    }


@router.get("/providers")
async def get_supported_model_providers():
    """Return provider metadata and safe defaults for BYOK UI configuration."""
    resolved = resolve_runtime_config()
    return {
        "default_provider": agent_settings.AGENT_PROVIDER,
        "default_model": resolved.model,
        "reasoning_mode": agent_settings.AGENT_REASONING_MODE,
        "supported_providers": list_supported_providers(),
    }


class ProviderValidationRequest(BaseModel):
    runtime: RuntimeModelConfig


@router.post("/providers/validate")
async def validate_model_provider_config(
    request: ProviderValidationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
):
    """
    Validate runtime provider config shape and credential completeness.
    Does not persist credentials.
    """
    runtime = request.runtime
    if runtime.api_key is None:
        try:
            stored_runtime = _load_user_runtime_config(db, current_user.id)
        except ValueError as exc:
            logger.warning(
                "Unable to decrypt runtime key while validating provider for user=%s: %s",
                current_user.id,
                exc,
            )
            stored_runtime = None
        if stored_runtime and stored_runtime.api_key is not None:
            runtime = runtime.model_copy(
                update={"api_key": stored_runtime.api_key.get_secret_value()}
            )

    resolved = resolve_runtime_config(runtime)
    return {
        "valid": resolved.is_configured,
        "provider": resolved.provider,
        "model": resolved.model,
        "reasoning_mode": resolved.reasoning_mode,
        "missing": [] if resolved.is_configured else ["credentials"],
    }


class RuntimeConfigUpsertRequest(BaseModel):
    runtime: RuntimeModelConfig


def _public_runtime_payload(runtime: RuntimeModelConfig | None) -> dict[str, Any]:
    if runtime is None:
        return {}
    return runtime.model_dump(exclude_none=True, exclude={"api_key"})


def _load_user_runtime_credential(
    db: Session, user_id: uuid_lib.UUID
) -> AgentRuntimeCredential | None:
    return (
        db.query(AgentRuntimeCredential)
        .filter(AgentRuntimeCredential.user_id == user_id)
        .first()
    )


def _credential_to_runtime_config(
    credential: AgentRuntimeCredential,
) -> RuntimeModelConfig:
    api_key: str | None = None
    if credential.encrypted_api_key:
        api_key = decrypt_secret(credential.encrypted_api_key)

    return RuntimeModelConfig(
        provider=credential.provider,  # type: ignore[arg-type]
        model=credential.model,
        api_key=api_key,
        base_url=credential.base_url,
        organization=credential.organization,
        use_vertex_ai=credential.use_vertex_ai,
        vertex_project=credential.vertex_project,
        vertex_location=credential.vertex_location,
        reasoning_mode=credential.reasoning_mode,  # type: ignore[arg-type]
        temperature=credential.temperature,
        max_tokens=credential.max_tokens,
    )


def _load_user_runtime_config(
    db: Session,
    user_id: uuid_lib.UUID,
) -> RuntimeModelConfig | None:
    credential = _load_user_runtime_credential(db, user_id)
    if credential is None:
        return None
    return _credential_to_runtime_config(credential)


def _resolve_effective_runtime_config(
    request_runtime: RuntimeModelConfig | None,
    *,
    db: Session,
    user: User,
) -> RuntimeModelConfig | None:
    if request_runtime is not None:
        return request_runtime
    try:
        return _load_user_runtime_config(db, user.id)
    except ValueError as exc:
        logger.error(
            "Failed to decrypt stored runtime credentials for user=%s: %s",
            user.id,
            exc,
        )
        return None


def _build_runtime_config_response(
    *,
    source: str,
    runtime: RuntimeModelConfig | None,
    has_api_key: bool,
    api_key_masked: str = "",
) -> dict[str, Any]:
    resolved = resolve_runtime_config(runtime)
    return {
        "configured": resolved.is_configured,
        "source": source,
        "runtime": _public_runtime_payload(runtime),
        "has_api_key": has_api_key,
        "api_key_masked": api_key_masked,
        "effective_provider": resolved.provider,
        "effective_model": resolved.model,
        "reasoning_mode": resolved.reasoning_mode,
    }


@router.get("/runtime-config")
async def get_runtime_config(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
):
    """Get the current user's stored runtime model configuration."""
    credential = _load_user_runtime_credential(db, current_user.id)
    if credential is None:
        default_runtime = RuntimeModelConfig(provider=agent_settings.AGENT_PROVIDER)
        resolved = resolve_runtime_config(default_runtime)
        return _build_runtime_config_response(
            source="environment" if resolved.is_configured else "none",
            runtime=default_runtime,
            has_api_key=bool(resolved.api_key),
        )

    try:
        runtime = _credential_to_runtime_config(credential)
    except ValueError as exc:
        logger.error(
            "Failed to decrypt stored runtime credentials for user=%s: %s",
            current_user.id,
            exc,
        )
        return _build_runtime_config_response(
            source="none",
            runtime=RuntimeModelConfig(provider=agent_settings.AGENT_PROVIDER),
            has_api_key=False,
        )
    key_mask = mask_secret(runtime.api_key.get_secret_value() if runtime.api_key else "")
    return _build_runtime_config_response(
        source="database",
        runtime=runtime.model_copy(update={"api_key": None}),
        has_api_key=bool(credential.encrypted_api_key),
        api_key_masked=key_mask,
    )


@router.put("/runtime-config")
async def upsert_runtime_config(
    request: RuntimeConfigUpsertRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
):
    """Create or update encrypted per-user runtime model configuration."""
    credential = _load_user_runtime_credential(db, current_user.id)
    if credential is None:
        credential = AgentRuntimeCredential(user_id=current_user.id)
        db.add(credential)

    runtime = request.runtime
    credential.provider = runtime.provider
    credential.model = runtime.model
    credential.base_url = runtime.base_url
    credential.organization = runtime.organization
    credential.use_vertex_ai = bool(runtime.use_vertex_ai)
    credential.vertex_project = runtime.vertex_project
    credential.vertex_location = runtime.vertex_location
    credential.reasoning_mode = runtime.reasoning_mode
    credential.temperature = runtime.temperature
    credential.max_tokens = runtime.max_tokens

    if runtime.api_key is not None:
        api_key_value = runtime.api_key.get_secret_value().strip()
        if api_key_value:
            credential.encrypted_api_key = encrypt_secret(api_key_value)
            credential.api_key_last4 = api_key_value[-4:]
        else:
            credential.encrypted_api_key = None
            credential.api_key_last4 = None

    db.commit()
    db.refresh(credential)

    persisted_runtime = _credential_to_runtime_config(credential)
    key_mask = mask_secret(
        persisted_runtime.api_key.get_secret_value() if persisted_runtime.api_key else ""
    )
    return _build_runtime_config_response(
        source="database",
        runtime=persisted_runtime.model_copy(update={"api_key": None}),
        has_api_key=bool(credential.encrypted_api_key),
        api_key_masked=key_mask,
    )


@router.delete("/runtime-config")
async def delete_runtime_config(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
):
    """Delete the current user's stored runtime model configuration."""
    credential = _load_user_runtime_credential(db, current_user.id)
    if credential is not None:
        db.delete(credential)
        db.commit()
    return {"deleted": True}


# ============ Agent Stream Endpoint (with tool steps) ============


class AgentStep(BaseModel):
    id: str
    type: str  # "tool_call" | "thinking" | "waiting_user"
    name: str
    status: str  # "running", "complete", "error", "waiting"
    input: dict | None = None
    output: str | None = None
    start_time: int | None = None
    end_time: int | None = None


class AgentStreamEvent(BaseModel):
    event: str  # "thinking", "step", "token", "error", "done"
    data: dict | None = None


async def generate_real_agent_stream_with_steps(
    messages: list[ChatMessage],
    session_id: str | None = None,
    attachments: list[AttachmentData] | None = None,
    db_session_id: str | None = None,
    db: Session | None = None,
    user: User | None = None,
    runtime_config: RuntimeModelConfig | None = None,
):
    """
    Generate streaming response from real LangGraph agent with structured events.

    Event types emitted:
    - thinking: {"thinking": true/false}
    - step: {"id": str, "name": str, "status": "running"|"complete"|"error", "input": dict, "output": str}
    - token: {"token": str}
    - done: null

    Args:
        messages: List of chat messages
        session_id: Optional session ID for in-memory conversation memory (legacy)
        attachments: Optional list of spatial attachments (bbox, location, property)
        db_session_id: Optional database session ID for persistent storage
        db: Optional database session for persistence
        user: Optional authenticated user
        runtime_config: Optional runtime model provider config (BYOK)
    """
    from src.services.agent_graph import agent_service
    from src.services.conversation_memory import conversation_memory

    # Convert messages to dict format
    message_dicts = [{"role": m.role, "content": m.content} for m in messages]

    # Build spatial context from attachments
    spatial_context = ""
    attachments_data = None
    if attachments:
        spatial_context = build_spatial_context_message(attachments)
        attachments_data = [a.model_dump() for a in attachments]

    # Inject spatial context into the last user message if present
    if spatial_context and message_dicts:
        # Find the last user message and append spatial context
        for i in range(len(message_dicts) - 1, -1, -1):
            if message_dicts[i]["role"] == "user":
                message_dicts[i]["content"] = (
                    message_dicts[i]["content"] + "\n\n" + spatial_context
                )
                break

    # Persistent session: Load history from database
    if db_session_id and db and user:
        try:
            chat_service = ChatService(db)
            db_session = chat_service.get_session(
                uuid_lib.UUID(db_session_id), user.id, include_messages=True
            )
            if db_session and db_session.messages:
                history = [
                    {"role": m.role, "content": m.content}
                    for m in db_session.messages[-10:]  # Last 10 messages for context
                ]
                # Prepend history (excluding current message which is already in message_dicts)
                if history:
                    message_dicts = history + message_dicts[-1:]

            # Save the new user message to database
            user_msg = messages[-1] if messages else None
            if user_msg and user_msg.role == "user":
                chat_service.add_message(
                    session_id=uuid_lib.UUID(db_session_id),
                    role="user",
                    content=user_msg.content,
                    attachments=attachments_data,
                )
        except Exception as e:
            logger.warning(f"Failed to load/save from DB session: {e}")

    # Legacy in-memory session support
    elif session_id:
        history = conversation_memory.get_history(session_id, limit=10)
        if history:
            # Prepend history to messages (but keep the new user message)
            message_dicts = history + message_dicts

        # Save the new user message (without spatial context for cleaner history)
        user_msg = messages[-1] if messages else None
        if user_msg and user_msg.role == "user":
            conversation_memory.add_message(session_id, "user", user_msg.content)

    # Emit initial thinking event
    yield f"data: {json.dumps({'event': 'thinking', 'data': {'thinking': True}})}\n\n"

    current_tool_id: str | None = None
    current_tool_name: str | None = None
    current_tool_start: int | None = None
    response_content = ""
    has_started_response = False
    collected_tool_calls: list[dict[str, Any]] = []  # Track tool calls for persistence

    try:
        async for event in agent_service.astream(
            message_dicts, runtime_config=runtime_config
        ):
            event_type = event.get("type", "")
            content = event.get("content", "")

            if event_type == "decomposition":
                step_data = {
                    "id": f"step-decomposition-{int(time.time() * 1000)}",
                    "type": "thinking",
                    "name": "Task Decomposition DAG",
                    "status": "complete",
                    "output": json.dumps(content, ensure_ascii=False),
                    "start_time": int(time.time() * 1000),
                    "end_time": int(time.time() * 1000),
                }
                yield f"data: {json.dumps({'event': 'step', 'data': step_data})}\n\n"
                continue

            if event_type == "clarification":
                clarification_data = content if isinstance(content, dict) else {}
                clarification_message = clarification_data.get(
                    "message",
                    "I need more detail before executing this request.",
                )
                step_data = {
                    "id": f"step-clarification-{int(time.time() * 1000)}",
                    "type": "waiting_user",
                    "name": "Clarification Required",
                    "status": "waiting",
                    "output": clarification_message,
                    "start_time": int(time.time() * 1000),
                }
                yield f"data: {json.dumps({'event': 'thinking', 'data': {'thinking': False}})}\n\n"
                yield f"data: {json.dumps({'event': 'step', 'data': step_data})}\n\n"
                yield f"data: {json.dumps({'event': 'token', 'data': {'token': clarification_message}})}\n\n"
                response_content += clarification_message
                break

            if event_type == "tool_call":
                # A new tool is being called
                tool_info = content
                current_tool_id = (
                    f"step-{int(time.time() * 1000)}-{uuid_lib.uuid4().hex[:6]}"
                )
                current_tool_name = tool_info.get("name", "unknown")
                current_tool_start = int(time.time() * 1000)

                # Stop thinking indicator
                yield f"data: {json.dumps({'event': 'thinking', 'data': {'thinking': False}})}\n\n"

                # Emit running step
                step_data = {
                    "id": current_tool_id,
                    "type": "tool_call",
                    "name": current_tool_name,
                    "status": "running",
                    "input": tool_info.get("input", {}),
                    "start_time": current_tool_start,
                }
                yield f"data: {json.dumps({'event': 'step', 'data': step_data})}\n\n"

            elif event_type == "tool_result":
                # Tool execution completed
                if current_tool_id:
                    end_time = int(time.time() * 1000)

                    # Truncate output for display
                    output_str = str(content)
                    if len(output_str) > 1000:
                        output_str = output_str[:1000] + "..."

                    step_data = {
                        "id": current_tool_id,
                        "type": "tool_call",
                        "name": current_tool_name,
                        "status": "complete",
                        "output": output_str,
                        "start_time": current_tool_start,
                        "end_time": end_time,
                    }
                    yield f"data: {json.dumps({'event': 'step', 'data': step_data})}\n\n"

                    # Collect tool call for persistence
                    collected_tool_calls.append(step_data)

                    # Reset tool tracking
                    current_tool_id = None
                    current_tool_name = None
                    current_tool_start = None

                    # Resume thinking
                    yield f"data: {json.dumps({'event': 'thinking', 'data': {'thinking': True}})}\n\n"

            elif event_type == "token":
                # LLM is generating text
                if not has_started_response:
                    # Stop thinking when response starts
                    yield f"data: {json.dumps({'event': 'thinking', 'data': {'thinking': False}})}\n\n"
                    has_started_response = True

                response_content += content
                yield f"data: {json.dumps({'event': 'token', 'data': {'token': content}})}\n\n"

            elif event_type == "final":
                final_text = str(content)
                if final_text and not has_started_response:
                    yield f"data: {json.dumps({'event': 'thinking', 'data': {'thinking': False}})}\n\n"
                    response_content += final_text
                    yield f"data: {json.dumps({'event': 'token', 'data': {'token': final_text}})}\n\n"
                    has_started_response = True

            elif event_type == "error":
                # Handle errors
                error_payload = build_agent_error_payload(content)
                if current_tool_id:
                    step_data = {
                        "id": current_tool_id,
                        "type": "tool_call",
                        "name": current_tool_name or "unknown",
                        "status": "error",
                        "output": error_payload["raw_message"],
                        "end_time": int(time.time() * 1000),
                    }
                    yield f"data: {json.dumps({'event': 'step', 'data': step_data})}\n\n"

                yield f"data: {json.dumps({'event': 'thinking', 'data': {'thinking': False}})}\n\n"
                yield f"data: {json.dumps({'event': 'error', 'data': error_payload})}\n\n"
                response_content += (
                    f"{error_payload['title']}: {error_payload['message']}"
                )
                break

        # Save assistant response to database or memory
        if db_session_id and db and user and response_content:
            try:
                chat_service = ChatService(db)
                chat_service.add_message(
                    session_id=uuid_lib.UUID(db_session_id),
                    role="assistant",
                    content=response_content,
                    tool_calls=collected_tool_calls if collected_tool_calls else None,
                )
            except Exception as e:
                logger.warning(f"Failed to save assistant response to DB: {e}")
        elif session_id and response_content:
            conversation_memory.add_message(session_id, "assistant", response_content)

    except Exception as e:
        logger.error(f"Real agent stream error: {e}", exc_info=True)
        error_payload = build_agent_error_payload(e)
        yield f"data: {json.dumps({'event': 'thinking', 'data': {'thinking': False}})}\n\n"
        yield f"data: {json.dumps({'event': 'error', 'data': error_payload})}\n\n"
        response_content += f"{error_payload['title']}: {error_payload['message']}"

    # Emit done event
    yield f"data: {json.dumps({'event': 'done', 'data': None})}\n\n"


@router.post("/agent")
async def agent_chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
):
    """
    Stream agent chat responses with structured tool steps.
    Returns Server-Sent Events (SSE) with JSON-formatted events.

    Event types:
    - thinking: Agent is processing {"thinking": true/false}
    - step: Tool call step {"id", "name", "status", "input", "output", "start_time", "end_time"}
    - token: Text token for response {"token": str}
    - error: Structured provider/runtime error {"title", "message", ...}
    - done: Stream complete {null}

    Optional:
    - Pass session_id to maintain conversation context across requests.
    - Pass attachments for spatial context (bbox, location, property selections from map).

    Authentication:
    - User must be authenticated. Messages are persisted to the database.
    """
    db_session_id = None

    # User is always authenticated now - use database sessions
    chat_service = ChatService(db)
    if request.session_id:
        # Validate the session belongs to the user
        try:
            session = chat_service.get_session(
                uuid_lib.UUID(request.session_id),
                current_user.id,
                include_messages=False,
            )
            if session:
                db_session_id = request.session_id
            else:
                # Session doesn't exist or doesn't belong to user - create new
                new_session = chat_service.create_session(user_id=current_user.id)
                db_session_id = str(new_session.id)
        except Exception as e:
            logger.warning(f"Failed to validate session: {e}")
            # Fall back to creating a new session
            new_session = chat_service.create_session(user_id=current_user.id)
            db_session_id = str(new_session.id)
    else:
        # No session_id provided - create new database session
        new_session = chat_service.create_session(user_id=current_user.id)
        db_session_id = str(new_session.id)

    runtime_config = _resolve_effective_runtime_config(
        request.runtime,
        db=db,
        user=current_user,
    )

    # Choose real agent when configured; otherwise emit explicit configuration error.
    if is_runtime_model_configured(runtime_config):
        logger.info(
            f"Using real agent for session db={db_session_id} "
            f"with {len(request.attachments or [])} attachments "
            f"provider={resolve_runtime_config(runtime_config).provider}"
        )
        stream_generator = generate_real_agent_stream_with_steps(
            messages=request.messages,
            session_id=None,  # No legacy in-memory session
            attachments=request.attachments,
            db_session_id=db_session_id,
            db=db,
            user=current_user,
            runtime_config=runtime_config,
        )
    else:
        logger.warning("Agent not configured for user=%s", current_user.id)
        stream_generator = generate_unconfigured_agent_stream_with_steps()

    streaming_response = StreamingResponse(
        stream_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-ID": db_session_id,
        },
    )

    # Schedule title generation in background (only for new sessions)
    if db_session_id and len(request.messages) == 1:

        async def generate_title_background():
            try:
                chat_service = ChatService(db)
                await chat_service.generate_title(
                    uuid_lib.UUID(db_session_id), current_user.id
                )
            except Exception as e:
                logger.warning(f"Background title generation failed: {e}")

        background_tasks.add_task(generate_title_background)

    return streaming_response


@router.post("/memory-sessions")
async def create_memory_session():
    """Create a new in-memory conversation session (legacy, use /sessions for persistent)."""
    from src.services.conversation_memory import conversation_memory

    session_id = conversation_memory.create_session()
    return {"session_id": session_id}


@router.get("/memory-sessions/{session_id}/history")
async def get_memory_session_history(session_id: str, limit: int = Query(20, le=100)):
    """Get conversation history for an in-memory session (legacy)."""
    from src.services.conversation_memory import conversation_memory

    history = conversation_memory.get_history(session_id, limit=limit)
    return {"session_id": session_id, "messages": history}


@router.delete("/memory-sessions/{session_id}")
async def clear_memory_session(session_id: str):
    """Clear conversation history for an in-memory session (legacy)."""
    from src.services.conversation_memory import conversation_memory

    conversation_memory.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}
