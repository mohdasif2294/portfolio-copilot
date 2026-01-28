"""Watchlist Suggestion Agent workflow using LangGraph."""

import logging
import operator
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from src.agents.tools.news_tools import get_news_context_string
from src.mcp.kite_client import KiteClient


def replace_value(current: Any, new: Any) -> Any:
    """Reducer that replaces the current value with the new one."""
    return new


class WatchlistState(TypedDict):
    """State schema for watchlist suggestion workflow."""

    query: str
    current_holdings: Annotated[list, replace_value]
    current_sectors: Annotated[list, replace_value]
    opportunities: Annotated[list, replace_value]
    news_context: Annotated[list, replace_value]
    suggestions: Annotated[str, replace_value]
    error: Annotated[str | None, replace_value]
    steps_completed: Annotated[list, operator.add]

# Sector mappings for Indian stocks
STOCK_SECTORS = {
    # IT
    "TCS": "IT", "INFY": "IT", "WIPRO": "IT", "HCLTECH": "IT", "TECHM": "IT", "LTIM": "IT",
    # Banking
    "HDFCBANK": "Banking", "ICICIBANK": "Banking", "SBIN": "Banking", "KOTAKBANK": "Banking",
    "AXISBANK": "Banking", "INDUSINDBK": "Banking", "BANDHANBNK": "Banking",
    # NBFC
    "BAJFINANCE": "NBFC", "BAJAJFINSV": "NBFC", "HDFC": "NBFC",
    # Auto
    "TATAMOTORS": "Auto", "M&M": "Auto", "MARUTI": "Auto", "HEROMOTOCO": "Auto",
    "BAJAJ-AUTO": "Auto", "EICHERMOT": "Auto", "ASHOKLEY": "Auto",
    # Pharma
    "SUNPHARMA": "Pharma", "DRREDDY": "Pharma", "CIPLA": "Pharma", "DIVISLAB": "Pharma",
    # FMCG
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG",
    "DABUR": "FMCG", "MARICO": "FMCG", "COLPAL": "FMCG",
    # Energy
    "RELIANCE": "Energy", "ONGC": "Energy", "IOC": "Energy", "BPCL": "Energy",
    "NTPC": "Power", "POWERGRID": "Power", "TATAPOWER": "Power",
    # Metals
    "TATASTEEL": "Metals", "JSWSTEEL": "Metals", "HINDALCO": "Metals", "VEDL": "Metals",
    "COALINDIA": "Mining",
    # Infra
    "LT": "Infra", "ADANIENT": "Infra", "ADANIPORTS": "Infra",
    # Telecom
    "BHARTIARTL": "Telecom", "IDEA": "Telecom",
    # Consumer
    "TITAN": "Consumer", "ASIANPAINT": "Consumer", "PIDILITIND": "Consumer",
    # Cement
    "ULTRACEMCO": "Cement", "SHREECEM": "Cement", "AMBUJACEM": "Cement",
    # Auto Ancillary
    "GABRIEL": "Auto Ancillary", "MOTHERSON": "Auto Ancillary", "BOSCHLTD": "Auto Ancillary",
}

# Stocks to suggest per sector
SECTOR_SUGGESTIONS = {
    "IT": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "MPHASIS", "COFORGE"],
    "Banking": ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK"],
    "NBFC": ["BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "MUTHOOTFIN"],
    "Auto": ["TATAMOTORS", "M&M", "MARUTI", "HEROMOTOCO", "BAJAJ-AUTO", "EICHERMOT"],
    "Pharma": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP"],
    "FMCG": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO"],
    "Energy": ["RELIANCE", "ONGC", "IOC", "BPCL", "GAIL"],
    "Power": ["NTPC", "POWERGRID", "TATAPOWER", "ADANIGREEN"],
    "Metals": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "NMDC"],
    "Infra": ["LT", "ADANIENT", "ADANIPORTS", "BHARTIARTL"],
    "Consumer": ["TITAN", "ASIANPAINT", "PIDILITIND", "HAVELLS"],
    "Cement": ["ULTRACEMCO", "SHREECEM", "AMBUJACEM", "ACC"],
    "Auto Ancillary": ["GABRIEL", "MOTHERSON", "BOSCHLTD", "MRF"],
}


