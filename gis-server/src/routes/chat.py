"""
Chat API endpoints.
Provides agentic chatbot with streaming responses using LangGraph + Gemini.
"""

import asyncio
import logging
import random

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from src.config.agent_settings import agent_settings

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


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
                yield f"data: \n[🔧 {name}]\n\n"

            elif event_type == "tool_result" and debug:
                # Include truncated tool result in debug mode
                truncated = content[:200] + "..." if len(content) > 200 else content
                yield f"data: \n[→ {truncated}]\n\n"

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

    if "price" in lower_msg or "ราคา" in lower_msg:
        return [
            {
                "name": "search_properties",
                "input": {"query": message, "limit": 5},
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

    if "location" in lower_msg or "area" in lower_msg or "พื้นที่" in lower_msg:
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
                    "hospitals_nearby": 3,
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

    if "business" in lower_msg or "site" in lower_msg or "ร้าน" in lower_msg:
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
                    "recommendation": "Good location for F&B business",
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
                    {"title": "District Analysis Report", "relevance": 0.78},
                ],
            },
            "duration": 0.6,
        },
    ]


def generate_mock_response(message: str, tools: list[dict]) -> str:
    """Generate contextual response based on message and tools used."""
    lower_msg = message.lower()

    if "price" in lower_msg or "ราคา" in lower_msg:
        return """Based on my analysis of the market data, the average property price in the บางกะปิ district is around **4.8 million THB**.

I found several comparable properties in the area:
- Properties range from 3.8M to 5.2M THB
- Year-over-year price growth is approximately 5.2%
- The median price sits at 4.5M THB

Would you like me to analyze a specific location or property type in more detail?"""

    if "location" in lower_msg or "area" in lower_msg or "พื้นที่" in lower_msg:
        return """Here's my analysis of this location:

**Transit Score: 85/100** - Excellent public transit access with BTS/MRT nearby
**Walkability: 72/100** - Good walkability with essential amenities within walking distance
**Flood Risk: Low** - This area has minimal flood concerns
**Schools: 8 nearby** - Good options for families

The 15-minute catchment area reaches approximately 125,000 people across 4.2 sq km.

This is a well-connected location suitable for residential or commercial purposes."""

    if "business" in lower_msg or "site" in lower_msg or "ร้าน" in lower_msg:
        return """**Site Analysis Results**

🎯 **Site Score: 78/100** - Good potential for business

**Competition:** 12 similar businesses within 1km
**Traffic Magnets:** 8 nearby (schools, transit stops, attractions)
**Traffic Potential:** High

This location has a healthy balance of foot traffic drivers while maintaining manageable competition. The proximity to transit and schools creates consistent daily traffic patterns.

Would you like me to compare this with other potential sites?"""

    return """I found some relevant information in our knowledge base. Based on the Bangkok real estate data we have:

The Bangkok property market shows varied trends across districts. Prime areas like Sukhumvit command premium prices (10-15M+ THB), while developing areas near new transit lines offer better value (3-6M THB) with strong appreciation potential.

What specific aspect would you like me to explore further?"""


async def generate_agent_stream_with_steps(messages: list[ChatMessage]):
    """Generate streaming response with structured tool steps."""
    import json
    import time

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

    response = generate_mock_response(user_message, tools)
    for char in response:
        yield f"data: {json.dumps({'event': 'token', 'data': {'token': char}})}\n\n"
        await asyncio.sleep(0.015 + random.random() * 0.025)

    yield f"data: {json.dumps({'event': 'done', 'data': None})}\n\n"


@router.post("/agent")
async def agent_chat(request: ChatRequest):
    """
    Stream agent chat responses with structured tool steps.
    Returns Server-Sent Events (SSE) with JSON-formatted events.

    Event types:
    - thinking: Agent is processing
    - step: Tool call step (running or complete)
    - token: Text token for response
    - done: Stream complete
    """
    return StreamingResponse(
        generate_agent_stream_with_steps(request.messages),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
