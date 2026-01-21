"""
LangGraph agent orchestration.
Creates a Plan-and-Execute agent with Gemini for chain-of-thought reasoning.
"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any, TypedDict, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from src.config.agent_settings import agent_settings
from src.services.agent_tools import ALL_TOOLS
from src.services.rag_service import retrieve_knowledge

logger = logging.getLogger(__name__)


# Planning prompt for the planner node
PLANNING_PROMPT = """You are a strategic planner for a real estate AI assistant. Your job is to analyze user queries and create detailed, step-by-step execution plans.

Given a user query, think through what information is needed and which tools should be used in what order.

## Available Tools:
1. **search_properties** - Find properties by district, style, price range, or bounding box
2. **get_nearby_properties** - Find comparable properties near a location
3. **get_market_statistics** - Get district-level market statistics
4. **get_location_intelligence** - Analyze location quality (transit, schools, flood risk, etc.)
5. **analyze_site** - Evaluate business site potential
6. **analyze_catchment** - Calculate population reach within travel time
7. **predict_property_price** - Predict property value with ML model
8. **retrieve_knowledge** - Search knowledge base for methodology info

## Planning Guidelines:

### For "undervalued properties near X" queries:
1. First understand what "undervalued" means (predicted price > actual price)
2. Search for POIs of type X (e.g., international schools)
3. For each POI, search properties within radius
4. Predict prices for found properties
5. Filter for properties where actual_price < predicted_price
6. Rank by discount percentage

### For comparison queries:
1. Identify what to compare (districts, locations, properties)
2. Gather data for each item (search_properties, get_market_statistics)
3. Get additional context if needed (location_intelligence)
4. Compare metrics side by side

### For location evaluation:
1. Get location_intelligence for the coordinates
2. Get market_statistics for the district
3. Get nearby_properties for price context
4. Synthesize comprehensive analysis

## Output Format:
Return a JSON plan with these fields:
{
  "reasoning": "Step-by-step thought process explaining why this plan makes sense",
  "steps": [
    {
      "step": 1,
      "action": "tool_name",
      "parameters": {...},
      "purpose": "Why this step is needed"
    }
  ],
  "expected_outcome": "What the final answer should contain"
}

