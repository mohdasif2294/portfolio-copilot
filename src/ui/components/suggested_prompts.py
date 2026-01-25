"""Suggested prompts component with clickable chips."""

import streamlit as st

from src.ui.utils.session import SessionManager

# Suggested prompts organized by category
SUGGESTED_PROMPTS = {
    "Portfolio": [
        "Analyze my worst performing stocks",
        "Show my portfolio performance",
        "What is my total P&L?",
        "Which stock has the highest return?",
    ],
    "Research": [
        "Tell me about Reliance",
        "What's happening with TCS?",
        "Research HDFC Bank",
        "News on Infosys",
    ],
    "Market": [
        "Why is my portfolio down today?",
        "What happened to the market?",
        "Explain today's market movement",
    ],
    "Watchlist": [
        "Suggest stocks for my watchlist",
        "What stocks should I watch?",
        "Recommend stocks to buy",
    ],
    "Fundamentals": [
        "Is Reliance a good buy?",
        "Fundamentals of TCS",
        "Should I buy HDFC Bank?",
    ],
}


def render_suggested_prompts() -> None:
    """Render suggested prompts as clickable chips.

    When a prompt is clicked, it sets the pending prompt in session state.
    """
    st.markdown("**Try asking:**")

    # Create a more compact display using columns
    cols = st.columns(len(SUGGESTED_PROMPTS))

    for idx, (category, prompts) in enumerate(SUGGESTED_PROMPTS.items()):
        with cols[idx]:
            st.caption(category)
            # Show first 2 prompts per category to keep it compact
            for prompt in prompts[:2]:
                # Use a unique key for each button
                key = f"prompt_{category}_{prompts.index(prompt)}"
                if st.button(
                    prompt[:30] + "..." if len(prompt) > 30 else prompt,
                    key=key,
                    help=prompt,
                    use_container_width=True,
                ):
                    SessionManager.set_pending_prompt(prompt)
                    st.rerun()


def render_suggested_prompts_compact() -> None:
    """Render a compact version of suggested prompts.

    Shows a subset of prompts in a single row.
    """
    # Select representative prompts from different categories
    sample_prompts = [
        "Analyze my portfolio",
        "Tell me about Reliance",
        "Why is my portfolio down?",
        "Suggest watchlist stocks",
    ]

    cols = st.columns(len(sample_prompts))
    for idx, prompt in enumerate(sample_prompts):
        with cols[idx]:
            if st.button(prompt, key=f"sample_{idx}", use_container_width=True):
                SessionManager.set_pending_prompt(prompt)
                st.rerun()
