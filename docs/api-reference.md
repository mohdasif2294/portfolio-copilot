# API Reference

## Agents

### AgentOrchestrator

Main entry point for routing queries to specialized agents.

```python
from src.agents.orchestrator import AgentOrchestrator

orchestrator = AgentOrchestrator(kite_client)
```

#### Methods

##### `should_use_agent(query: str) -> tuple[bool, str | None]`

Determines if a query should trigger an agent workflow.

**Parameters:**
- `query`: User's natural language query

**Returns:**
- `tuple[bool, str | None]`: (should_use_agent, agent_type)

**Example:**
```python
should_use, agent_type = orchestrator.should_use_agent("Is TCS a good buy?")
# Returns: (True, "fundamental_analysis")
```

##### `async run_agent(agent_type: str, query: str) -> dict[str, Any]`

Executes the specified agent workflow.

**Parameters:**
- `agent_type`: One of "portfolio_analysis", "stock_research", "market_context", "watchlist", "fundamental_analysis"
- `query`: User's query

**Returns:**
```python
{
    "response": str,      # Markdown formatted response
    "agent_used": str,    # Human-readable agent name
}
```

##### `async process_query(query: str, force_agent: str | None = None) -> dict[str, Any]`

Processes a query, automatically detecting if an agent should be used.

**Parameters:**
- `query`: User's query
- `force_agent`: Optional agent type to force (bypasses detection)

**Returns:**
```python
{
    "response": str | None,
    "used_agent": bool,
    "agent_type": str | None,
}
```

---

### FundamentalAnalysisAgent

Evaluates stocks using fundamental data from screener.in.

```python
from src.agents.workflows.fundamental_analysis import FundamentalAnalysisAgent

agent = FundamentalAnalysisAgent(kite_client)
```

#### Methods

##### `async analyze(query: str, symbol: str | None = None) -> str`

Runs comprehensive fundamental analysis.

**Parameters:**
- `query`: User's query (e.g., "Is Reliance a good buy?")
- `symbol`: Optional explicit stock symbol

**Returns:**
- Markdown formatted analysis report

**Example:**
```python
report = await agent.analyze("Should I buy TCS?")
print(report)
```

---

### PortfolioAnalysisAgent

Analyzes portfolio holdings to identify performers.

```python
from src.agents.workflows.portfolio_analysis import PortfolioAnalysisAgent

agent = PortfolioAnalysisAgent(kite_client)
```

#### Methods

##### `async analyze(query: str, analysis_type: str = "worst") -> str`

Analyzes portfolio based on specified criteria.

**Parameters:**
- `query`: User's query
- `analysis_type`: "worst", "best", or "all"

**Returns:**
- Markdown formatted analysis

##### `detect_analysis_type(query: str) -> str`

Detects analysis type from query text.

**Parameters:**
- `query`: User's query

**Returns:**
- One of "worst", "best", "all"

---

### StockResearchAgent

Researches individual stocks with news and price data.

```python
from src.agents.workflows.stock_research import StockResearchAgent

agent = StockResearchAgent(kite_client)
```

#### Methods

##### `async research(query: str, symbol: str | None = None) -> str`

Researches a specific stock.

**Parameters:**
- `query`: User's query
- `symbol`: Optional explicit symbol

**Returns:**
- Markdown formatted research report

---

### MarketContextAgent

Explains market movements affecting the portfolio.

```python
from src.agents.workflows.market_context import MarketContextAgent

agent = MarketContextAgent(kite_client)
```

#### Methods

##### `async explain(query: str) -> str`

Explains market context for portfolio movements.

**Parameters:**
- `query`: User's query about market movements

**Returns:**
- Markdown formatted explanation

---

### WatchlistAgent

Suggests stocks for watchlist based on portfolio analysis.

```python
from src.agents.workflows.watchlist_suggestion import WatchlistAgent

agent = WatchlistAgent(kite_client)
```

#### Methods

##### `async suggest(query: str) -> str`

