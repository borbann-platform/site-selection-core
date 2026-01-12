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
