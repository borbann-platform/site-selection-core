"""
Chat API endpoints.
Provides agentic chatbot with streaming responses using LangGraph + Gemini.
"""

import asyncio
import json
import logging
import math
import random
import time
import uuid

from fastapi import APIRouter, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from src.config.agent_settings import agent_settings

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
            if lat and lon:
                parts.append(
                    f"- PIN LOCATION: latitude={lat}, longitude={lon} (User has selected this specific point on the map)"
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
                parts.append(
                    "  - USE THESE BOUNDS when searching for properties or analyzing this area"
                )

        elif attachment.type == "property":
            property_id = sanitized_data.get("id")
            property_data = sanitized_data

            if property_id:
                parts.append(f"- SELECTED PROPERTY: ID={property_id}")
                # Include key property details if available
                details = []
                if property_data.get("total_price"):
                    details.append(f"Price: ฿{property_data['total_price']:,.0f}")
                if property_data.get("building_style_desc"):
                    details.append(f"Type: {property_data['building_style_desc']}")
                if property_data.get("amphur"):
                    details.append(f"District: {property_data['amphur']}")
                if property_data.get("building_area"):
                    details.append(
                        f"Building Area: {property_data['building_area']} sqm"
                    )
                if property_data.get("lat") and property_data.get("lon"):
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


# Mock responses for fallback when agent is not configured
MOCK_RESPONSES = [
    "Based on the current market data, properties in this area have seen a 5% increase in value over the past year.",
    "The average price per square meter in Bangkok is around 80,000-120,000 THB, depending on the district.",
    "I can help you analyze property prices. What specific area or property type are you interested in?",
    "Looking at the data, บางกะปิ district has affordable options with good public transit access.",
    "For investment purposes, areas near new BTS extensions typically show strong appreciation.",
    "The price you mentioned seems reasonable for that location. Would you like me to find comparable properties?",
]


async def generate_mock_stream(user_message: str):
    """Generate mock streaming response when agent is not configured."""
    response = random.choice(MOCK_RESPONSES)

    if "price" in user_message.lower():
        response = "Based on our database, the average house price in Bangkok is around 4.5 million THB. Prices vary significantly by district - from 2M in outer areas to 15M+ in prime locations like Sukhumvit."
    elif "predict" in user_message.lower() or "forecast" in user_message.lower():
        response = "Our price prediction model suggests that properties in developing areas near new transit lines could see 10-15% appreciation over the next 2 years. Would you like me to analyze a specific location?"
    elif "recommend" in user_message.lower() or "suggest" in user_message.lower():
        response = "Based on your criteria, I'd recommend looking at properties in Lat Phrao or Bang Kapi districts. They offer good value with improving infrastructure and are well-connected to the city center."

    # Add warning about mock mode
    response = "[Mock Mode - Set GOOGLE_API_KEY for full agent]\n\n" + response

    words = response.split()
    for i, word in enumerate(words):
        chunk = f" {word}" if i > 0 else word
        yield f"data: {chunk}\n\n"
        await asyncio.sleep(random.uniform(0.03, 0.08))

    yield "data: [DONE]\n\n"


async def generate_agent_stream(messages: list[ChatMessage], debug: bool = False):
    """Generate streaming response from the LangGraph agent."""
    from src.services.agent_graph import agent_service

    # Convert to dict format
    message_dicts = [{"role": m.role, "content": m.content} for m in messages]

    try:
        async for event in agent_service.astream(message_dicts):
            event_type = event.get("type", "")
            content = event.get("content", "")

            if event_type == "token":
                # Stream text tokens
                yield f"data: {content}\n\n"

            elif event_type == "tool_call" and debug:
                # Include tool call info in debug mode
                tool_info = content
                name = tool_info.get("name", "unknown")
                yield f"data: \n[{name}]\n\n"

            elif event_type == "tool_result" and debug:
                # Include truncated tool result in debug mode
                truncated = content[:200] + "..." if len(content) > 200 else content
                yield f"data: \n[-> {truncated}]\n\n"

            elif event_type == "error":
                yield f"data: \n[Error: {content}]\n\n"

        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Agent stream error: {e}", exc_info=True)
        yield f"data: Sorry, I encountered an error: {e!s}\n\n"
        yield "data: [DONE]\n\n"


@router.post("")
async def chat(
    request: ChatRequest,
    debug: bool = Query(False, description="Include tool call info in response"),
):
    """
    Stream chat responses from the AI agent.
    Returns Server-Sent Events (SSE) stream.

    Set debug=true to include tool call information in the stream.
    """
    # Get the last user message for context
    user_message = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_message = msg.content
            break

    # Use agent if configured, otherwise fall back to mock
    if agent_settings.is_configured:
        stream_generator = generate_agent_stream(request.messages, debug=debug)
    else:
        logger.warning("Agent not configured, using mock responses")
        stream_generator = generate_mock_stream(user_message)

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
    return {
        "agent_configured": agent_settings.is_configured,
        "model": agent_settings.AGENT_MODEL if agent_settings.is_configured else None,
        "embedding_model": agent_settings.EMBEDDING_MODEL
        if agent_settings.is_configured
        else None,
        "max_iterations": agent_settings.AGENT_MAX_ITERATIONS,
    }


# ============ Agent Stream Endpoint (with tool steps) ============


class AgentStep(BaseModel):
    id: str
    type: str  # "tool_call"
    name: str
    status: str  # "running", "complete", "error"
    input: dict | None = None
    output: str | None = None
    start_time: int | None = None
    end_time: int | None = None


class AgentStreamEvent(BaseModel):
    event: str  # "thinking", "step", "token", "done"
    data: dict | None = None


def select_mock_tools(message: str) -> list[dict]:
    """Select mock tools based on message content."""
    lower_msg = message.lower()

    if (
        "price" in lower_msg
        or "ราคา" in lower_msg
        or "หา" in lower_msg
        or "บ้าน" in lower_msg
    ):
        return [
            {
                "name": "search_properties",
                "input": {"district": "บางกะปิ", "limit": 5},
                "output": {
                    "count": 5,
                    "properties": [
                        {
                            "id": 1,
                            "price": 4500000,
                            "district": "บางกะปิ",
                            "building_style": "บ้านเดี่ยว",
                        },
                        {
                            "id": 2,
                            "price": 5200000,
                            "district": "ลาดพร้าว",
                            "building_style": "ทาวน์เฮ้าส์",
                        },
                        {
                            "id": 3,
                            "price": 3800000,
                            "district": "บางกะปิ",
                            "building_style": "บ้านเดี่ยว",
                        },
                    ],
                },
                "duration": 1.2,
            },
            {
                "name": "get_market_statistics",
                "input": {"district": "บางกะปิ"},
                "output": {
                    "avg_price": 4800000,
                    "median_price": 4500000,
                    "price_change_yoy": 5.2,
                    "total_listings": 1245,
                },
                "duration": 0.8,
            },
        ]

    if (
        "location" in lower_msg
        or "area" in lower_msg
        or "พื้นที่" in lower_msg
        or "ทำเล" in lower_msg
    ):
        return [
            {
                "name": "get_location_intelligence",
                "input": {
                    "latitude": 13.7563,
                    "longitude": 100.5018,
                    "radius_meters": 1000,
                },
                "output": {
                    "transit_score": 85,
                    "walkability_score": 72,
                    "flood_risk": "low",
                    "schools_nearby": 8,
                },
                "duration": 1.5,
            },
            {
                "name": "analyze_catchment",
                "input": {"latitude": 13.7563, "longitude": 100.5018, "minutes": 15},
                "output": {
                    "population_reached": 125000,
                    "area_sqkm": 4.2,
                    "transit_stops": 12,
                },
                "duration": 1.0,
            },
        ]

    if (
        "business" in lower_msg
        or "site" in lower_msg
        or "ร้าน" in lower_msg
        or "ธุรกิจ" in lower_msg
    ):
        return [
            {
                "name": "analyze_site",
                "input": {
                    "latitude": 13.7563,
                    "longitude": 100.5018,
                    "target_category": "restaurant",
                },
                "output": {
                    "site_score": 78,
                    "competitors_count": 12,
                    "magnets_count": 8,
                    "traffic_potential": "High",
                },
                "duration": 1.8,
            },
        ]

    # Default: knowledge retrieval
    return [
        {
            "name": "retrieve_knowledge",
            "input": {"query": message},
            "output": {
                "documents": [
                    {"title": "Bangkok Real Estate Guide 2025", "relevance": 0.92},
                    {"title": "Price Prediction Methodology", "relevance": 0.85},
                ],
            },
            "duration": 0.6,
        },
    ]


def generate_mock_response(message: str, tools: list[dict]) -> str:
    """Generate contextual response based on message and tools used."""
    lower_msg = message.lower()

    if (
        "price" in lower_msg
        or "ราคา" in lower_msg
        or "หา" in lower_msg
        or "บ้าน" in lower_msg
    ):
        return """## Property Search Results

Based on my analysis of the market data, here are the properties I found:

| District | Style | Price | 
|----------|-------|-------|
| บางกะปิ | บ้านเดี่ยว | ฿4,500,000 |
| ลาดพร้าว | ทาวน์เฮ้าส์ | ฿5,200,000 |
| บางกะปิ | บ้านเดี่ยว | ฿3,800,000 |

### Market Statistics for บางกะปิ
- **Average Price:** ฿4.8M
- **Median Price:** ฿4.5M  
- **YoY Growth:** +5.2%
- **Total Listings:** 1,245

Would you like me to analyze specific properties or search with different criteria?"""

    if (
        "location" in lower_msg
        or "area" in lower_msg
        or "พื้นที่" in lower_msg
        or "ทำเล" in lower_msg
    ):
        return """## Location Intelligence Report

### Scores
| Metric | Score | Rating |
|--------|-------|--------|
| Transit | 85/100 | Excellent |
| Walkability | 72/100 | Good |
| Schools | 8 nearby | Good |
| Flood Risk | Low | Safe |

### Catchment Analysis (15-min walk)
- **Population Reached:** 125,000
- **Area Coverage:** 4.2 sq km
- **Transit Stops:** 12

This is a well-connected location suitable for both residential and commercial use."""

    if (
        "business" in lower_msg
        or "site" in lower_msg
        or "ร้าน" in lower_msg
        or "ธุรกิจ" in lower_msg
    ):
        return """## Site Analysis Results

### Overall Score: 78/100 - Good Potential

| Factor | Value |
|--------|-------|
| Competitors | 12 within 1km |
| Traffic Magnets | 8 nearby |
| Traffic Potential | High |

**Recommendation:** This location has good foot traffic from nearby transit and schools. Competition is moderate, suggesting market demand exists.

Would you like me to compare this with other potential sites?"""

    return """## Information Retrieved

Based on our knowledge base, here's what I found:

The Bangkok property market shows varied trends across districts:
- **Prime areas** (Sukhumvit, Sathorn): ฿10-15M+ 
- **Mid-range** (Chatuchak, Phra Khanong): ฿5-10M
- **Affordable** (Bang Kapi, Lat Phrao): ฿2.5-5M

Areas near new transit extensions typically show 10-15% appreciation potential.

What specific aspect would you like me to explore?"""


async def generate_mock_agent_stream_with_steps(messages: list[ChatMessage]):
    """Generate mock streaming response with structured tool steps (fallback mode)."""
    # Get the last user message
    user_message = ""
    for msg in reversed(messages):
        if msg.role == "user":
            user_message = msg.content
            break

    # Emit thinking event
    yield f"data: {json.dumps({'event': 'thinking', 'data': {'thinking': True}})}\n\n"
    await asyncio.sleep(0.8)

    # Get mock tools for this message
    tools = select_mock_tools(user_message)

    # Execute each tool with steps
    for i, tool in enumerate(tools):
        step_id = f"step-{int(time.time() * 1000)}-{i}"
        start_time = int(time.time() * 1000)

        # Emit running step
        step_running = {
            "id": step_id,
            "type": "tool_call",
            "name": tool["name"],
            "status": "running",
            "input": tool["input"],
            "start_time": start_time,
        }
        yield f"data: {json.dumps({'event': 'step', 'data': step_running})}\n\n"

        # Simulate execution time
        await asyncio.sleep(tool["duration"])

        # Emit completed step
        step_complete = {
            "id": step_id,
            "type": "tool_call",
            "name": tool["name"],
            "status": "complete",
            "input": tool["input"],
            "output": json.dumps(tool["output"], ensure_ascii=False),
            "start_time": start_time,
            "end_time": int(time.time() * 1000),
        }
        yield f"data: {json.dumps({'event': 'step', 'data': step_complete})}\n\n"

        # Brief pause between tools
        if i < len(tools) - 1:
            yield f"data: {json.dumps({'event': 'thinking', 'data': {'thinking': True}})}\n\n"
            await asyncio.sleep(0.4)

    # Stream final response
    yield f"data: {json.dumps({'event': 'thinking', 'data': {'thinking': False}})}\n\n"

    # Add mock mode warning
    response = (
        "[Mock Mode - Configure GOOGLE_API_KEY for real agent]\n\n"
        + generate_mock_response(user_message, tools)
    )

    for char in response:
        yield f"data: {json.dumps({'event': 'token', 'data': {'token': char}})}\n\n"
        await asyncio.sleep(0.012 + random.random() * 0.018)

    yield f"data: {json.dumps({'event': 'done', 'data': None})}\n\n"


async def generate_real_agent_stream_with_steps(
    messages: list[ChatMessage],
    session_id: str | None = None,
    attachments: list[AttachmentData] | None = None,
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
        session_id: Optional session ID for conversation memory
        attachments: Optional list of spatial attachments (bbox, location, property)
    """
    from src.services.agent_graph import agent_service
    from src.services.conversation_memory import conversation_memory

    # Convert messages to dict format
    message_dicts = [{"role": m.role, "content": m.content} for m in messages]

    # Build spatial context from attachments
    spatial_context = ""
    if attachments:
        spatial_context = build_spatial_context_message(attachments)

    # Inject spatial context into the last user message if present
    if spatial_context and message_dicts:
        # Find the last user message and append spatial context
        for i in range(len(message_dicts) - 1, -1, -1):
            if message_dicts[i]["role"] == "user":
                message_dicts[i]["content"] = (
                    message_dicts[i]["content"] + "\n\n" + spatial_context
                )
                break

    # Get conversation history if session exists
    if session_id:
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

    try:
        async for event in agent_service.astream(message_dicts):
            event_type = event.get("type", "")
            content = event.get("content", "")

            if event_type == "tool_call":
                # A new tool is being called
                tool_info = content
                current_tool_id = (
                    f"step-{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}"
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

            elif event_type == "error":
                # Handle errors
                if current_tool_id:
                    step_data = {
                        "id": current_tool_id,
                        "type": "tool_call",
                        "name": current_tool_name or "unknown",
                        "status": "error",
                        "output": str(content),
                        "end_time": int(time.time() * 1000),
                    }
                    yield f"data: {json.dumps({'event': 'step', 'data': step_data})}\n\n"

                yield f"data: {json.dumps({'event': 'thinking', 'data': {'thinking': False}})}\n\n"
                error_msg = f"\n\n**Error:** {content}"
                yield f"data: {json.dumps({'event': 'token', 'data': {'token': error_msg}})}\n\n"

        # Save assistant response to memory
        if session_id and response_content:
            conversation_memory.add_message(session_id, "assistant", response_content)

    except Exception as e:
        logger.error(f"Real agent stream error: {e}", exc_info=True)
        yield f"data: {json.dumps({'event': 'thinking', 'data': {'thinking': False}})}\n\n"
        error_msg = f"Sorry, I encountered an error: {str(e)}"
        yield f"data: {json.dumps({'event': 'token', 'data': {'token': error_msg}})}\n\n"

    # Emit done event
    yield f"data: {json.dumps({'event': 'done', 'data': None})}\n\n"


@router.post("/agent")
async def agent_chat(request: ChatRequest, response: Response):
    """
    Stream agent chat responses with structured tool steps.
    Returns Server-Sent Events (SSE) with JSON-formatted events.

    Event types:
    - thinking: Agent is processing {"thinking": true/false}
    - step: Tool call step {"id", "name", "status", "input", "output", "start_time", "end_time"}
    - token: Text token for response {"token": str}
    - done: Stream complete {null}

    Optional:
    - Pass session_id to maintain conversation context across requests.
    - Pass attachments for spatial context (bbox, location, property selections from map).
    """
    from src.services.conversation_memory import conversation_memory

    # Create or use session
    session_id = request.session_id
    if not session_id:
        session_id = conversation_memory.create_session()

    # Choose real agent or mock based on configuration
    if agent_settings.is_configured:
        logger.info(
            f"Using real agent for session {session_id} with {len(request.attachments or [])} attachments"
        )
        stream_generator = generate_real_agent_stream_with_steps(
            request.messages, session_id, request.attachments
        )
    else:
        logger.warning("Agent not configured, using mock stream")
        stream_generator = generate_mock_agent_stream_with_steps(request.messages)

    streaming_response = StreamingResponse(
        stream_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-ID": session_id,
        },
    )

    return streaming_response


@router.post("/sessions")
async def create_session():
    """Create a new conversation session."""
    from src.services.conversation_memory import conversation_memory

    session_id = conversation_memory.create_session()
    return {"session_id": session_id}


@router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str, limit: int = Query(20, le=100)):
    """Get conversation history for a session."""
    from src.services.conversation_memory import conversation_memory

    history = conversation_memory.get_history(session_id, limit=limit)
    return {"session_id": session_id, "messages": history}


@router.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    from src.services.conversation_memory import conversation_memory

    conversation_memory.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}
