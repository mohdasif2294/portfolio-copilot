"""Fundamental Analysis Agent using screener.in data, news, and LLM synthesis."""

import operator
import os
from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

from anthropic import Anthropic
from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from src.agents.tools.news_tools import (
    ensure_news_indexed,
    get_news_context_string,
    search_stock_news,
)
from src.agents.tools.symbol_tools import extract_symbol
from src.data.scrapers.screener import FundamentalData, get_stock_fundamentals
from src.mcp.kite_client import KiteClient

load_dotenv()

MODEL = "claude-sonnet-4-20250514"


def replace_value(current: Any, new: Any) -> Any:
    """Reducer that replaces the current value with the new one."""
    return new


class FundamentalAnalysisState(TypedDict):
    """State schema for fundamental analysis workflow."""

    query: str
    symbol: Annotated[str, replace_value]
    fundamentals: Annotated[Any, replace_value]  # FundamentalData
    score: Annotated[Any, replace_value]  # FundamentalScore
    in_portfolio: Annotated[bool, replace_value]
    holding_qty: Annotated[int, replace_value]
    holding_avg_price: Annotated[float, replace_value]
    holding_pnl: Annotated[float, replace_value]
    holding_value: Annotated[float, replace_value]
    news_articles: Annotated[list, replace_value]
    response: Annotated[str, replace_value]
    error: Annotated[str | None, replace_value]
    steps_completed: Annotated[list, operator.add]


