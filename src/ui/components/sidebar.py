"""Sidebar component combining login, actions, and portfolio summary."""

import streamlit as st

from src.mcp.kite_client import KiteClient
from src.ui.components.login import render_login
from src.ui.components.portfolio_display import render_portfolio_summary
from src.ui.utils.session import SessionManager


# Quick action definitions with their agent types
QUICK_ACTIONS = [
    {
        "label": "Analyze Portfolio",
        "icon": "📊",
        "agent": "portfolio_analysis",
        "prompt": "Analyze my portfolio and show my best and worst performers",
    },
    {
        "label": "Research Stock",
        "icon": "🔍",
        "agent": "stock_research",
        "prompt": None,  # Will prompt user for stock name
    },
    {
        "label": "Market Context",
        "icon": "📰",
        "agent": "market_context",
        "prompt": "Why did my portfolio move today?",
    },
    {
        "label": "Watchlist Ideas",
        "icon": "📋",
        "agent": "watchlist",
        "prompt": "Suggest stocks for my watchlist based on my current portfolio",
    },
    {
        "label": "Check Fundamentals",
        "icon": "📈",
        "agent": "fundamental_analysis",
        "prompt": None,  # Will prompt user for stock name
    },
]


def render_sidebar(kite_client: KiteClient) -> None:
    """Render the complete sidebar.

    Args:
        kite_client: The Kite MCP client instance
    """
    with st.sidebar:
        # App title - use markdown for better theme compatibility
        st.markdown("## 📈 Portfolio Copilot")
        st.markdown("*AI-powered portfolio analysis*")

        st.markdown("---")

        # Login section
        render_login(kite_client)

        st.markdown("---")

        # Quick actions section
        _render_quick_actions()

        # Portfolio summary (only when logged in)
        if SessionManager.is_logged_in():
            st.markdown("---")
            render_portfolio_summary(kite_client)

        # Footer
        st.markdown("---")
        _render_footer()


def _render_quick_actions() -> None:
    """Render quick action buttons."""
    st.subheader("Quick Actions")

    for action in QUICK_ACTIONS:
        button_label = f"{action['icon']} {action['label']}"

        if st.button(button_label, key=f"action_{action['agent']}", use_container_width=True):
            if action["prompt"]:
                # Direct prompt - set it as pending
                SessionManager.set_pending_prompt(action["prompt"])
                st.rerun()
            else:
                # Need user input - show input dialog
                _handle_action_with_input(action)


def _handle_action_with_input(action: dict) -> None:
    """Handle an action that requires user input.

    Args:
        action: The action definition dictionary
    """
    # Store the action type in session state for the dialog
    if "pending_action" not in st.session_state:
        st.session_state.pending_action = None

    st.session_state.pending_action = action["agent"]


def render_action_input_dialog() -> None:
    """Render input dialog for actions that need user input.

    This should be called in the main area, not the sidebar.
    """
    pending_action = st.session_state.get("pending_action")

    if pending_action == "stock_research":
        st.markdown("### Research a Stock")
        stock_name = st.text_input(
            "Enter stock name or symbol:",
            placeholder="e.g., Reliance, TCS, INFY",
            key="research_input",
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Research", type="primary") and stock_name:
                SessionManager.set_pending_prompt(f"Tell me about {stock_name}")
                st.session_state.pending_action = None
                st.rerun()
        with col2:
            if st.button("Cancel"):
                st.session_state.pending_action = None
                st.rerun()

    elif pending_action == "fundamental_analysis":
        st.markdown("### Fundamental Analysis")
        stock_name = st.text_input(
            "Enter stock name or symbol:",
            placeholder="e.g., Reliance, TCS, INFY",
            key="fundamental_input",
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Analyze", type="primary") and stock_name:
                SessionManager.set_pending_prompt(f"Is {stock_name} a good buy?")
                st.session_state.pending_action = None
                st.rerun()
        with col2:
            if st.button("Cancel"):
                st.session_state.pending_action = None
                st.rerun()


def _render_footer() -> None:
    """Render sidebar footer with help and info."""
    st.caption("Need help?")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Clear Chat", use_container_width=True):
            SessionManager.clear_chat_history()
            st.rerun()
    with col2:
        if st.button("About", use_container_width=True):
            st.session_state.show_about = True

    # About dialog
    if st.session_state.get("show_about"):
        st.info(
            """
            **Portfolio Copilot** is an AI-powered tool for analyzing
            your Zerodha Kite portfolio.

            Built with Claude AI, MCP, and RAG.

            This is a learning project - not financial advice!
            """
        )
        if st.button("Close"):
            st.session_state.show_about = False
            st.rerun()