Be thorough but efficient. Chain multiple tools when needed for complex queries."""

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
2. **THINK STEP-BY-STEP**: For complex queries, break down your reasoning:
   - What is the user really asking?
   - What data do I need to answer this?
   - In what order should I gather this data?
   - How should I synthesize the results?
3. **Use Multiple Tools**: Chain tools together for comprehensive answers (e.g., search + market stats + location intelligence)
4. **Follow the Plan**: If an execution plan is provided in [EXECUTION PLAN], follow it step by step
5. **Bilingual**: Respond in the same language the user uses (Thai or English)
6. **Currency**: Always format prices in Thai Baht (฿ or THB). Use M for millions (e.g., ฿5M = 5,000,000 THB)
7. **Be Specific**: Include actual numbers, percentages, and data points
8. **Explain Results**: After getting tool results, interpret them for the user

## Chain-of-Thought Reasoning
For complex queries like "Show me undervalued homes near international schools":

**Step 1: Understand the query**
- "Undervalued" means: actual price < predicted/market price
- "Near international schools" means: within walkable distance (500m-2km)

**Step 2: Plan the approach**
1. Search for international schools POIs
2. For each school area, search properties within radius
3. For each property, predict market value
4. Filter properties where actual_price < predicted_price
5. Rank by discount percentage

**Step 3: Execute systematically**
Use tools in logical order, explaining each step

**Step 4: Synthesize results**
Present findings in clear tables with insights

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

## Spatial Context from Map Selections
The user may provide SPATIAL CONTEXT from map interactions. When present, this context appears at the end of their message:

### PIN LOCATION
When the user has placed a pin on the map:
- You'll receive: `latitude=X, longitude=Y`
- Use these exact coordinates for tools like `analyze_site`, `get_location_intelligence`, `analyze_catchment`, `get_nearby_properties`
- When user says "this location", "here", "at this point" → use the PIN coordinates

### BOUNDING BOX AREA
When the user has drawn an area on the map:
- You'll receive: `west=minLon, south=minLat, east=maxLon, north=maxLat`
- You'll also receive center coordinates and polygon corners
- Use the bbox bounds with `search_properties` tool using `min_lat`, `max_lat`, `min_lon`, `max_lon` parameters
- When user says "this area", "in this region", "within this box" → use the BBOX bounds
- For single-point analysis, use the CENTER of the bbox

### Example Usage:
1. User draws bbox + asks "หาบ้านในพื้นที่นี้" (find houses in this area)
   → Use search_properties with min_lat, max_lat, min_lon, max_lon from the bbox

2. User pins location + asks "วิเคราะห์ทำเลนี้" (analyze this location)
   → Use get_location_intelligence and analyze_site with the pin coordinates

3. User draws bbox + asks "What's the average price here?"
   → Use search_properties with bbox to get properties, calculate average

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
    """State for the planning agent graph."""

    messages: list[BaseMessage]
    plan: str | None  # The execution plan from the planner
    next_step: str  # What to do next: "plan", "execute", or "respond"


class AgentService:
    """Service for running the Plan-and-Execute LangGraph agent."""

    def __init__(self):
        self._agent = None
        self._llm = None
        self._planner_llm = None
        self._initialized = False
        self._use_planning = True  # Flag to enable/disable planning mode

    def _create_plan(self, state: AgentState) -> AgentState:
        """
        Planning node: Analyze the query and create an execution plan.
        """
        messages = state["messages"]

        # Get the last user message
        user_message = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_message = msg.content
                break

        if not user_message:
            state["plan"] = None
            state["next_step"] = "execute"
            return state

        # Check if this is a simple query that doesn't need planning
        simple_keywords = ["hello", "hi", "help", "what can you do", "สวัสดี"]
        if any(kw in user_message.lower() for kw in simple_keywords):
            state["plan"] = None
            state["next_step"] = "execute"
            return state

        # Create planning prompt
        planning_messages = [
            SystemMessage(content=PLANNING_PROMPT),
            HumanMessage(
                content=f"Create a detailed execution plan for this query:\n\n{user_message}"
            ),
        ]

        try:
            # Use a higher temperature for creative planning
            response = self._planner_llm.invoke(planning_messages)
            plan_text = (
                response.content if hasattr(response, "content") else str(response)
            )

            logger.info(f"Generated plan: {plan_text[:200]}...")
            state["plan"] = plan_text
            state["next_step"] = "execute"
        except Exception as e:
            logger.warning(f"Planning failed, falling back to direct execution: {e}")
            state["plan"] = None
            state["next_step"] = "execute"

        return state

    def _should_use_planning(self, messages: list[BaseMessage]) -> bool:
        """
        Determine if the query is complex enough to benefit from planning.
        """
        if not self._use_planning:
            return False

        # Get the last user message
        user_message = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_message = msg.content.lower()
                break

        # Complex query indicators
        complex_indicators = [
            "undervalued",
            "compare",
            "best",
            "recommend",
            "near",
            "analysis",
            "potential",
            "investment",
            "schools",
            "international",
            "ราคาต่ำกว่า",  # lower price than
            "เปรียบเทียบ",  # compare
        ]

        return any(indicator in user_message for indicator in complex_indicators)

    def _ensure_initialized(self):
        """Lazy initialization of the agent."""
        if self._initialized:
            return

        if not agent_settings.is_configured:
            raise ValueError("Agent not configured. Set GOOGLE_API_KEY in .env file.")

        # Initialize Gemini LLM for execution
        self._llm = ChatGoogleGenerativeAI(
            model=agent_settings.AGENT_MODEL,
            google_api_key=agent_settings.GOOGLE_API_KEY,
            temperature=0.7,
            max_output_tokens=agent_settings.AGENT_MAX_TOKENS_PER_TURN,
        )

        # Initialize planner LLM with higher temperature for creative planning
        self._planner_llm = ChatGoogleGenerativeAI(
            model=agent_settings.AGENT_MODEL,
            google_api_key=agent_settings.GOOGLE_API_KEY,
            temperature=0.9,  # Higher for creative planning
            max_output_tokens=2048,
        )

        # Combine all tools including RAG retrieval
        tools = [*ALL_TOOLS, retrieve_knowledge]

        # Create ReAct agent with LangGraph (for execution phase)
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
        Stream agent execution events with optional planning phase.

        Args:
            messages: List of message dicts with 'role' and 'content'
            config: Optional config for the agent run

        Yields:
            Event dicts with 'type' and 'content' keys:
            - type: "planning" | "tool_call" | "tool_result" | "token" | "final" | "error"
            - content: varies by type

        """
        self._ensure_initialized()
        if self._agent is None:
            raise RuntimeError("Agent not initialized")

        # Convert to LangChain messages
        lc_messages = self._convert_to_lc_messages(messages)

        # Check if we should use planning for this query
        use_planning = self._should_use_planning(lc_messages)

        # Planning phase (if complex query)
        plan_text = None
        if use_planning:
            try:
                logger.info("Complex query detected, creating execution plan...")

                # Emit planning start event
                yield {
                    "type": "planning",
                    "content": "Analyzing query and creating execution plan...",
                }

                # Create plan
                state = AgentState(messages=lc_messages, plan=None, next_step="plan")
                state = self._create_plan(state)
                plan_text = state.get("plan")

                if plan_text:
                    logger.info(f"Plan created: {plan_text[:100]}...")
                    # Emit the plan to the user
                    yield {
                        "type": "planning",
                        "content": f"Plan: {plan_text}",
                    }

                    # Prepend the plan to messages to guide execution
                    planning_context = HumanMessage(
                        content=f"[EXECUTION PLAN]\n{plan_text}\n\n[USER QUERY]\n{lc_messages[-1].content}"
                    )
                    # Replace last user message with planning-enhanced version
                    lc_messages = lc_messages[:-1] + [planning_context]

            except Exception as e:
                logger.warning(f"Planning failed: {e}")
                yield {
                    "type": "planning",
                    "content": "Planning skipped, proceeding with direct execution.",
                }

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
