"""
LangGraph agent orchestration.
Creates a ReAct agent with Gemini and tool calling capabilities.
"""

import logging
from collections.abc import AsyncIterator
from typing import Any, TypedDict, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from src.config.agent_settings import agent_settings
from src.services.agent_tools import ALL_TOOLS
from src.services.rag_service import retrieve_knowledge

logger = logging.getLogger(__name__)


# Enhanced system prompt for the agent with structured output guidelines
SYSTEM_PROMPT = """You are Borbann AI, an intelligent real estate assistant for Bangkok, Thailand.
You help users analyze properties, predict prices, evaluate locations, and understand the market.

## Your Capabilities
You have access to the following tools - USE THEM PROACTIVELY:

### Property Tools
- **search_properties**: Find properties matching criteria (district, style, price range)
  - Example: User asks "หาบ้านในบางกะปิ" → Use search_properties(district="บางกะปิ")
- **get_nearby_properties**: Find comparable properties near a specific location
- **get_market_statistics**: Get district-level market data (avg price, trends)

### Location Analysis Tools  
- **get_location_intelligence**: Get comprehensive scores (transit, walkability, schools, flood risk, noise)
- **analyze_site**: Evaluate business potential (competitors, magnets, traffic)
- **analyze_catchment**: Calculate reachable area and population within travel time

### Prediction & Knowledge Tools
- **predict_property_price**: Predict property value with feature explanations (NOTE: Currently mock data)
- **retrieve_knowledge**: Search documentation for background info about methodology

## Database Schema Reference
The property data comes from Thailand's Treasury Department (กรมธนารักษ์):

### Property Table: `house_prices`
| Column | Type | Description | Example Values |
|--------|------|-------------|----------------|
| id | int | Unique property ID | 1, 2, 3... |
| amphur | string | District (เขต) | บางกะปิ, สาทร, วัฒนา, ลาดพร้าว |
| tumbon | string | Sub-district (แขวง) | หัวหมาก, คลองเตย |
| building_style_desc | string | Property type | บ้านเดี่ยว, ทาวน์เฮ้าส์, บ้านแฝด, ตึกแถว |
| building_area | float | Building area (sqm) | 150.0, 200.5 |
| land_area | float | Land area (sq wah) | 50.0, 100.0 |
| building_age | float | Age in years | 5.0, 10.0 |
| no_of_floor | float | Number of floors | 1.0, 2.0, 3.0 |
| total_price | float | Price in THB | 3500000.0, 10000000.0 |
| geometry | geometry | PostGIS point | POINT(100.5 13.7) |

### Valid District Names (Thai)
บางกะปิ, วัฒนา, สาทร, ลาดพร้าว, พระโขนง, จตุจักร, บางนา, ห้วยขวาง, คลองเตย, 
บึงกุ่ม, ดินแดง, ราชเทวี, พญาไท, ปทุมวัน, บางรัก, สวนหลวง, คันนายาว, สะพานสูง,
มีนบุรี, หนองจอก, คลองสามวา, ลาดกระบัง, ประเวศ, บางขุนเทียน, ภาษีเจริญ, ตลิ่งชัน

### Valid Building Styles (Thai)
- **บ้านเดี่ยว** = Detached house (most common)
- **ทาวน์เฮ้าส์** = Townhouse
- **บ้านแฝด** = Semi-detached/twin house
- **ตึกแถว** = Shophouse
- **อาคารพาณิชย์** = Commercial building

### Price Ranges (THB)
- Budget: < 3,000,000 (< 3M)
- Mid-range: 3,000,000 - 10,000,000 (3M - 10M)
- Premium: 10,000,000 - 30,000,000 (10M - 30M)
- Luxury: > 30,000,000 (> 30M)

## Response Format Guidelines
Format your responses using **Rich Markdown** for readability:

### For Property Searches:
```
## Property Results

Found **X properties** matching your criteria:

| District | Style | Price | Area |
|----------|-------|-------|------|
| บางกะปิ | บ้านเดี่ยว | ฿4.5M | 150 sqm |

### Summary
- Average price: ฿X.XM
- Price range: ฿X.XM - ฿X.XM
```

### For Location Analysis:
```
## Location Intelligence Report

### Scores
| Metric | Score | Rating |
|--------|-------|--------|
| Transit | XX/100 | Good/Excellent |

### Key Findings
- Bullet point insights
```

### For Comparisons:
Use side-by-side tables when comparing districts or properties.

## Behavioral Guidelines
1. **BE PROACTIVE**: Always use tools to get real data before answering. Never give generic advice when you can look up actual data.
2. **Use Multiple Tools**: Chain tools together for comprehensive answers (e.g., search + market stats + location intelligence)
3. **Bilingual**: Respond in the same language the user uses (Thai or English)
4. **Currency**: Always format prices in Thai Baht (฿ or THB). Use M for millions (e.g., ฿5M = 5,000,000 THB)
5. **Be Specific**: Include actual numbers, percentages, and data points
6. **Explain Results**: After getting tool results, interpret them for the user

## Tool Parameter Guidelines
When using tools:
- **district**: Use Thai names exactly (e.g., "บางกะปิ" not "Bang Kapi")
- **building_style**: Use Thai names exactly (e.g., "บ้านเดี่ยว" not "detached house")
- **price**: Use numbers, not strings (e.g., 5000000 not "5M" or "5 million")
- **coordinates**: Bangkok area is approximately lat 13.5-14.0, lon 100.3-100.9

## Location Handling
- Bangkok coordinates: approximately lat 13.7, lon 100.5
- If user mentions a location name, try to find properties there first
- For coordinates, use them directly in tool calls

## Error Handling
- If a tool fails, explain what went wrong and suggest alternatives
- If data is limited, acknowledge it and provide what's available
- For areas outside Bangkok, explain your coverage is Bangkok-focused

## Examples of Good Responses

User: "หาบ้านราคาไม่เกิน 10 ล้าน"
→ Use search_properties(max_price=10000000)
→ Format results in a table with key details

User: "Find houses under 5 million in Bangkapi"
→ Use search_properties(district="บางกะปิ", max_price=5000000)
→ Then use get_market_statistics(district="บางกะปิ") for context
→ Format results in a table with market insights

User: "What's a good location for a coffee shop near BTS?"
→ Use analyze_site with a central BTS location
→ Use get_location_intelligence for foot traffic data
→ Provide specific recommendations with data

Remember: You're helping people make important decisions. Be accurate, specific, and data-driven.
"""


