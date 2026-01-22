# Architecture Documentation

## System Overview

Portfolio Copilot is a multi-agent AI system that combines:
- **MCP (Model Context Protocol)** for broker data integration
- **RAG (Retrieval Augmented Generation)** for news context
- **LangGraph** for agentic workflows
- **Claude LLM** for natural language understanding and synthesis

## Component Architecture

### 1. CLI Layer (`src/ui/cli.py`)

The entry point for user interaction using Rich library.

```python
# Main loop
async def async_main():
    async with KiteClient() as client:
        assistant = PortfolioAssistant(client)
        while True:
            user_input = await get_input()
            if is_command(user_input):
                await handle_command(user_input)
            else:
                await handle_chat(user_input, assistant, client)
```

**Responsibilities:**
- User input handling
- Command routing
- Response rendering (Markdown via Rich)
- Session management

### 2. Agent Orchestrator (`src/agents/orchestrator.py`)

Routes queries to appropriate specialized agents using regex pattern matching.

```python
class AgentOrchestrator:
    def should_use_agent(self, query: str) -> tuple[bool, str | None]:
        # Pattern matching for each agent type
        portfolio_patterns = [r"analyz\w*\s+(my\s+)?portfolio", ...]
        fundamental_patterns = [r"(is|are)\s+\w+\s+(a\s+)?(good|bad)\s+(buy|stock)", ...]
        # ... returns (should_use, agent_type)

    async def run_agent(self, agent_type: str, query: str) -> dict:
        # Dispatch to appropriate agent
```

**Agent Types:**
| Type | Description | Patterns |
|------|-------------|----------|
| `portfolio_analysis` | Portfolio performance | "analyze portfolio", "worst stocks" |
| `stock_research` | Individual stock research | "tell me about X", "research X" |
| `market_context` | Market movement explanation | "why portfolio down", "market today" |
| `watchlist` | Stock suggestions | "suggest stocks", "what to buy" |
| `fundamental_analysis` | Fundamental evaluation | "is X good buy", "fundamentals of X" |

### 3. Agent Workflows (`src/agents/workflows/`)

Each agent is a LangGraph state machine with nodes and edges.

#### Workflow Structure

```python
def create_workflow_graph() -> StateGraph:
    workflow = StateGraph(dict)

    # Add nodes (functions that process state)
    workflow.add_node("step1", step1_node)
    workflow.add_node("step2", step2_node)
    workflow.add_node("step3", step3_node)

    # Define edges (control flow)
    workflow.set_entry_point("step1")
    workflow.add_edge("step1", "step2")
    workflow.add_conditional_edges("step2", condition_fn, {...})
    workflow.add_edge("step3", END)

    return workflow.compile()
```

#### Node Types

1. **Data Fetching Nodes** - Retrieve external data
   ```python
   async def fetch_portfolio_node(state, config: RunnableConfig):
       client = config["configurable"]["kite_client"]
       holdings = await client.get_holdings()
       return {**state, "holdings": holdings}
   ```

2. **Processing Nodes** - Transform/analyze data
   ```python
   def analyze_performers_node(state):
       holdings = state["holdings"]
       sorted_by_return = sorted(holdings, key=lambda x: x["return_pct"])
       return {**state, "worst_performers": sorted_by_return[:3]}
   ```

3. **LLM Synthesis Nodes** - Generate natural language output
   ```python
   def generate_insights_node(state):
       prompt = format_prompt(state)
       response = anthropic.messages.create(model=MODEL, messages=[...])
       return {**state, "insights": response.content[0].text}
   ```

### 4. MCP Integration (`src/mcp/kite_client.py`)

Connects to Zerodha Kite via Model Context Protocol.

```python
class KiteClient:
    async def get_holdings(self) -> list[dict]:
        """Fetch portfolio holdings via MCP."""

    async def get_quotes(self, instruments: list[str]) -> dict:
        """Get real-time quotes for instruments."""

    async def login(self) -> LoginResult:
        """Initiate OAuth login flow."""
```

