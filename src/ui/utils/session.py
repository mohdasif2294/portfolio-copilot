"""Session state management for Streamlit."""

from dataclasses import dataclass, field
from typing import Any

import streamlit as st


@dataclass
class ChatMessage:
    """A chat message in the conversation history."""

    role: str  # "user" or "assistant"
    content: str
    agent_used: str | None = None  # Which agent handled this, if any
    metadata: dict[str, Any] | None = None  # Extra data (e.g. events list)


@dataclass
class UserProfile:
    """User profile information from Kite."""

    user_id: str = ""
    user_name: str = ""
    email: str = ""
    broker: str = ""


@dataclass
class SessionState:
    """Container for all session state."""

    logged_in: bool = False
    user_profile: UserProfile | None = None
    chat_history: list[ChatMessage] = field(default_factory=list)
    pending_prompt: str | None = None  # For suggested prompt clicks


class SessionManager:
    """Manages Streamlit session state."""

    @staticmethod
    def initialize() -> None:
        """Initialize session state with defaults if not already set."""
        if "initialized" not in st.session_state:
            st.session_state.initialized = True
            st.session_state.logged_in = False
            st.session_state.user_profile = None
            st.session_state.chat_history = []
            st.session_state.pending_prompt = None
            st.session_state.login_url = None
            st.session_state.checking_login = False

    @staticmethod
    def is_logged_in() -> bool:
        """Check if user is logged in."""
        return st.session_state.get("logged_in", False)

    @staticmethod
    def set_logged_in(logged_in: bool, profile: dict[str, Any] | None = None) -> None:
        """Set login status and user profile."""
        st.session_state.logged_in = logged_in
        if profile:
            st.session_state.user_profile = UserProfile(
                user_id=profile.get("user_id", ""),
                user_name=profile.get("user_name", ""),
                email=profile.get("email", ""),
                broker=profile.get("broker", ""),
            )
        elif not logged_in:
            st.session_state.user_profile = None

    @staticmethod
    def get_user_profile() -> UserProfile | None:
        """Get the current user profile."""
        return st.session_state.get("user_profile")

    @staticmethod
    def get_chat_history() -> list[ChatMessage]:
        """Get chat history."""
        return st.session_state.get("chat_history", [])

    @staticmethod
    def add_message(
        role: str,
        content: str,
        agent_used: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a message to chat history."""
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
        st.session_state.chat_history.append(
            ChatMessage(role=role, content=content, agent_used=agent_used, metadata=metadata)
        )

    @staticmethod
    def clear_chat_history() -> None:
        """Clear the chat history."""
        st.session_state.chat_history = []

    @staticmethod
    def set_pending_prompt(prompt: str | None) -> None:
        """Set a pending prompt to be processed."""
        st.session_state.pending_prompt = prompt

    @staticmethod
    def get_pending_prompt() -> str | None:
        """Get and clear the pending prompt."""
        prompt = st.session_state.get("pending_prompt")
        st.session_state.pending_prompt = None
        return prompt

    @staticmethod
    def set_login_url(url: str | None) -> None:
        """Set the login URL."""
        st.session_state.login_url = url

    @staticmethod
    def get_login_url() -> str | None:
        """Get the login URL."""
        return st.session_state.get("login_url")

    @staticmethod
    def set_checking_login(checking: bool) -> None:
        """Set whether we're checking login status."""
        st.session_state.checking_login = checking

    @staticmethod
    def is_checking_login() -> bool:
        """Check if we're currently checking login status."""
        return st.session_state.get("checking_login", False)
