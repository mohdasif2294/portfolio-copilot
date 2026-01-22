"""Agent orchestrator for detecting and routing to appropriate workflows."""

import re
from typing import Any

from src.agents.workflows.fundamental_analysis import FundamentalAnalysisAgent
from src.agents.workflows.market_context import MarketContextAgent
from src.agents.workflows.portfolio_analysis import PortfolioAnalysisAgent
from src.agents.workflows.stock_research import StockResearchAgent
from src.agents.workflows.watchlist_suggestion import WatchlistAgent
from src.mcp.kite_client import KiteClient


class AgentOrchestrator:
    """Orchestrates agent workflows based on user queries."""

    def __init__(self, kite_client: KiteClient):
        self._client = kite_client
        self._portfolio_agent = PortfolioAnalysisAgent(kite_client)
        self._research_agent = StockResearchAgent(kite_client)
        self._context_agent = MarketContextAgent(kite_client)
        self._watchlist_agent = WatchlistAgent(kite_client)
        self._fundamental_agent = FundamentalAnalysisAgent(kite_client)

    def should_use_agent(self, query: str) -> tuple[bool, str | None]:
        """Determine if query should trigger an agent workflow.

        Args:
            query: User's query

        Returns:
            Tuple of (should_use_agent, agent_type)
        """
        query_lower = query.lower()

        # Portfolio Analysis patterns
        portfolio_patterns = [
            r"analyz\w*\s+(my\s+)?portfolio",
            r"(worst|best|top|losing|winning)\s+(performing\s+)?(stock|holding)",
            r"which\s+(stock|holding).*(worst|best|losing|winning)",
            r"portfolio\s+(analysis|insight|summary)",
            r"(deep\s+)?dive\s+(into\s+)?(my\s+)?portfolio",
            # Change/performance queries
            r"(change|performance|return|pnl|p&l|profit|loss)\s+(in|of|for)\s+(my\s+)?portfolio",
            r"(my\s+)?portfolio.*(change|performance|yesterday|today|week|month)",
            r"how\s+(did|is|has|was)\s+(my\s+)?portfolio",
            r"(what|show).*(my\s+)?portfolio.*(change|return|pnl|performance)",
        ]

        for pattern in portfolio_patterns:
            if re.search(pattern, query_lower):
                return True, "portfolio_analysis"

        # Market Context patterns
        context_patterns = [
            r"why\s+(is|are|did)\s+(my\s+)?(portfolio|stock|market).*(down|up|fall|drop|rise|crash)",
            r"what\s+(happened|caused).*(market|portfolio|today)",
            r"market\s+(context|overview|summary|update)",
            r"explain\s+(today|the)\s*(market|movement|change)",
            r"(portfolio|market)\s+(drop|crash|rally|surge)",
        ]

        for pattern in context_patterns:
            if re.search(pattern, query_lower):
                return True, "market_context"

        # Watchlist patterns
        watchlist_patterns = [
            r"watchlist\s*(suggestion|recommend|idea|stock)",
            r"(suggest|recommend)\s+(stock|share)s?\s*(to\s+)?(watch|buy|add)",
            r"what\s+(should|can)\s+i\s+(buy|watch|add)",
            r"(stock|share)s?\s+to\s+(watch|buy|add)",
            r"(build|create|make)\s+(my\s+)?watchlist",
            r"(future|next)\s+(buy|investment|stock)",
            r"what\s+to\s+(buy|invest|watch)",
        ]

        for pattern in watchlist_patterns:
            if re.search(pattern, query_lower):
                return True, "watchlist"

        # Fundamental Analysis patterns (check before stock_research as it's more specific)
        fundamental_patterns = [
            r"(is|are)\s+\w+\s+(a\s+)?(good|bad)\s+(buy|stock|investment)",
            r"fundamental(s)?\s+(analysis|of|for)\s+\w+",
            r"\w+\s+fundamental(s)?",
            r"(should\s+i|can\s+i)\s+(buy|invest|hold|sell)\s+\w+",
            r"(valuation|value)\s+(of|for)\s+\w+",
            r"(pe|pb|roe|roce|debt)\s+(ratio\s+)?(of|for)\s+\w+",
            r"(analyze|check)\s+(the\s+)?(financials|fundamentals)\s+(of|for)\s+\w+",
            r"(good|bad)\s+(stock|investment|buy)\s*\?",
            r"worth\s+(buying|investing)",
        ]

        for pattern in fundamental_patterns:
            if re.search(pattern, query_lower):
                return True, "fundamental_analysis"

        # Stock Research patterns
        research_patterns = [
            r"(tell|inform)\s+(me\s+)?(about|regarding)\s+\w+",
            r"research\s+\w+(\s+stock)?",
            r"(what|how)\s+(is|about)\s+\w+\s*(stock|share|doing)?",
            r"(analyze|analysis)\s+(of\s+)?\w+\s*(stock)?",
            r"\w+\s+(stock|share)\s+(research|analysis|info|details)",
            r"(news|update)\s+(on|about|for)\s+\w+",
        ]

        for pattern in research_patterns:
            if re.search(pattern, query_lower):
                return True, "stock_research"

        return False, None

    async def run_agent(
        self,
        agent_type: str,
        query: str,
    ) -> dict[str, Any]:
        """Run the specified agent workflow.

        Args:
            agent_type: Type of agent to run
            query: User's query

        Returns:
            Dict with 'response' and 'agent_used'
        """
        if agent_type == "portfolio_analysis":
            analysis_type = self._portfolio_agent.detect_analysis_type(query)
            response = await self._portfolio_agent.analyze(query, analysis_type)
            return {
                "response": response,
                "agent_used": "Portfolio Analysis Agent",
            }

        elif agent_type == "stock_research":
            response = await self._research_agent.research(query)
            return {
                "response": response,
                "agent_used": "Stock Research Agent",
            }

        elif agent_type == "market_context":
            response = await self._context_agent.explain(query)
            return {
                "response": response,
                "agent_used": "Market Context Agent",
            }

        elif agent_type == "watchlist":
            response = await self._watchlist_agent.suggest(query)
            return {
                "response": response,
                "agent_used": "Watchlist Suggestion Agent",
            }

        elif agent_type == "fundamental_analysis":
            response = await self._fundamental_agent.analyze(query)
            return {
                "response": response,
                "agent_used": "Fundamental Analysis Agent",
            }

        return {
            "response": "Unknown agent type",
            "agent_used": None,
        }

    async def process_query(
        self,
        query: str,
        force_agent: str | None = None,
    ) -> dict[str, Any]:
        """Process a query, using agents if appropriate.

        Args:
            query: User's query
            force_agent: Force a specific agent (bypasses detection)

        Returns:
            Dict with 'response', 'used_agent', 'agent_type'
        """
        # Check for forced agent
        if force_agent:
            # Validate force_agent against known agent types
            valid_agent_types = {
                "portfolio_analysis",
                "stock_research",
                "market_context",
                "watchlist",
                "fundamental_analysis",
            }
            
            if force_agent not in valid_agent_types:
                return {
                    "response": f"Invalid agent type '{force_agent}'. Valid types are: {', '.join(sorted(valid_agent_types))}",
                    "used_agent": False,
                    "agent_type": None,
                }
            
            result = await self.run_agent(force_agent, query)
            
            # Check if run_agent returned an error (agent_used is None/falsy)
            if not result.get("agent_used"):
                return {
                    "response": result.get("response", "Agent execution failed"),
                    "used_agent": False,
                    "agent_type": None,
                }
            
            return {
                "response": result["response"],
                "used_agent": True,
                "agent_type": result.get("agent_used"),
            }

        # Auto-detect if agent should be used
        should_use, agent_type = self.should_use_agent(query)

        if should_use and agent_type:
            result = await self.run_agent(agent_type, query)
            return {
                "response": result["response"],
                "used_agent": True,
                "agent_type": result.get("agent_used"),
            }

        # No agent needed - return None to indicate regular chat should be used
        return {
            "response": None,
            "used_agent": False,
            "agent_type": None,
        }


# Query patterns that trigger agents (for documentation/help)
AGENT_TRIGGERS = {
    "portfolio_analysis": [
        "Analyze my portfolio",
        "What are my worst performing stocks?",
        "Which stock is losing the most?",
        "Show my best performers",
        "Deep dive into my portfolio",
        "What is the change in my portfolio from yesterday?",
        "How did my portfolio do today?",
        "Show my portfolio performance",
    ],
    "stock_research": [
        "Tell me about Reliance",
        "Research TCS stock",
        "What's happening with INFY?",
        "Analyze HDFC Bank",
        "News on ICICI Bank",
    ],
    "market_context": [
        "Why is my portfolio down?",
        "What happened to the market today?",
        "Explain today's market movement",
        "Why did my stocks crash?",
        "Market context for my portfolio",
    ],
    "watchlist": [
        "Suggest stocks for my watchlist",
        "What stocks should I watch?",
        "Recommend stocks to buy",
        "Build my watchlist",
        "What should I invest in next?",
    ],
    "fundamental_analysis": [
        "Is Reliance a good buy?",
        "Fundamentals of TCS",
        "Should I buy HDFC Bank?",
        "Is ITC a good investment?",
        "Check financials of Infosys",
        "PE ratio of Wipro",
    ],
}
