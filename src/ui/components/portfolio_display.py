"""Portfolio display component for showing holdings and metrics."""

import pandas as pd
import streamlit as st

from src.mcp.kite_client import KiteClient
from src.ui.utils.async_bridge import run_async
from src.ui.utils.session import SessionManager


def render_portfolio_summary(kite_client: KiteClient) -> None:
    """Render portfolio summary metrics in the sidebar.

    Args:
        kite_client: The Kite MCP client instance
    """
    if not SessionManager.is_logged_in():
        return

    st.subheader("Portfolio Summary")

    try:
        with st.spinner("Loading..."):
            holdings = run_async(kite_client.get_holdings())

        if not holdings:
            st.info("No holdings found")
            return

        # Calculate metrics
        total_value = sum(
            h.get("quantity", 0) * h.get("last_price", 0) for h in holdings
        )
        total_invested = sum(
            h.get("quantity", 0) * h.get("average_price", 0) for h in holdings
        )
        total_pnl = sum(h.get("pnl", 0) for h in holdings)
        pnl_percent = (total_pnl / total_invested * 100) if total_invested > 0 else 0

        # Display metrics
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Value", f"₹{total_value:,.0f}")
            st.metric("Invested", f"₹{total_invested:,.0f}")
        with col2:
            st.metric(
                "P&L",
                f"₹{total_pnl:,.0f}",
                delta=f"{pnl_percent:+.1f}%",
            )
            st.metric("Holdings", len(holdings))

        # Show top performers
        _render_top_performers(holdings)

    except Exception as e:
        st.error(f"Error loading portfolio: {e}")


def _render_top_performers(holdings: list[dict]) -> None:
    """Render top gaining and losing stocks.

    Args:
        holdings: List of holding dictionaries
    """
    if len(holdings) < 2:
        return

    # Sort by P&L percentage
    sorted_holdings = sorted(
        holdings,
        key=lambda h: h.get("day_change_percentage", 0),
        reverse=True,
    )

    st.markdown("---")
    st.caption("Today's Movers")

    # Top gainer
    top = sorted_holdings[0]
    change = top.get("day_change_percentage", 0)
    if change > 0:
        st.markdown(
            f"📈 **{top.get('tradingsymbol', 'N/A')}** "
            f":green[+{change:.1f}%]"
        )

    # Top loser
    bottom = sorted_holdings[-1]
    change = bottom.get("day_change_percentage", 0)
    if change < 0:
        st.markdown(
            f"📉 **{bottom.get('tradingsymbol', 'N/A')}** "
            f":red[{change:.1f}%]"
        )


def render_holdings_table(kite_client: KiteClient) -> None:
    """Render full holdings table in the main area.

    Args:
        kite_client: The Kite MCP client instance
    """
    if not SessionManager.is_logged_in():
        st.warning("Please login to view your holdings")
        return

    try:
        with st.spinner("Loading holdings..."):
            holdings = run_async(kite_client.get_holdings())

        if not holdings:
            st.info("No holdings found in your portfolio")
            return

        # Convert to DataFrame
        df = pd.DataFrame(holdings)

        # Select and rename columns
        display_cols = {
            "tradingsymbol": "Symbol",
            "quantity": "Qty",
            "average_price": "Avg Price",
            "last_price": "LTP",
            "pnl": "P&L",
            "day_change_percentage": "Change %",
        }

        # Filter to available columns
        available_cols = [c for c in display_cols.keys() if c in df.columns]
        df_display = df[available_cols].copy()
        df_display.columns = [display_cols[c] for c in available_cols]

        # Format numeric columns
        if "Avg Price" in df_display.columns:
            df_display["Avg Price"] = df_display["Avg Price"].apply(
                lambda x: f"₹{x:,.2f}"
            )
        if "LTP" in df_display.columns:
            df_display["LTP"] = df_display["LTP"].apply(lambda x: f"₹{x:,.2f}")
        if "P&L" in df_display.columns:
            df_display["P&L"] = df_display["P&L"].apply(lambda x: f"₹{x:,.2f}")
        if "Change %" in df_display.columns:
            df_display["Change %"] = df_display["Change %"].apply(
                lambda x: f"{x:+.2f}%"
            )

        st.dataframe(df_display, use_container_width=True, hide_index=True)

        # Summary row
        total_pnl = sum(h.get("pnl", 0) for h in holdings)
        total_value = sum(
            h.get("quantity", 0) * h.get("last_price", 0) for h in holdings
        )
        st.markdown(
            f"**Total Value:** ₹{total_value:,.2f} | "
            f"**Total P&L:** ₹{total_pnl:,.2f}"
        )

    except Exception as e:
        st.error(f"Error loading holdings: {e}")