Generates watchlist suggestions.

**Parameters:**
- `query`: User's query about watchlist

**Returns:**
- Markdown formatted suggestions

---

## Data Scrapers

### ScreenerScraper

Scrapes fundamental data from screener.in.

```python
from src.data.scrapers.screener import ScreenerScraper, get_stock_fundamentals

# Using context manager
async with ScreenerScraper() as scraper:
    data = await scraper.get_fundamentals("TCS")

# Using convenience function
data = await get_stock_fundamentals("TCS")
```

#### FundamentalData

```python
@dataclass
class FundamentalData:
    symbol: str
    name: str = ""

    # Valuation
    market_cap: float = 0       # in Cr
    current_price: float = 0
    pe_ratio: float = 0
    pb_ratio: float = 0
    dividend_yield: float = 0

    # Profitability
    roe: float = 0              # Return on Equity %
    roce: float = 0             # Return on Capital Employed %
    profit_margin: float = 0

    # Growth
    revenue_growth_3yr: float = 0
    profit_growth_3yr: float = 0

    # Financial Health
    debt_to_equity: float = 0
    current_ratio: float = 0
    interest_coverage: float = 0

    # Shareholding
    promoter_holding: float = 0
    promoter_holding_change: float = 0

    # Screener's analysis
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)

    # Additional info
    sector: str = ""
    industry: str = ""
    book_value: float = 0
    face_value: float = 0
    high_52w: float = 0
    low_52w: float = 0

    error: str | None = None
```

---

### MoneyControlScraper

Scrapes news from MoneyControl.

```python
from src.data.scrapers.moneycontrol import MoneyControlScraper

async with MoneyControlScraper() as scraper:
    articles = await scraper.get_latest_news(limit=10)
    stock_news = await scraper.get_stock_news("RELIANCE", limit=5)
```

#### Methods

##### `async get_latest_news(limit: int = 10) -> list[NewsArticle]`

Fetches latest market news.

##### `async get_stock_news(symbol: str, limit: int = 5) -> list[NewsArticle]`

Fetches news for a specific stock.

---

### EconomicTimesScraper

Scrapes news from Economic Times.

```python
from src.data.scrapers.economictimes import EconomicTimesScraper

async with EconomicTimesScraper() as scraper:
    articles = await scraper.get_latest_news(limit=10)
```

---

## RAG System

### VectorStore

ChromaDB wrapper for vector storage.

```python
from src.rag.vector_store import VectorStore, get_vector_store

store = get_vector_store()
```

#### Methods

##### `add(documents: list[str], metadatas: list[dict], ids: list[str]) -> None`

Adds documents to the vector store.

**Parameters:**
- `documents`: List of text content
- `metadatas`: List of metadata dicts
- `ids`: List of unique IDs

##### `search(query: str, top_k: int = 5, where: dict | None = None) -> list[SearchResult]`

Searches for similar documents.

**Parameters:**
- `query`: Search query
- `top_k`: Number of results
- `where`: Optional metadata filter

**Returns:**
- List of SearchResult objects

##### `count() -> int`

Returns total document count.

---

### EmbeddingModel

Sentence transformer wrapper.

```python
from src.rag.embeddings import EmbeddingModel, get_embedding_model

model = get_embedding_model()
embedding = model.embed("Some text")
```

#### Methods

##### `embed(text: str) -> list[float]`

Generates embedding for text.

**Returns:**
- 384-dimensional float vector

##### `embed_batch(texts: list[str]) -> list[list[float]]`

Generates embeddings for multiple texts.

---

### Retriever

High-level retrieval interface.

```python
from src.rag.retriever import Retriever, get_retriever

retriever = get_retriever()
results = retriever.search("TCS quarterly results", top_k=5)
```

#### Methods

##### `search(query: str, top_k: int = 5, symbol: str | None = None) -> list[SearchResult]`

Searches for relevant documents.

**Parameters:**
- `query`: Search query
- `top_k`: Number of results
- `symbol`: Optional stock symbol filter

