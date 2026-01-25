"""Chat interface component."""

import streamlit as st

from src.agents.orchestrator import AgentOrchestrator
from src.llm.claude import PortfolioAssistant
from src.mcp.kite_client import AuthenticationError, KiteClient
from src.ui.utils.async_bridge import run_async
from src.ui.utils.session import SessionManager

# User-friendly messages for common API errors
API_ERROR_MESSAGES = {
    "overloaded_error": (
        "The AI service is currently experiencing high demand. "
        "Please try again in a few moments."
    ),
    "rate_limit_error": (
        "Too many requests. Please wait a moment before trying again."
    ),
    "api_error": (
        "There was a temporary issue connecting to the AI service. "
        "Please try again."
    ),
    "timed out": (
        "The request timed out. The service may be slow or unavailable. "
        "Please try again."
    ),
    "timeout": (
        "The request timed out. The service may be slow or unavailable. "
        "Please try again."
    ),
}


def _get_friendly_error_message(error: Exception) -> str:
    """Convert API errors to user-friendly messages.

    Args:
        error: The exception that occurred

    Returns:
        A user-friendly error message
    """
    error_str = str(error).lower()

    for error_type, message in API_ERROR_MESSAGES.items():
        if error_type in error_str:
            return message

    # Default message for unknown errors
    return f"An error occurred: {error}"


def render_chat(
    kite_client: KiteClient,
    assistant: PortfolioAssistant,
    orchestrator: AgentOrchestrator,
) -> None:
    """Render the chat interface.

    Args:
        kite_client: The Kite MCP client instance
        assistant: The PortfolioAssistant for regular chat
        orchestrator: The AgentOrchestrator for agent-based queries
    """
    # Display chat history
    _render_chat_history()

    # Check for pending prompt (from suggested prompts click)
    pending_prompt = SessionManager.get_pending_prompt()
    if pending_prompt:
        _process_query(pending_prompt, assistant, orchestrator)

    # Chat input
    user_input = st.chat_input("Ask about your portfolio...")
    if user_input:
        _process_query(user_input, assistant, orchestrator)


def _render_chat_history() -> None:
    """Render the chat message history."""
    history = SessionManager.get_chat_history()

    for message in history:
        with st.chat_message(message.role):
            st.markdown(message.content)
            if message.agent_used:
                st.caption(f"Handled by: {message.agent_used}")


def _process_query(
    query: str,
    assistant: PortfolioAssistant,
    orchestrator: AgentOrchestrator,
) -> None:
    """Process a user query through agents or regular chat.

    Args:
        query: The user's query
        assistant: The PortfolioAssistant for regular chat
        orchestrator: The AgentOrchestrator for agent queries
    """
    # Add user message to history and display
    SessionManager.add_message("user", query)
    with st.chat_message("user"):
        st.markdown(query)

    # Check if an agent should handle this
    should_use_agent, agent_type = orchestrator.should_use_agent(query)

    with st.chat_message("assistant"):
        if should_use_agent and agent_type:
            _handle_agent_query(query, agent_type, orchestrator)
        else:
            _handle_regular_chat(query, assistant)


def _handle_agent_query(
    query: str,
    agent_type: str,
    orchestrator: AgentOrchestrator,
) -> None:
    """Handle a query using an agent workflow.

    Args:
        query: The user's query
        agent_type: The type of agent to use
        orchestrator: The AgentOrchestrator
    """
    agent_name = agent_type.replace("_", " ").title()
    st.caption(f"Using {agent_name}...")

    try:
        with st.spinner(f"Running {agent_name}..."):
            result = run_async(orchestrator.run_agent(agent_type, query))

        response = result.get("response", "No response from agent.")
        agent_used = result.get("agent_used", agent_name)

        st.markdown(response)
        st.caption(f"Handled by: {agent_used}")

        SessionManager.add_message("assistant", response, agent_used)

    except AuthenticationError:
        error_msg = "Please login to Kite first to access your portfolio data."
        st.error(error_msg)
        SessionManager.add_message("assistant", error_msg)

    except Exception as e:
        error_msg = _get_friendly_error_message(e)
        st.error(error_msg)
        SessionManager.add_message("assistant", error_msg)


def _handle_regular_chat(query: str, assistant: PortfolioAssistant) -> None:
    """Handle a query using regular Claude chat.

    Args:
        query: The user's query
        assistant: The PortfolioAssistant
    """
    try:
        with st.spinner("Thinking..."):
            # Collect the full response
            response_text = ""

            async def collect_response() -> str:
                nonlocal response_text
                async for event in assistant.chat(query):
                    if event.type == "text":
                        response_text += event.text
                    elif event.type == "done":
                        break
                return response_text

            response_text = run_async(collect_response())

        st.markdown(response_text)
        SessionManager.add_message("assistant", response_text)

    except AuthenticationError:
        error_msg = "Please login to Kite first to access your portfolio data."
        st.error(error_msg)
        SessionManager.add_message("assistant", error_msg)

    except Exception as e:
        error_msg = _get_friendly_error_message(e)
        st.error(error_msg)
        SessionManager.add_message("assistant", error_msg)


def render_empty_chat_state() -> None:
    """Render the empty state when no chat history exists."""
    st.markdown(
        """
        ### Welcome to Portfolio Copilot!

        I can help you with:
        - **Portfolio Analysis**: Understand your holdings and performance
        - **Stock Research**: Get insights on specific stocks
        - **Market Context**: Learn why your portfolio moved
        - **Watchlist Suggestions**: Discover stocks to watch
        - **Fundamental Analysis**: Evaluate if a stock is worth buying

        **Get started** by clicking a suggestion below or typing your question!
        """
    )