# Node functions


async def analyze_portfolio_node(
    state: WatchlistState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Node: Analyze current portfolio holdings and sectors."""
    client: KiteClient = config["configurable"]["kite_client"]

    try:
        holdings = await client.get_holdings()

        if not holdings:
            return {
                "current_holdings": [],
                "current_sectors": [],
                "steps_completed": ["analyze_portfolio"],
            }

        # Extract symbols and map to sectors
        holding_info = []
        sectors = set()

        for h in holdings:
            symbol = h.get("tradingsymbol", "")
            pnl = h.get("pnl", 0)
            return_pct = 0
            avg_price = h.get("average_price", 0)
            last_price = h.get("last_price", 0)
            if avg_price > 0:
                return_pct = ((last_price - avg_price) / avg_price) * 100

            sector = STOCK_SECTORS.get(symbol, "Other")
            sectors.add(sector)

            holding_info.append({
                "symbol": symbol,
                "sector": sector,
                "pnl": pnl,
                "return_pct": return_pct,
            })

        return {
            "current_holdings": holding_info,
            "current_sectors": list(sectors),
            "steps_completed": ["analyze_portfolio"],
        }

    except Exception as e:
        return {
            "current_holdings": [],
            "current_sectors": [],
            "error": f"Failed to analyze portfolio: {e}",
            "steps_completed": ["analyze_portfolio"],
        }


def identify_opportunities_node(state: WatchlistState) -> dict[str, Any]:
    """Node: Identify potential stocks to watch based on sectors."""
    current_holdings = state.get("current_holdings", [])
    current_sectors = state.get("current_sectors", [])

    # Get symbols user already holds
    held_symbols = {h["symbol"] for h in current_holdings}

    opportunities = []

    # Suggest stocks from sectors user invests in
    for sector in current_sectors:
        if sector in SECTOR_SUGGESTIONS:
            for symbol in SECTOR_SUGGESTIONS[sector]:
                if symbol not in held_symbols:
                    opportunities.append({
                        "symbol": symbol,
                        "sector": sector,
                        "reason": f"Same sector as your {sector} holdings",
                    })

    # Add some blue chips if not already held
    blue_chips = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR"]
    for symbol in blue_chips:
        if symbol not in held_symbols and symbol not in [o["symbol"] for o in opportunities]:
            opportunities.append({
                "symbol": symbol,
                "sector": STOCK_SECTORS.get(symbol, "Other"),
                "reason": "Blue chip stock for diversification",
            })

    # Limit to top 10 opportunities
    return {
        "opportunities": opportunities[:10],
        "steps_completed": ["identify_opportunities"],
    }


async def fetch_news_node(state: WatchlistState) -> dict[str, Any]:
    """Node: Fetch news for opportunity stocks."""
    opportunities = state.get("opportunities", [])

    if not opportunities:
        return {
            "news_context": [],
            "steps_completed": ["fetch_news"],
        }

    # Get symbols to search news for
    symbols = [o["symbol"] for o in opportunities[:5]]

    # Import here to avoid circular imports
    from src.agents.tools.news_tools import ensure_news_indexed, search_stock_news

    try:
        # Ensure news is indexed
        await ensure_news_indexed(symbols)

        # Search for news
        news_articles = search_stock_news(symbols, top_k=2)

        return {
            "news_context": news_articles,
            "steps_completed": ["fetch_news"],
        }
    except Exception as err:
        logging.error(f"Error fetching news for symbols {symbols}: {err}")
        return {
            "news_context": [],
            "steps_completed": ["fetch_news"],
        }


async def generate_suggestions_node(state: WatchlistState) -> dict[str, Any]:
    """Node: Generate watchlist suggestions using LLM."""
    query = state.get("query", "")
    current_holdings = state.get("current_holdings", [])
    current_sectors = state.get("current_sectors", [])
    opportunities = state.get("opportunities", [])
    news_context = state.get("news_context", [])

    if state.get("error"):
        return {
            "suggestions": f"Unable to generate suggestions: {state['error']}",
            "steps_completed": ["generate_suggestions"],
        }

    # Format current portfolio
    portfolio_text = "Your Current Portfolio:\n"
    if current_holdings:
        for h in current_holdings[:10]:
            portfolio_text += f"- {h['symbol']} ({h['sector']}): {h['return_pct']:.1f}% return\n"
        portfolio_text += f"\nSectors you invest in: {', '.join(current_sectors)}"
    else:
        portfolio_text = "No current holdings found."

    # Format opportunities
    opps_text = "Potential Watchlist Candidates:\n"
    for o in opportunities:
        opps_text += f"- {o['symbol']} ({o['sector']}): {o['reason']}\n"

    # Format news
    news_text = get_news_context_string(news_context) if news_context else "No recent news available."

    prompt = f"""Generate personalized watchlist suggestions based on the user's portfolio and query.

User Query: {query}

{portfolio_text}

{opps_text}

Recent News on Suggested Stocks:
{news_text}

Provide watchlist suggestions that:
1. Consider the user's current sector exposure
2. Suggest stocks for diversification if needed
3. Highlight any stocks with positive news momentum
4. Categorize suggestions (e.g., "Add to existing sectors", "Diversification picks", "Momentum plays")
5. Give brief reasoning for each suggestion

Format as a clear, actionable watchlist. Keep it under 400 words.

IMPORTANT: This is NOT investment advice. Remind the user to do their own research."""

    try:
        from src.llm.factory import get_simple_provider

        provider = get_simple_provider()
        suggestions = await provider.complete(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
        )

        if not suggestions:
            suggestions = "Error: Empty response from AI model"

    except Exception as e:
        suggestions = f"Error generating suggestions: {e}"

    return {
        "suggestions": suggestions,
        "steps_completed": ["generate_suggestions"],
    }


def should_continue(state: WatchlistState) -> str:
    """Determine if workflow should continue or end."""
    if state.get("error"):
        return "generate_suggestions"
    return "continue"


def create_watchlist_graph() -> StateGraph:
    """Create the Watchlist Suggestion workflow graph."""
    workflow = StateGraph(WatchlistState)

    # Add nodes
    workflow.add_node("analyze_portfolio", analyze_portfolio_node)
    workflow.add_node("identify_opportunities", identify_opportunities_node)
    workflow.add_node("fetch_news", fetch_news_node)
    workflow.add_node("generate_suggestions", generate_suggestions_node)

    # Define edges
    workflow.set_entry_point("analyze_portfolio")

    workflow.add_conditional_edges(
        "analyze_portfolio",
        should_continue,
        {
            "continue": "identify_opportunities",
            "generate_suggestions": "generate_suggestions",
        },
    )

    workflow.add_edge("identify_opportunities", "fetch_news")
    workflow.add_edge("fetch_news", "generate_suggestions")
    workflow.add_edge("generate_suggestions", END)

    return workflow.compile()


class WatchlistAgent:
    """High-level interface for Watchlist Suggestion workflow."""

    def __init__(self, kite_client: KiteClient):
        self._client = kite_client
        self._graph = create_watchlist_graph()

    async def suggest(self, query: str) -> str:
        """Generate watchlist suggestions.

        Args:
            query: User's query about watchlist

        Returns:
            Watchlist suggestions as string
        """
        initial_state = {
            "query": query,
            "current_holdings": [],
            "current_sectors": [],
            "opportunities": [],
            "news_context": [],
            "suggestions": "",
            "error": None,
            "steps_completed": [],
        }

        config = {"configurable": {"kite_client": self._client}}

        final_state = await self._graph.ainvoke(initial_state, config)

        return final_state.get("suggestions", "No suggestions generated.")


async def run_watchlist_suggestion(
    kite_client: KiteClient,
    query: str,
) -> str:
    """Run watchlist suggestion workflow."""
    agent = WatchlistAgent(kite_client)
    return await agent.suggest(query)
