"""
LangGraph agent orchestration.
Creates a ReAct agent with Gemini and tool calling capabilities.
"""

import logging
from collections.abc import AsyncIterator
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from src.config.agent_settings import agent_settings
from src.services.agent_tools import ALL_TOOLS
from src.services.rag_service import retrieve_knowledge

logger = logging.getLogger(__name__)


# System prompt for the agent
SYSTEM_PROMPT = """You are an intelligent real estate assistant for Bangkok, Thailand.
You help users analyze properties, predict prices, evaluate locations, and understand the market.

## Your Capabilities
You have access to the following tools:
- **analyze_site**: Evaluate business potential of a location (competitors, magnets, traffic)
- **get_location_intelligence**: Get comprehensive scores (transit, walkability, schools, flood risk)
- **predict_property_price**: Predict property value with SHAP-based explanations
- **search_properties**: Find properties matching criteria
- **get_nearby_properties**: Find comparable properties near a location
- **get_market_statistics**: Get district-level market data
- **analyze_catchment**: Calculate reachable area and population
- **retrieve_knowledge**: Search documentation for background info

## Guidelines
1. **Be proactive**: Use tools to gather data before answering questions about locations or prices
2. **Be specific**: When asked about a location, use tools to get actual data rather than giving generic advice
3. **Explain your reasoning**: After getting tool results, interpret them for the user
4. **Handle Thai and English**: Respond in the same language the user uses
5. **Currency**: All prices are in Thai Baht (THB)
6. **Location format**: Use latitude/longitude for tool calls. Bangkok is around lat 13.7, lon 100.5

## Error Handling
- If a tool fails, explain what went wrong and suggest alternatives
- If asked about areas outside Bangkok, explain that your data coverage is limited to Bangkok

Remember: You're helping people make important real estate decisions. Be accurate and helpful.
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
        # Using in-memory checkpointer for conversation state
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
        lc_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            elif role == "system":
                lc_messages.append(SystemMessage(content=content))

        # Run agent with iteration limit
        config = config or {}
        config["recursion_limit"] = agent_settings.AGENT_MAX_ITERATIONS * 2 + 1

        result = self._agent.invoke({"messages": lc_messages}, config=config)
        return result

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
            Event dicts with 'type' and 'content' keys

        """
        self._ensure_initialized()
        if self._agent is None:
            raise RuntimeError("Agent not initialized")

        # Convert to LangChain messages
        lc_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))

        # Run agent with streaming
        config = config or {}
        config["recursion_limit"] = agent_settings.AGENT_MAX_ITERATIONS * 2 + 1

        iteration = 0
        max_iterations = agent_settings.AGENT_MAX_ITERATIONS

        async for event in self._agent.astream_events(
            {"messages": lc_messages},
            config=config,
            version="v2",
        ):
            event_type = event.get("event", "")
            event_name = event.get("name", "")
            data = event.get("data", {})

            # Track iterations
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
                yield {
                    "type": "tool_result",
                    "content": str(tool_output)[:500],  # Truncate long outputs
                }

            # Stream LLM tokens
            elif event_type == "on_chat_model_stream":
                chunk = data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield {
                        "type": "token",
                        "content": chunk.content,
                    }

            # Final response
            elif event_type == "on_chain_end" and event_name == "LangGraph":
                output = data.get("output", {})
                messages = output.get("messages", [])
                if messages:
                    last_message = messages[-1]
                    if hasattr(last_message, "content"):
                        yield {
                            "type": "final",
                            "content": last_message.content,
                        }

    async def astream_text(
        self,
        messages: list[dict[str, str]],
        include_tool_info: bool = False,
    ) -> AsyncIterator[str]:
        """
        Stream just the text content for SSE.

        Args:
            messages: List of message dicts
            include_tool_info: Whether to include tool call info in stream

        Yields:
            Text chunks for streaming

        """
        final_content = ""

        async for event in self.astream(messages):
            event_type = event.get("type", "")
            content = event.get("content", "")

            if event_type == "token":
                yield content
            elif event_type == "tool_call" and include_tool_info:
                tool_info = content
                name = tool_info.get("name", "unknown")
                yield f"\n[Calling tool: {name}...]\n"
            elif event_type == "final":
                # Don't yield final again if we already streamed tokens
                final_content = content
            elif event_type == "error":
                yield f"\n[Error: {content}]\n"

        # If no tokens were streamed, yield the final content
        if final_content and not any(c for c in final_content if c):
            yield final_content


# Singleton instance
agent_service = AgentService()