**Returns:**
```python
@dataclass
class SearchResult:
    content: str
    title: str | None
    source: str
    url: str | None
    score: float
    metadata: dict
```

##### `get_document_count() -> int`

Returns total indexed documents.

---

## MCP Client

### KiteClient

Zerodha Kite MCP client.

```python
from src.mcp.kite_client import KiteClient

async with KiteClient() as client:
    holdings = await client.get_holdings()
```

#### Methods

##### `async login() -> LoginResult`

Initiates OAuth login flow.

**Returns:**
```python
@dataclass
class LoginResult:
    url: str | None
    success: bool
    error: str | None
```

##### `async get_holdings() -> list[dict]`

Fetches portfolio holdings.

**Returns:**
```python
[
    {
        "tradingsymbol": "TCS",
        "quantity": 10,
        "average_price": 3500.0,
        "last_price": 4000.0,
        "pnl": 5000.0,
        "day_change": 50.0,
        "day_change_percentage": 1.25,
    },
    ...
]
```

##### `async get_quotes(instruments: list[str]) -> dict`

Fetches real-time quotes.

**Parameters:**
- `instruments`: List like ["NSE:TCS", "NSE:RELIANCE"]

**Returns:**
```python
{
    "NSE:TCS": {
        "last_price": 4000.0,
        "change": 50.0,
        "change_percent": 1.25,
        "ohlc": {"open": 3950, "high": 4020, "low": 3940, "close": 3950},
    },
    ...
}
```

##### `async list_tools() -> list[str]`

Lists available MCP tools.

---

## Ingestion

### ingest_news

Main ingestion pipeline.

```python
from src.data.ingestion import ingest_news

stats = await ingest_news(symbols=["TCS", "RELIANCE"], limit=10)
```

#### Parameters

- `symbols`: Optional list of stock symbols to fetch news for
- `limit`: Number of articles per source

#### Returns

```python
@dataclass
class IngestionStats:
    articles_fetched: int
    chunks_stored: int
    errors: list[str]
```

---

## Utility Functions

### News Tools

```python
from src.agents.tools.news_tools import (
    search_stock_news,
    ensure_news_indexed,
    get_news_context_string,
)

# Search for news
articles = search_stock_news(["TCS", "INFY"], top_k=3)

# Ensure news is indexed (fetches if needed)
stats = await ensure_news_indexed(["TCS"])

# Format for LLM context
context = get_news_context_string(articles)
```

### Portfolio Tools

```python
from src.agents.tools.portfolio_tools import (
    fetch_holdings,
    analyze_performers,
)

# Fetch holdings
result = await fetch_holdings(kite_client)
# Returns: {"holdings": [...], "total_value": float, "total_pnl": float, "error": str | None}

# Analyze performers
worst_3 = analyze_performers(holdings, analysis_type="worst", top_n=3)
best_3 = analyze_performers(holdings, analysis_type="best", top_n=3)
```

---

## Scoring Functions

### analyze_fundamentals

```python
from src.agents.workflows.fundamental_analysis import (
    analyze_fundamentals,
    FundamentalScore,
)

score = analyze_fundamentals(fundamental_data)
print(f"Total Score: {score.total_score}/10")
print(f"Recommendation: {score.recommendation}")
```

#### FundamentalScore

```python
@dataclass
class FundamentalScore:
    valuation_score: int       # -2 to +2
    profitability_score: int   # -2 to +2
    growth_score: int          # -2 to +2
    financial_health_score: int  # -2 to +2
    promoter_score: int        # -2 to +2

    valuation_notes: list[str]
    profitability_notes: list[str]
    growth_notes: list[str]
    financial_health_notes: list[str]
    promoter_notes: list[str]

    @property
    def total_score(self) -> int:
        """Total score from -10 to +10."""

    @property
    def recommendation(self) -> str:
        """STRONG BUY, BUY, HOLD, SELL, or STRONG SELL."""
```
