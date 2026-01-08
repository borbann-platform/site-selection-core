"""
Chat API endpoints.
Provides agentic chatbot with streaming responses.
"""

import asyncio
import random

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


# Mock responses for POC - will be replaced with real LLM integration
MOCK_RESPONSES = [
    "Based on the current market data, properties in this area have seen a 5% increase in value over the past year.",
    "The average price per square meter in Bangkok is around 80,000-120,000 THB, depending on the district.",
    "I can help you analyze property prices. What specific area or property type are you interested in?",
    "Looking at the data, บางกะปิ district has affordable options with good public transit access.",
    "For investment purposes, areas near new BTS extensions typically show strong appreciation.",
    "The price you mentioned seems reasonable for that location. Would you like me to find comparable properties?",
]


async def generate_mock_stream(user_message: str):
    """Generate mock streaming response, simulating LLM behavior."""
    # Pick a contextual response based on keywords, or random
    response = random.choice(MOCK_RESPONSES)

    if "price" in user_message.lower():
        response = "Based on our database, the average house price in Bangkok is around 4.5 million THB. Prices vary significantly by district - from 2M in outer areas to 15M+ in prime locations like Sukhumvit."
    elif "predict" in user_message.lower() or "forecast" in user_message.lower():
        response = "Our price prediction model suggests that properties in developing areas near new transit lines could see 10-15% appreciation over the next 2 years. Would you like me to analyze a specific location?"
    elif "recommend" in user_message.lower() or "suggest" in user_message.lower():
        response = "Based on your criteria, I'd recommend looking at properties in Lat Phrao or Bang Kapi districts. They offer good value with improving infrastructure and are well-connected to the city center."

    # Stream the response word by word
    words = response.split()
    for i, word in enumerate(words):
        # Add space before word (except first)
        chunk = f" {word}" if i > 0 else word
        yield f"data: {chunk}\n\n"
        # Simulate typing delay
        await asyncio.sleep(random.uniform(0.03, 0.08))

    yield "data: [DONE]\n\n"


@router.post("")
async def chat(request: ChatRequest):
    """
    Stream chat responses from the AI agent.
    Returns Server-Sent Events (SSE) stream.
    """
    # Get the last user message
    user_message = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_message = msg.content
            break

    return StreamingResponse(
        generate_mock_stream(user_message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