def _get_anthropic() -> Anthropic:
    """Get Anthropic client."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    return Anthropic(api_key=api_key)


@dataclass
class FundamentalScore:
    """Scoring breakdown for fundamental analysis."""

    valuation_score: int = 0  # -2 to +2
    profitability_score: int = 0  # -2 to +2
    growth_score: int = 0  # -2 to +2
    financial_health_score: int = 0  # -2 to +2
    promoter_score: int = 0  # -2 to +2

    valuation_notes: list[str] = field(default_factory=list)
    profitability_notes: list[str] = field(default_factory=list)
    growth_notes: list[str] = field(default_factory=list)
    financial_health_notes: list[str] = field(default_factory=list)
    promoter_notes: list[str] = field(default_factory=list)

    @property
    def total_score(self) -> int:
        """Total score from -10 to +10."""
        return (
            self.valuation_score
            + self.profitability_score
            + self.growth_score
            + self.financial_health_score
            + self.promoter_score
        )

    @property
    def recommendation(self) -> str:
        """Get recommendation based on total score."""
        score = self.total_score
        if score >= 5:
            return "STRONG BUY"
        elif score >= 2:
            return "BUY"
        elif score >= -1:
            return "HOLD"
        elif score >= -4:
            return "SELL"
        else:
            return "STRONG SELL"


def analyze_fundamentals(data: FundamentalData) -> FundamentalScore:
    """Analyze fundamental data and generate scores.

    Scoring criteria:
    - Each category scores from -2 (very bad) to +2 (excellent)
    - Total score ranges from -10 to +10
    """
    score = FundamentalScore()

    # 1. Valuation Analysis
    if data.pe_ratio > 0:
        if data.pe_ratio < 15:
            score.valuation_score += 2
            score.valuation_notes.append(f"Attractive P/E of {data.pe_ratio:.1f}")
        elif data.pe_ratio < 25:
            score.valuation_score += 1
            score.valuation_notes.append(f"Fair P/E of {data.pe_ratio:.1f}")
        elif data.pe_ratio < 40:
            score.valuation_notes.append(f"P/E of {data.pe_ratio:.1f} is on the higher side")
        else:
            score.valuation_score -= 1
            score.valuation_notes.append(f"Expensive P/E of {data.pe_ratio:.1f}")

    if data.pb_ratio > 0:
        if data.pb_ratio < 2:
            score.valuation_score += 1
            score.valuation_notes.append(f"Good P/B of {data.pb_ratio:.1f}")
        elif data.pb_ratio > 5:
            score.valuation_score -= 1
            score.valuation_notes.append(f"High P/B of {data.pb_ratio:.1f}")

    if data.dividend_yield > 2:
        score.valuation_score += 1
        score.valuation_notes.append(f"Good dividend yield of {data.dividend_yield:.1f}%")

    # Cap valuation score
    score.valuation_score = max(-2, min(2, score.valuation_score))

    # 2. Profitability Analysis
    if data.roe > 0:
        if data.roe >= 20:
            score.profitability_score += 2
            score.profitability_notes.append(f"Excellent ROE of {data.roe:.1f}%")
        elif data.roe >= 15:
            score.profitability_score += 1
            score.profitability_notes.append(f"Good ROE of {data.roe:.1f}%")
        elif data.roe >= 10:
            score.profitability_notes.append(f"Moderate ROE of {data.roe:.1f}%")
        else:
            score.profitability_score -= 1
            score.profitability_notes.append(f"Low ROE of {data.roe:.1f}%")

    if data.roce > 0:
        if data.roce >= 20:
            score.profitability_score += 1
            score.profitability_notes.append(f"Strong ROCE of {data.roce:.1f}%")
        elif data.roce < 10:
            score.profitability_score -= 1
            score.profitability_notes.append(f"Weak ROCE of {data.roce:.1f}%")

    # Cap profitability score
    score.profitability_score = max(-2, min(2, score.profitability_score))

    # 3. Growth Analysis
    if data.revenue_growth_3yr > 0:
        if data.revenue_growth_3yr >= 15:
            score.growth_score += 1
            score.growth_notes.append(
                f"Strong revenue growth of {data.revenue_growth_3yr:.1f}% (3yr)"
            )
        elif data.revenue_growth_3yr < 5:
            score.growth_score -= 1
            score.growth_notes.append(
                f"Slow revenue growth of {data.revenue_growth_3yr:.1f}% (3yr)"
            )

    if data.profit_growth_3yr > 0:
        if data.profit_growth_3yr >= 15:
            score.growth_score += 1
            score.growth_notes.append(
                f"Strong profit growth of {data.profit_growth_3yr:.1f}% (3yr)"
            )
        elif data.profit_growth_3yr < 5:
            score.growth_score -= 1
            score.growth_notes.append(
                f"Slow profit growth of {data.profit_growth_3yr:.1f}% (3yr)"
            )

    # Cap growth score
    score.growth_score = max(-2, min(2, score.growth_score))

    # 4. Financial Health Analysis
    if data.debt_to_equity >= 0:
        if data.debt_to_equity < 0.5:
            score.financial_health_score += 2
            score.financial_health_notes.append(
                f"Low debt with D/E of {data.debt_to_equity:.2f}"
            )
        elif data.debt_to_equity < 1:
            score.financial_health_score += 1
            score.financial_health_notes.append(
                f"Manageable debt with D/E of {data.debt_to_equity:.2f}"
            )
        elif data.debt_to_equity < 2:
            score.financial_health_notes.append(f"D/E ratio of {data.debt_to_equity:.2f}")
        else:
            score.financial_health_score -= 2
            score.financial_health_notes.append(
                f"High debt with D/E of {data.debt_to_equity:.2f}"
            )

    if data.current_ratio > 0:
        if data.current_ratio >= 2:
            score.financial_health_score += 1
            score.financial_health_notes.append(
                f"Strong liquidity with current ratio of {data.current_ratio:.1f}"
            )
        elif data.current_ratio < 1:
            score.financial_health_score -= 1
            score.financial_health_notes.append(
                f"Liquidity concern with current ratio of {data.current_ratio:.1f}"
            )

    # Cap financial health score
    score.financial_health_score = max(-2, min(2, score.financial_health_score))

    # 5. Promoter Holding Analysis
    if data.promoter_holding > 0:
        if data.promoter_holding >= 60:
            score.promoter_score += 1
            score.promoter_notes.append(
                f"Strong promoter holding of {data.promoter_holding:.1f}%"
            )
        elif data.promoter_holding < 30:
            score.promoter_score -= 1
            score.promoter_notes.append(
                f"Low promoter holding of {data.promoter_holding:.1f}%"
            )

    if data.promoter_holding_change != 0:
        if data.promoter_holding_change > 0:
            score.promoter_score += 1
            score.promoter_notes.append(
                f"Promoters increasing stake by {data.promoter_holding_change:.1f}%"
            )
        elif data.promoter_holding_change < -2:
            score.promoter_score -= 1
            score.promoter_notes.append(
                f"Promoters reducing stake by {abs(data.promoter_holding_change):.1f}%"
            )

    # Cap promoter score
    score.promoter_score = max(-2, min(2, score.promoter_score))

    return score


def format_fundamentals_for_llm(data: FundamentalData, score: FundamentalScore) -> str:
    """Format fundamental data as context for LLM."""
    lines = []

    lines.append(f"Company: {data.name or data.symbol}")
    lines.append(f"Symbol: {data.symbol}")
    lines.append("")

    if data.error:
        lines.append(f"Error fetching data: {data.error}")
        return "\n".join(lines)

    lines.append("KEY METRICS:")
    if data.market_cap > 0:
        lines.append(f"- Market Cap: ₹{data.market_cap:,.0f} Cr")
    if data.current_price > 0:
        lines.append(f"- Current Price: ₹{data.current_price:,.2f}")
    if data.pe_ratio > 0:
        lines.append(f"- P/E Ratio: {data.pe_ratio:.1f}")
    if data.pb_ratio > 0:
        lines.append(f"- P/B Ratio: {data.pb_ratio:.1f}")
    if data.dividend_yield > 0:
        lines.append(f"- Dividend Yield: {data.dividend_yield:.1f}%")
    if data.roe > 0:
        lines.append(f"- ROE: {data.roe:.1f}%")
    if data.roce > 0:
        lines.append(f"- ROCE: {data.roce:.1f}%")
    if data.debt_to_equity >= 0:
        lines.append(f"- Debt/Equity: {data.debt_to_equity:.2f}")
    if data.promoter_holding > 0:
        lines.append(f"- Promoter Holding: {data.promoter_holding:.1f}%")
        if data.promoter_holding_change != 0:
            lines.append(f"- Promoter Holding Change: {data.promoter_holding_change:+.1f}%")

    if data.high_52w > 0 and data.low_52w > 0:
        lines.append(f"- 52W High: ₹{data.high_52w:,.2f}")
        lines.append(f"- 52W Low: ₹{data.low_52w:,.2f}")

    lines.append("")
    lines.append("QUANTITATIVE ANALYSIS:")
    lines.append(f"- Total Score: {score.total_score}/10")
    lines.append(f"- System Recommendation: {score.recommendation}")
    lines.append("")
    lines.append("Score Breakdown:")
    lines.append(f"- Valuation: {score.valuation_score:+d} ({', '.join(score.valuation_notes) or 'N/A'})")
    lines.append(f"- Profitability: {score.profitability_score:+d} ({', '.join(score.profitability_notes) or 'N/A'})")
    lines.append(f"- Growth: {score.growth_score:+d} ({', '.join(score.growth_notes) or 'N/A'})")
    lines.append(f"- Financial Health: {score.financial_health_score:+d} ({', '.join(score.financial_health_notes) or 'N/A'})")
    lines.append(f"- Promoter Activity: {score.promoter_score:+d} ({', '.join(score.promoter_notes) or 'N/A'})")

    if data.pros or data.cons:
        lines.append("")
        lines.append("SCREENER.IN ANALYSIS:")
        if data.pros:
            lines.append("Strengths:")
            for pro in data.pros:
                lines.append(f"  + {pro}")
        if data.cons:
            lines.append("Concerns:")
            for con in data.cons:
                lines.append(f"  - {con}")

    return "\n".join(lines)


# Node functions for LangGraph workflow

async def extract_symbol_node(state: FundamentalAnalysisState) -> dict[str, Any]:
    """Node: Extract stock symbol from query."""
    query = state.get("query", "")
    symbol = state.get("symbol", "")

    if not symbol:
        symbol = extract_symbol(query)

    if not symbol:
        return {
            "error": "Could not identify stock symbol from query. Please specify a stock symbol.",
            "steps_completed": ["extract_symbol"],
        }

    return {
        "symbol": symbol.upper(),
        "steps_completed": ["extract_symbol"],
    }


async def fetch_fundamentals_node(state: FundamentalAnalysisState) -> dict[str, Any]:
    """Node: Fetch fundamental data from screener.in."""
    symbol = state.get("symbol")

    if not symbol or state.get("error"):
        return {
            "steps_completed": ["fetch_fundamentals"],
        }

    fundamentals = await get_stock_fundamentals(symbol)
    score = analyze_fundamentals(fundamentals) if not fundamentals.error else FundamentalScore()

    return {
        "fundamentals": fundamentals,
        "score": score,
        "steps_completed": ["fetch_fundamentals"],
    }


async def check_holdings_node(state: FundamentalAnalysisState, config: RunnableConfig) -> dict[str, Any]:
    """Node: Check if user holds this stock."""
    client: KiteClient = config["configurable"]["kite_client"]
    symbol = state.get("symbol", "").upper()

    if state.get("error"):
        return {
            "steps_completed": ["check_holdings"],
        }

    try:
        holdings = await client.get_holdings()
        for h in holdings:
            if h.get("tradingsymbol", "").upper() == symbol:
                return {
                    "in_portfolio": True,
                    "holding_qty": h.get("quantity", 0),
                    "holding_avg_price": h.get("average_price", 0),
                    "holding_pnl": h.get("pnl", 0),
                    "holding_value": h.get("quantity", 0) * h.get("last_price", 0),
                    "steps_completed": ["check_holdings"],
                }
    except Exception:
        pass

    return {
        "in_portfolio": False,
        "steps_completed": ["check_holdings"],
    }


async def fetch_news_node(state: FundamentalAnalysisState) -> dict[str, Any]:
    """Node: Fetch recent news about the stock."""
    symbol = state.get("symbol", "")

    if not symbol or state.get("error"):
        return {
            "news_articles": [],
            "steps_completed": ["fetch_news"],
        }

    # Ensure news is indexed
    await ensure_news_indexed([symbol])

    # Search for news
    news_articles = search_stock_news([symbol], top_k=5)

    return {
        "news_articles": news_articles,
        "steps_completed": ["fetch_news"],
    }


def generate_analysis_node(state: FundamentalAnalysisState) -> dict[str, Any]:
    """Node: Generate comprehensive analysis using Claude."""
    query = state.get("query", "")
    fundamentals = state.get("fundamentals")
    score = state.get("score") or FundamentalScore()
    in_portfolio = state.get("in_portfolio", False)
    holding_qty = state.get("holding_qty", 0)
    holding_avg_price = state.get("holding_avg_price", 0)
    holding_pnl = state.get("holding_pnl", 0)
    holding_value = state.get("holding_value", 0)
    news_articles = state.get("news_articles", [])

    # Handle errors
    if state.get("error"):
        return {
            "response": f"## Analysis Error\n\n{state['error']}",
            "steps_completed": ["generate_analysis"],
        }

    # Format holdings info
    holdings_text = "User does not currently hold this stock."
    if in_portfolio:
        holdings_text = f"""User's Position:
- Quantity: {holding_qty} shares
- Average Price: ₹{holding_avg_price:.2f}
- Current Value: ₹{holding_value:,.2f}
- P&L: ₹{holding_pnl:,.2f}"""

    # Format fundamentals
    fundamentals_text = "Fundamental data not available."
    if fundamentals and not fundamentals.error:
        fundamentals_text = format_fundamentals_for_llm(fundamentals, score)
    elif fundamentals and fundamentals.error:
        fundamentals_text = f"Error fetching fundamentals: {fundamentals.error}"

    # Format news
    news_text = get_news_context_string(news_articles)

    prompt = f"""You are a financial analyst providing fundamental analysis for Indian stocks.

User Query: {query}

{holdings_text}

FUNDAMENTAL DATA FROM SCREENER.IN:
{fundamentals_text}

RECENT NEWS:
{news_text}

Based on the fundamental data, news, and the user's query, provide a comprehensive analysis that:

1. **Summary**: Brief overview of the company and current state
2. **Fundamental Analysis**: Comment on valuation, profitability, growth, and financial health
3. **News Impact**: How recent news might affect the stock
4. **Recommendation**: Clear recommendation (Strong Buy/Buy/Hold/Sell/Strong Sell) with reasoning
5. **Risk Factors**: Key risks to consider
6. **Action Items**: What should the user do based on whether they hold this stock or not