class AgentState(TypedDict):
    """State for the agent graph."""

    messages: list[BaseMessage]


class AgentService:
    """Service for running the LangGraph agent."""

    def __init__(self):
        self._agent = None
        self._llm = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of the agent."""
        if self._initialized:
            return

        if not agent_settings.is_configured:
            raise ValueError("Agent not configured. Set GOOGLE_API_KEY in .env file.")

        # Initialize Gemini LLM
        self._llm = ChatGoogleGenerativeAI(
            model=agent_settings.AGENT_MODEL,
            google_api_key=agent_settings.GOOGLE_API_KEY,
            temperature=0.7,
            max_output_tokens=agent_settings.AGENT_MAX_TOKENS_PER_TURN,
        )

        # Combine all tools including RAG retrieval
        tools = [*ALL_TOOLS, retrieve_knowledge]

        # Create ReAct agent with LangGraph
        self._agent = create_react_agent(
            model=self._llm,
            tools=tools,
            prompt=SYSTEM_PROMPT,
        )

        self._initialized = True
        logger.info(f"Agent initialized with model: {agent_settings.AGENT_MODEL}")

    def invoke(
        self,
        messages: list[dict[str, str]],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Run the agent synchronously.

        Args:
            messages: List of message dicts with 'role' and 'content'
            config: Optional config for the agent run

        Returns:
            Agent response with messages

        """
        self._ensure_initialized()
        if self._agent is None:
            raise RuntimeError("Agent not initialized")

        # Convert to LangChain messages
        lc_messages = self._convert_to_lc_messages(messages)

        # Build config
        run_config: RunnableConfig = {
            "recursion_limit": agent_settings.AGENT_MAX_ITERATIONS * 2 + 1,
            **(config or {}),
        }

        result = self._agent.invoke({"messages": lc_messages}, config=run_config)
        return result

    def _convert_to_lc_messages(
        self, messages: list[dict[str, str]]
    ) -> list[BaseMessage]:
        """Convert dict messages to LangChain message objects."""
        lc_messages: list[BaseMessage] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            elif role == "system":
                lc_messages.append(SystemMessage(content=content))
        return lc_messages

    async def astream(
        self,
        messages: list[dict[str, str]],
        config: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Stream agent execution events.

        Args:
            messages: List of message dicts with 'role' and 'content'
            config: Optional config for the agent run

        Yields:
            Event dicts with 'type' and 'content' keys:
            - type: "tool_call" | "tool_result" | "token" | "final" | "error"
            - content: varies by type

        """
        self._ensure_initialized()
        if self._agent is None:
            raise RuntimeError("Agent not initialized")

        # Convert to LangChain messages
        lc_messages = self._convert_to_lc_messages(messages)

        # Build config with type hint
        run_config: RunnableConfig = {
            "recursion_limit": agent_settings.AGENT_MAX_ITERATIONS * 2 + 1,
            **(config or {}),
        }

        iteration = 0
        max_iterations = agent_settings.AGENT_MAX_ITERATIONS

        try:
            async for event in self._agent.astream_events(
                {"messages": lc_messages},
                config=run_config,
                version="v2",
            ):
                event_type = event.get("event", "")
                event_name = event.get("name", "")
                data = event.get("data", {})

                # Track iterations to prevent infinite loops
                if event_type == "on_chain_start" and event_name == "tools":
                    iteration += 1
                    if iteration > max_iterations:
                        yield {
                            "type": "error",
                            "content": f"Max iterations ({max_iterations}) reached. Stopping.",
                        }
                        break

                # Stream tool calls
                if event_type == "on_tool_start":
                    tool_name = event_name
                    tool_input = data.get("input", {})

                    # Parse input if it's a string (sometimes happens)
                    if isinstance(tool_input, str):
                        try:
                            import json

                            tool_input = json.loads(tool_input)
                        except json.JSONDecodeError:
                            tool_input = {"raw_input": tool_input}

                    yield {
                        "type": "tool_call",
                        "content": {
                            "name": tool_name,
                            "input": tool_input,
                        },
                    }

                # Stream tool results
                elif event_type == "on_tool_end":
                    tool_output = data.get("output", "")
                    # Truncate very long outputs
                    output_str = str(tool_output)
                    if len(output_str) > 2000:
                        output_str = output_str[:2000] + "... (truncated)"

                    yield {
                        "type": "tool_result",
                        "content": output_str,
                    }

                # Stream LLM tokens
                elif event_type == "on_chat_model_stream":
                    chunk = data.get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield {
                            "type": "token",
                            "content": chunk.content,
                        }

                # Final response (backup - tokens should have streamed already)
                elif event_type == "on_chain_end" and event_name == "LangGraph":
                    output = data.get("output", {})
                    if isinstance(output, dict):
                        output_messages = output.get("messages", [])
                        if output_messages:
                            last_message = output_messages[-1]
                            if (
                                hasattr(last_message, "content")
                                and last_message.content
                            ):
                                yield {
                                    "type": "final",
                                    "content": last_message.content,
                                }

        except Exception as e:
            logger.error(f"Agent streaming error: {e}", exc_info=True)
            yield {
                "type": "error",
                "content": str(e),
            }

    async def astream_text(
        self,
        messages: list[dict[str, str]],
        include_tool_info: bool = False,
    ) -> AsyncIterator[str]:
        """
        Stream just the text content for simple SSE.

        Args:
            messages: List of message dicts
            include_tool_info: Whether to include tool call info in stream

        Yields:
            Text chunks for streaming

        """
        final_content = ""
        tokens_streamed = False

        async for event in self.astream(messages):
            event_type = event.get("type", "")
            content = event.get("content", "")

            if event_type == "token":
                tokens_streamed = True
                yield content
            elif event_type == "tool_call" and include_tool_info:
                tool_info = cast(dict, content)
                name = tool_info.get("name", "unknown")
                yield f"\n[Calling tool: {name}...]\n"
            elif event_type == "tool_result" and include_tool_info:
                yield f"\n[Tool completed]\n"
            elif event_type == "final":
                final_content = str(content)
            elif event_type == "error":
                yield f"\n[Error: {content}]\n"

        # If no tokens were streamed, yield the final content
        if not tokens_streamed and final_content:
            yield final_content


# Singleton instance
agent_service = AgentService()
