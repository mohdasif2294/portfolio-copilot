"""Login component for Kite OAuth flow."""

import streamlit as st

from src.mcp.kite_client import KiteClient
from src.ui.utils.async_bridge import run_async
from src.ui.utils.session import SessionManager


def render_login(kite_client: KiteClient) -> None:
    """Render the login component in the sidebar.

    Args:
        kite_client: The Kite MCP client instance
    """
    st.subheader("Account")

    if SessionManager.is_logged_in():
        # Show logged-in status
        profile = SessionManager.get_user_profile()
        if profile:
            st.success(f"Logged in as **{profile.user_name}**")
            st.caption(f"User ID: {profile.user_id}")
        else:
            st.success("Logged in")

        # Logout button
        if st.button("Logout", use_container_width=True):
            SessionManager.set_logged_in(False)
            st.rerun()
    else:
        # Show login flow
        login_url = SessionManager.get_login_url()

        if login_url:
            # Show the login URL
            st.info("Click the link below to login:")
            st.markdown(f"[Open Kite Login]({login_url})")
            st.caption("Complete login in the browser, then click 'Verify Login'")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Verify Login", use_container_width=True):
                    _verify_login(kite_client)
            with col2:
                if st.button("Cancel", use_container_width=True):
                    SessionManager.set_login_url(None)
                    st.rerun()
        else:
            # Show connect button
            st.warning("Not connected to Kite")
            if st.button("Connect to Kite", use_container_width=True, type="primary"):
                _initiate_login(kite_client)


def _initiate_login(kite_client: KiteClient) -> None:
    """Initiate the login flow."""
    with st.spinner("Getting login URL..."):
        try:
            result = run_async(kite_client.login())
            if result.url:
                SessionManager.set_login_url(result.url)
                st.rerun()
            else:
                st.error("Failed to get login URL")
        except Exception as e:
            st.error(f"Error: {e}")


def _verify_login(kite_client: KiteClient) -> None:
    """Verify that login was successful."""
    with st.spinner("Verifying login..."):
        try:
            logged_in = run_async(kite_client.is_logged_in())
            if logged_in:
                profile = run_async(kite_client.get_profile())
                kite_client.mark_logged_in()
                SessionManager.set_logged_in(True, profile)
                SessionManager.set_login_url(None)
                st.rerun()
            else:
                st.warning("Login not detected yet. Please complete login in browser.")
        except Exception as e:
            st.error(f"Verification error: {e}")


def check_initial_login_status(kite_client: KiteClient) -> None:
    """Check login status on app load (called once).

    Args:
        kite_client: The Kite MCP client instance
    """
    if SessionManager.is_checking_login():
        return

    SessionManager.set_checking_login(True)
    try:
        # Use shorter timeout for initial check to avoid blocking app load
        logged_in = run_async(kite_client.is_logged_in(), timeout=10.0)
        if logged_in:
            profile = run_async(kite_client.get_profile(), timeout=10.0)
            kite_client.mark_logged_in()
            SessionManager.set_logged_in(True, profile)
    except Exception:
        pass  # Silently fail on initial check
    finally:
        SessionManager.set_checking_login(False)