Format the response in clean markdown. Be direct and actionable.
Keep the analysis concise but comprehensive (under 500 words).

IMPORTANT: This is for informational purposes only, not financial advice."""

    try:
        anthropic = _get_anthropic()
        response = anthropic.messages.create(
            model=MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        analysis = response.content[0].text

    except Exception as e:
        analysis = f"## Analysis Error\n\nUnable to generate analysis: {e}"

    return {
        "response": analysis,
        "steps_completed": ["generate_analysis"],
    }


def should_continue(state: FundamentalAnalysisState) -> str:
    """Determine if workflow should continue or skip to analysis."""
    if state.get("error"):
        return "generate_analysis"
    return "continue"


def create_fundamental_analysis_graph() -> StateGraph:
    """Create the Fundamental Analysis workflow graph."""
    workflow = StateGraph(FundamentalAnalysisState)

    # Add nodes
    workflow.add_node("extract_symbol", extract_symbol_node)
    workflow.add_node("fetch_fundamentals", fetch_fundamentals_node)
    workflow.add_node("check_holdings", check_holdings_node)
    workflow.add_node("fetch_news", fetch_news_node)
    workflow.add_node("generate_analysis", generate_analysis_node)

    # Define edges
    workflow.set_entry_point("extract_symbol")

    workflow.add_conditional_edges(
        "extract_symbol",
        should_continue,
        {
            "continue": "fetch_fundamentals",
            "generate_analysis": "generate_analysis",
        },
    )

    workflow.add_edge("fetch_fundamentals", "check_holdings")
    workflow.add_edge("check_holdings", "fetch_news")
    workflow.add_edge("fetch_news", "generate_analysis")
    workflow.add_edge("generate_analysis", END)

    return workflow.compile()


class FundamentalAnalysisAgent:
    """Agent for fundamental stock analysis with news integration."""

    def __init__(self, kite_client: KiteClient):
        self._client = kite_client
        self._graph = create_fundamental_analysis_graph()

    async def analyze(self, query: str, symbol: str | None = None) -> str:
        """Run fundamental analysis for a stock.

        Args:
            query: User query like "Is Reliance a good buy?"
            symbol: Optional explicit symbol

        Returns:
            Comprehensive analysis report
        """
        initial_state = {
            "query": query,
            "symbol": symbol or "",
            "fundamentals": None,
            "score": None,
            "in_portfolio": False,
            "holding_qty": 0,
            "holding_avg_price": 0,
            "holding_pnl": 0,
            "holding_value": 0,
            "news_articles": [],
            "response": "",
            "error": None,
            "steps_completed": [],
        }

        config = {"configurable": {"kite_client": self._client}}

        final_state = await self._graph.ainvoke(initial_state, config)

        return final_state.get("response", "Unable to complete analysis")


async def run_fundamental_analysis(
    kite_client: KiteClient,
    query: str,
    symbol: str | None = None,
) -> dict[str, Any]:
    """Convenience function to run fundamental analysis.

    Args:
        kite_client: KiteClient instance
        query: User query
        symbol: Optional explicit symbol

    Returns:
        Dict with response and metadata
    """
    agent = FundamentalAnalysisAgent(kite_client)
    response = await agent.analyze(query, symbol)
    return {
        "response": response,
        "agent_used": "Fundamental Analysis Agent",
    }
