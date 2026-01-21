"""Portfolio Analysis Agent workflow using LangGraph."""

import os
from typing import Annotated, Any

from anthropic import Anthropic
from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from src.agents.state import PortfolioAnalysisState
from src.agents.tools.news_tools import (
    ensure_news_indexed,
    get_news_context_string,
    search_stock_news,
)
from src.agents.tools.portfolio_tools import analyze_performers, fetch_holdings
from src.mcp.kite_client import KiteClient

load_dotenv()

# LLM for generating insights
MODEL = "claude-sonnet-4-20250514"


def _get_anthropic() -> Anthropic:
    """Get Anthropic client."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    return Anthropic(api_key=api_key)


# Node functions for the workflow


async def fetch_portfolio_node(
    state: dict[str, Any],
    config: RunnableConfig,
) -> dict[str, Any]:
    """Node: Fetch portfolio holdings."""
    client: KiteClient = config["configurable"]["kite_client"]

    result = await fetch_holdings(client)

    if result["error"]:
        return {
            "error": result["error"],
            "steps_completed": state.get("steps_completed", []) + ["fetch_portfolio"],
        }

    return {
        "holdings": result["holdings"],
        "total_value": result["total_value"],
        "total_pnl": result["total_pnl"],
        "steps_completed": state.get("steps_completed", []) + ["fetch_portfolio"],
    }


def analyze_performers_node(state: dict[str, Any]) -> dict[str, Any]:
    """Node: Identify best/worst performing stocks."""
    holdings = state.get("holdings", [])
    analysis_type = state.get("analysis_type", "worst")

    if not holdings:
        return {
            "target_stocks": [],
            "steps_completed": state.get("steps_completed", []) + ["analyze_performers"],
        }

    target_stocks = analyze_performers(holdings, analysis_type, top_n=3)

    return {
        "target_stocks": target_stocks,
        "steps_completed": state.get("steps_completed", []) + ["analyze_performers"],
    }


async def fetch_news_node(state: dict[str, Any]) -> dict[str, Any]:
    """Node: Fetch and search news for target stocks."""
    target_stocks = state.get("target_stocks", [])

    if not target_stocks:
        return {
            "news_context": [],
            "steps_completed": state.get("steps_completed", []) + ["fetch_news"],
        }

    symbols = [s["symbol"] for s in target_stocks]

    # Ensure news is indexed
    await ensure_news_indexed(symbols)

    # Search for news
    news_articles = search_stock_news(symbols, top_k=2)

    return {
        "news_context": news_articles,
        "steps_completed": state.get("steps_completed", []) + ["fetch_news"],
    }


def generate_insights_node(state: dict[str, Any]) -> dict[str, Any]:
    """Node: Generate insights using Claude."""
    holdings = state.get("holdings", [])
    target_stocks = state.get("target_stocks", [])
    news_context = state.get("news_context", [])
    analysis_type = state.get("analysis_type", "worst")
    total_value = state.get("total_value", 0)
    total_pnl = state.get("total_pnl", 0)
    query = state.get("query", "")

    if state.get("error"):
        return {
            "insights": f"Unable to analyze portfolio: {state['error']}",
            "steps_completed": state.get("steps_completed", []) + ["generate_insights"],
        }

    if not holdings:
        return {
            "insights": "No holdings found in your portfolio.",
            "steps_completed": state.get("steps_completed", []) + ["generate_insights"],
        }

    # Format data for LLM
    performers_text = ""
    for i, stock in enumerate(target_stocks, 1):
        performers_text += (
            f"{i}. {stock['symbol']}: "
            f"Return {stock['return_pct']:.1f}%, "
            f"P&L ₹{stock['pnl']:.2f}, "
            f"Qty {stock['quantity']}\n"
        )

    news_text = get_news_context_string(news_context)

    prompt = f"""Analyze this portfolio based on the user's query.

User Query: {query}

Portfolio Summary:
- Total Value: ₹{total_value:,.2f}
- Total P&L: ₹{total_pnl:,.2f}
- Number of Holdings: {len(holdings)}

{analysis_type.title()} Performing Stocks:
{performers_text}

Recent News Context:
{news_text}

Provide a concise analysis that:
1. Summarizes the {analysis_type} performers and their returns
2. Explains possible reasons based on news (if available)
3. Gives actionable insights or observations

Keep the response focused and under 300 words."""

    try:
        anthropic = _get_anthropic()
        response = anthropic.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        insights = response.content[0].text

    except Exception as e:
        insights = f"Error generating insights: {e}"

    return {
        "insights": insights,
        "steps_completed": state.get("steps_completed", []) + ["generate_insights"],
    }


def should_continue(state: dict[str, Any]) -> str:
    """Determine if workflow should continue or end."""
    if state.get("error"):
        return "generate_insights"  # Go straight to insights to report error
    return "continue"


def create_portfolio_analysis_graph() -> StateGraph:
    """Create the Portfolio Analysis workflow graph."""
    # Define the graph with state schema
    workflow = StateGraph(dict)

    # Add nodes
    workflow.add_node("fetch_portfolio", fetch_portfolio_node)
    workflow.add_node("analyze_performers", analyze_performers_node)
    workflow.add_node("fetch_news", fetch_news_node)
    workflow.add_node("generate_insights", generate_insights_node)

    # Define edges
    workflow.set_entry_point("fetch_portfolio")

    workflow.add_conditional_edges(
        "fetch_portfolio",
        should_continue,
        {
            "continue": "analyze_performers",
            "generate_insights": "generate_insights",
        },
    )

    workflow.add_edge("analyze_performers", "fetch_news")
    workflow.add_edge("fetch_news", "generate_insights")
    workflow.add_edge("generate_insights", END)

    return workflow.compile()


class PortfolioAnalysisAgent:
    """High-level interface for Portfolio Analysis workflow."""

    def __init__(self, kite_client: KiteClient):
        self._client = kite_client
        self._graph = create_portfolio_analysis_graph()

    async def analyze(
        self,
        query: str,
        analysis_type: str = "worst",
    ) -> str:
        """Run portfolio analysis.

        Args:
            query: User's query
            analysis_type: "worst", "best", or "all"

        Returns:
            Analysis insights as string
        """
        initial_state = {
            "query": query,
            "analysis_type": analysis_type,
            "holdings": [],
            "total_value": 0.0,
            "total_pnl": 0.0,
            "target_stocks": [],
            "news_context": [],
            "insights": "",
            "error": None,
            "steps_completed": [],
        }

        config = {"configurable": {"kite_client": self._client}}

        # Run the workflow
        final_state = await self._graph.ainvoke(initial_state, config)

        return final_state.get("insights", "No insights generated.")

    def detect_analysis_type(self, query: str) -> str:
        """Detect analysis type from query."""
        query_lower = query.lower()

        if any(word in query_lower for word in ["worst", "losing", "loss", "down", "decline", "poor"]):
            return "worst"
        elif any(word in query_lower for word in ["best", "top", "winning", "gain", "up", "good"]):
            return "best"
        else:
            return "worst"  # Default


# Convenience function
async def run_portfolio_analysis(
    kite_client: KiteClient,
    query: str,
) -> str:
    """Run portfolio analysis workflow.

    Args:
        kite_client: Connected Kite MCP client
        query: User's query

    Returns:
        Analysis insights
    """
    agent = PortfolioAnalysisAgent(kite_client)
    analysis_type = agent.detect_analysis_type(query)
    return await agent.analyze(query, analysis_type)