**MCP Tools Used:**
- `get_holdings` - Portfolio holdings
- `get_positions` - Open positions
- `get_quotes` - Real-time prices
- `get_orders` - Order history

### 5. RAG System (`src/rag/`)

Vector-based news retrieval using ChromaDB.

#### Components

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Scrapers      │ --> │   Chunking      │ --> │   Embeddings    │
│ (MC, ET)        │     │   (512 tokens)  │     │ (MiniLM-L6-v2)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Retriever     │ <-- │   Search        │ <-- │   ChromaDB      │
│   (top-k)       │     │   (cosine sim)  │     │   (vector store)│
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

#### Embedding Model

```python
# all-MiniLM-L6-v2: 384 dimensions, fast inference
class EmbeddingModel:
    def __init__(self):
        self._model = SentenceTransformer("all-MiniLM-L6-v2")

    def embed(self, text: str) -> list[float]:
        return self._model.encode(text).tolist()
```

#### Chunking Strategy

```python
class TokenChunker:
    def __init__(self, chunk_size=512, overlap=50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[str]:
        # Split into overlapping chunks for context preservation
```

### 6. Screener.in Scraper (`src/data/scrapers/screener.py`)

Web scraper for fundamental data.

```python
@dataclass
class FundamentalData:
    symbol: str
    name: str
    market_cap: float      # in Cr
    pe_ratio: float
    pb_ratio: float
    roe: float             # Return on Equity %
    roce: float            # Return on Capital Employed %
    debt_to_equity: float
    promoter_holding: float
    promoter_holding_change: float
    pros: list[str]        # Screener's pros
    cons: list[str]        # Screener's cons

class ScreenerScraper:
    async def get_fundamentals(self, symbol: str) -> FundamentalData:
        url = f"https://www.screener.in/company/{symbol}/"
        response = await self._client.get(url)
        soup = BeautifulSoup(response.text, "lxml")
        # Extract ratios, shareholding, pros/cons
```

### 7. LLM Integration (`src/llm/claude.py`)

Claude API wrapper with tool calling support.

```python
class PortfolioAssistant:
    def __init__(self, kite_client: KiteClient):
        self._client = Anthropic()
        self._kite = kite_client
        self._tools = self._build_tools()

    async def chat(self, message: str) -> AsyncIterator[Event]:
        # Stream responses with tool use
        async with self._client.messages.stream(...) as stream:
            async for event in stream:
                yield self._process_event(event)
```

## Data Flow

### Query Processing Flow

```
User Query
    │
    ▼
┌─────────────────────┐
│  Orchestrator       │
│  (Pattern Match)    │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │ Agent Type? │
    └──────┬──────┘
           │
    ┌──────┴──────────────────────────┐
    │                                  │
    ▼                                  ▼
┌───────────┐                    ┌───────────┐
│ Specific  │                    │ General   │
│ Agent     │                    │ Chat      │
│ Workflow  │                    │ (Claude)  │
└─────┬─────┘                    └─────┬─────┘
      │                                │
      ▼                                ▼
┌───────────┐                    ┌───────────┐
│ LangGraph │                    │ Tool      │
│ Nodes     │                    │ Calling   │
└─────┬─────┘                    └─────┬─────┘
      │                                │
      └────────────┬───────────────────┘
                   │
                   ▼
            ┌────────────┐
            │  Response  │
            │  (Markdown)│
            └────────────┘
```

### Fundamental Analysis Flow

```
"Is TCS a good buy?"
         │
         ▼
┌─────────────────────┐
│ extract_symbol_node │  → symbol = "TCS"
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────┐
│ fetch_fundamentals_node │  → screener.in API
└──────────┬──────────────┘    P/E, ROE, ROCE, etc.
           │
           ▼
┌─────────────────────┐
│ check_holdings_node │  → Kite MCP
└──────────┬──────────┘    in_portfolio: true/false
           │
           ▼
┌─────────────────────┐
│ fetch_news_node     │  → ChromaDB RAG
└──────────┬──────────┘    Recent news articles
           │
           ▼
┌─────────────────────────┐
│ generate_analysis_node  │  → Claude LLM
└──────────┬──────────────┘    Synthesize all data
           │
           ▼
    Comprehensive Analysis
    with Recommendation
```

