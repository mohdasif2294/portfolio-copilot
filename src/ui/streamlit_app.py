#!/usr/bin/env python3
"""Streamlit web interface for Portfolio Copilot."""

import logging

import streamlit as st

from src.agents.orchestrator import AgentOrchestrator
from src.llm.claude import PortfolioAssistant
from src.mcp.kite_client import KiteClient
from src.ui.components.chat import render_chat, render_empty_chat_state
from src.ui.components.login import check_initial_login_status
from src.ui.components.sidebar import render_action_input_dialog, render_sidebar
from src.ui.components.suggested_prompts import render_suggested_prompts
from src.ui.utils.async_bridge import run_async
from src.ui.utils.session import SessionManager

# Page configuration
st.set_page_config(
    page_title="Portfolio Copilot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better appearance
st.markdown(
    """
    <style>
    /* Improve chat message styling */
    .stChatMessage {
        padding: 1rem;
        border-radius: 0.5rem;
    }

    /* Make buttons more consistent */
    .stButton > button {
        border-radius: 0.5rem;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

logger = logging.getLogger(__name__)


@st.cache_resource
def get_kite_client() -> KiteClient:
    """Get or create a cached KiteClient instance.

    Uses st.cache_resource to maintain a single connection across reruns.
    """
    client = KiteClient()
    # Connect the client with a timeout
    try:
        run_async(client.connect(), timeout=15.0)
    except TimeoutError:
        # Connection timed out, return client anyway (will retry on use)
        logger.exception("KiteClient.connect timed out")
    except Exception:
        # Connection failed, return client anyway (will retry on use)
        logger.exception("KiteClient.connect failed")
    return client


@st.cache_resource
def get_assistant(_kite_client: KiteClient) -> PortfolioAssistant:
    """Get or create a cached PortfolioAssistant instance.

    Args:
        _kite_client: The Kite client (underscore prefix for cache key)
    """
    return PortfolioAssistant(_kite_client)


@st.cache_resource
def get_orchestrator(_kite_client: KiteClient) -> AgentOrchestrator:
    """Get or create a cached AgentOrchestrator instance.

    Args:
        _kite_client: The Kite client (underscore prefix for cache key)
    """
    return AgentOrchestrator(_kite_client)


def main() -> None:
    """Main entry point for the Streamlit app."""
    # Initialize session state
    SessionManager.initialize()

    # Get cached instances
    kite_client = get_kite_client()
    assistant = get_assistant(kite_client)
    orchestrator = get_orchestrator(kite_client)

    # Check initial login status (only on first load)
    if "initial_login_checked" not in st.session_state:
        check_initial_login_status(kite_client)
        st.session_state.initial_login_checked = True

    # Render sidebar
    render_sidebar(kite_client)

    # Main content area
    _render_main_content(kite_client, assistant, orchestrator)


def _render_main_content(
    kite_client: KiteClient,
    assistant: PortfolioAssistant,
    orchestrator: AgentOrchestrator,
) -> None:
    """Render the main content area.

    Args:
        kite_client: The Kite MCP client
        assistant: The PortfolioAssistant
        orchestrator: The AgentOrchestrator
    """
    # Check if there's a pending action that needs input
    if st.session_state.get("pending_action"):
        render_action_input_dialog()
        return

    # Get chat history
    chat_history = SessionManager.get_chat_history()

    # Check for pending prompt first (from suggested prompts or empty state input)
    pending_prompt = SessionManager.get_pending_prompt()

    if not chat_history and not pending_prompt:
        # Show welcome message and suggestions for empty chat
        render_empty_chat_state()
        st.markdown("---")
        render_suggested_prompts()

        # Chat input for empty state
        user_input = st.chat_input("Ask about your portfolio...")
        if user_input:
            SessionManager.set_pending_prompt(user_input)
            st.rerun()
    else:
        # If we have a pending prompt, set it back for render_chat to process
        if pending_prompt:
            SessionManager.set_pending_prompt(pending_prompt)
        # Render chat interface (handles both history display and new queries)
        render_chat(kite_client, assistant, orchestrator)


if __name__ == "__main__":
    main()
