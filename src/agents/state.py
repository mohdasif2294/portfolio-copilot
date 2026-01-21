"""Agent state definitions for LangGraph workflows."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PortfolioAnalysisState:
    """State for Portfolio Analysis Agent.

    Tracks the progress through analysis steps:
    1. Fetch holdings
    2. Calculate metrics & identify performers
    3. Search for relevant news
    4. Generate insights
    """

    # Input
    query: str = ""
    analysis_type: str = "worst"  # "worst", "best", "all"

    # Portfolio data
    holdings: list[dict[str, Any]] = field(default_factory=list)
    total_value: float = 0.0
    total_pnl: float = 0.0

    # Analysis results
    target_stocks: list[dict[str, Any]] = field(default_factory=list)
    news_context: list[dict[str, Any]] = field(default_factory=list)

    # Output
    insights: str = ""
    error: str | None = None

    # Workflow tracking
    steps_completed: list[str] = field(default_factory=list)


@dataclass
class StockResearchState:
    """State for Stock Research Agent."""

    # Input
    symbol: str = ""
    query: str = ""

    # Data gathered
    holdings_position: dict[str, Any] | None = None
    current_price: dict[str, Any] | None = None
    news_articles: list[dict[str, Any]] = field(default_factory=list)

    # Output
    research_report: str = ""
    error: str | None = None

    steps_completed: list[str] = field(default_factory=list)


@dataclass
class MarketContextState:
    """State for Market Context Agent."""

    # Input
    query: str = ""

    # Data gathered
    portfolio_pnl: dict[str, Any] | None = None
    movers: list[dict[str, Any]] = field(default_factory=list)
    market_news: list[dict[str, Any]] = field(default_factory=list)

    # Output
    context_report: str = ""
    error: str | None = None

    steps_completed: list[str] = field(default_factory=list)