## Scoring Algorithm

The fundamental analysis uses a weighted scoring system:

```python
@dataclass
class FundamentalScore:
    valuation_score: int      # -2 to +2
    profitability_score: int  # -2 to +2
    growth_score: int         # -2 to +2
    financial_health_score: int  # -2 to +2
    promoter_score: int       # -2 to +2

    @property
    def total_score(self) -> int:
        return sum([
            self.valuation_score,
            self.profitability_score,
            self.growth_score,
            self.financial_health_score,
            self.promoter_score
        ])  # Range: -10 to +10

    @property
    def recommendation(self) -> str:
        score = self.total_score
        if score >= 5: return "STRONG BUY"
        if score >= 2: return "BUY"
        if score >= -1: return "HOLD"
        if score >= -4: return "SELL"
        return "STRONG SELL"
```

### Scoring Criteria

| Category | Metric | Score | Condition |
|----------|--------|-------|-----------|
| Valuation | P/E | +2 | < 15 |
| | | +1 | 15-25 |
| | | -1 | > 40 |
| | P/B | +1 | < 2 |
| | | -1 | > 5 |
| | Dividend Yield | +1 | > 2% |
| Profitability | ROE | +2 | >= 20% |
| | | +1 | 15-20% |
| | | -1 | < 10% |
| | ROCE | +1 | >= 20% |
| | | -1 | < 10% |
| Growth | Revenue (3yr) | +1 | >= 15% |
| | | -1 | < 5% |
| | Profit (3yr) | +1 | >= 15% |
| | | -1 | < 5% |
| Financial | D/E Ratio | +2 | < 0.5 |
| | | +1 | 0.5-1.0 |
| | | -2 | > 2.0 |
| | Current Ratio | +1 | >= 2 |
| | | -1 | < 1 |
| Promoter | Holding | +1 | >= 60% |
| | | -1 | < 30% |
| | Change | +1 | Increasing |
| | | -1 | Decreasing > 2% |

## Error Handling

### Graceful Degradation

Each workflow handles failures at node level:

```python
async def fetch_news_node(state):
    try:
        news = search_stock_news([state["symbol"]])
        return {**state, "news_articles": news}
    except Exception:
        # Continue without news rather than failing
        return {**state, "news_articles": []}
```

### Conditional Edges

Workflows skip to synthesis if errors occur:

```python
def should_continue(state):
    if state.get("error"):
        return "generate_report"  # Skip to final node
    return "continue"

workflow.add_conditional_edges(
    "fetch_data",
    should_continue,
    {"continue": "process_data", "generate_report": "generate_report"}
)
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |

### Model Configuration

```python
# LLM Model
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 2048

# Embedding Model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# ChromaDB
COLLECTION_NAME = "portfolio_news"
PERSIST_DIRECTORY = "data/chroma"

# Chunking
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
```

## Testing

### Unit Testing Agents

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock

def test_fundamental_analysis():
    mock_client = MagicMock()
    mock_client.get_holdings = AsyncMock(return_value=[])

    agent = FundamentalAnalysisAgent(mock_client)
    result = asyncio.run(agent.analyze("Is TCS good?"))

    assert "TCS" in result
    assert any(word in result for word in ["BUY", "HOLD", "SELL"])
```

### Integration Testing

```python
async def test_full_workflow():
    async with KiteClient() as client:
        orchestrator = AgentOrchestrator(client)

        # Test pattern detection
        should_use, agent_type = orchestrator.should_use_agent("Is TCS good?")
        assert should_use is True
        assert agent_type == "fundamental_analysis"

        # Test full workflow
        result = await orchestrator.run_agent("fundamental_analysis", "Is TCS good?")
        assert "response" in result
```
