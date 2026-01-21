# Portfolio Copilot

An AI-powered portfolio analysis assistant for Zerodha Kite users, built to learn MCP + LLM + RAG + Agentic AI fundamentals.

## Features

- **Natural Language Queries**: Ask questions about your portfolio in plain English
- **Multi-Agent System**: Specialized AI agents for different analysis tasks
- **Fundamental Analysis**: Stock evaluation using screener.in data with buy/hold/sell recommendations
- **News Integration**: RAG-powered news search from Indian financial sources
- **Real-time Data**: Live portfolio data via Zerodha Kite MCP integration

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Interface (Rich)                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   Agent Orchestrator                         │
│  • Query pattern detection                                   │
│  • Route to appropriate agent                                │
└────────┬─────────────┬─────────────┬─────────────┬─────────┘
         │             │             │             │
         ▼             ▼             ▼             ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Portfolio  │ │   Stock     │ │   Market    │ │ Fundamental │
│  Analysis   │ │  Research   │ │   Context   │ │  Analysis   │
│   Agent     │ │   Agent     │ │   Agent     │ │   Agent     │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
         │             │             │             │
         └─────────────┴──────┬──────┴─────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Kite MCP      │  │   RAG System    │  │  Screener.in    │
│   (Holdings,    │  │   (ChromaDB +   │  │   (Fundamental  │
│    Quotes)      │  │    News)        │  │    Data)        │
└─────────────────┘  └─────────────────┘  └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Claude LLM     │
                    │  (Synthesis)    │
                    └─────────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12 |
| LLM | Claude Sonnet 4 (Anthropic) |
| Agent Framework | LangGraph |
| Vector Database | ChromaDB |
| Embeddings | Sentence Transformers (all-MiniLM-L6-v2) |
| Broker Integration | Zerodha Kite MCP |
| CLI | Rich |
| HTTP Client | httpx |
| Web Scraping | BeautifulSoup4, lxml |

## Installation

### Prerequisites

- Python 3.12+
- [Poetry](https://python-poetry.org/docs/#installation)
- Zerodha Kite account with API access
- Anthropic API key

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/portfolio-copilot.git
cd portfolio-copilot

# Install dependencies
poetry install

# Copy environment template and fill in your keys
cp .env.example .env
```

### Environment Variables

```bash
# .env file
ANTHROPIC_API_KEY=sk-ant-xxx        # Required: Claude API key
KITE_API_KEY=xxx                     # Required: Zerodha Kite API key
KITE_API_SECRET=xxx                  # Required: Zerodha Kite API secret
```

## Usage

### Start the CLI

```bash
poetry run python -m src.ui.cli
```

### Available Commands

| Command | Description |
|---------|-------------|
| `login` | Authenticate with Zerodha Kite |
| `holdings` | Display portfolio holdings table |
| `analyze` | Run portfolio analysis agent |
| `research` | Run stock research agent |
| `context` | Run market context agent |
| `watchlist` | Run watchlist suggestion agent |
| `fundamentals` | Run fundamental analysis (screener.in) |
| `ingest` | Fetch and index news articles |
| `search` | Search indexed news |
| `status` | Show vector store status |
| `clear` | Clear conversation history |
| `help` | Show help message |
| `exit` | Exit the application |

### Natural Language Queries

The orchestrator auto-detects query intent and routes to the appropriate agent:

```
You> Analyze my worst performing stocks
    → Portfolio Analysis Agent

You> Tell me about Reliance
    → Stock Research Agent

You> Why is my portfolio down today?
    → Market Context Agent

You> Suggest stocks for my watchlist
    → Watchlist Suggestion Agent

You> Is TCS a good buy?
    → Fundamental Analysis Agent
```

## Agents

### 1. Portfolio Analysis Agent

Analyzes your portfolio holdings to identify best/worst performers.

**Workflow:**
```
fetch_portfolio → analyze_performers → fetch_news → generate_insights
```

**Triggers:**
- "Analyze my portfolio"
- "What are my worst performing stocks?"
- "Show my best performers"

### 2. Stock Research Agent

Researches individual stocks with price data and news.

**Workflow:**
```
extract_symbol → check_holdings → get_price → fetch_news → generate_report
```

**Triggers:**
- "Tell me about Reliance"
- "Research TCS stock"
- "What's happening with INFY?"

### 3. Market Context Agent

Explains market movements affecting your portfolio.

**Workflow:**
```
fetch_portfolio → identify_movers → fetch_news → generate_context
```

**Triggers:**
- "Why is my portfolio down?"
- "What happened to the market today?"
- "Explain today's market movement"

### 4. Watchlist Suggestion Agent

Suggests stocks for your watchlist based on portfolio analysis.

**Workflow:**
```
analyze_portfolio → identify_opportunities → fetch_news → generate_suggestions
```

**Triggers:**
- "Suggest stocks for my watchlist"
- "What stocks should I watch?"
- "What should I invest in next?"

### 5. Fundamental Analysis Agent

Evaluates stocks using screener.in data with buy/hold/sell recommendations.

**Workflow:**
```
extract_symbol → fetch_fundamentals → check_holdings → fetch_news → generate_analysis
```

**Data Sources:**
- **Screener.in**: P/E, P/B, ROE, ROCE, debt/equity, promoter holding, pros/cons
- **Holdings**: Checks if you own the stock
- **News (RAG)**: Recent developments
- **Claude**: Synthesizes comprehensive analysis

**Scoring System:**
| Category | Score Range | Metrics |
|----------|-------------|---------|
| Valuation | -2 to +2 | P/E, P/B, dividend yield |
| Profitability | -2 to +2 | ROE, ROCE |
| Growth | -2 to +2 | Revenue growth, profit growth (3yr) |
| Financial Health | -2 to +2 | Debt/equity, current ratio |
| Promoter Activity | -2 to +2 | Holding %, quarterly change |

**Recommendations:**
| Total Score | Recommendation |
|-------------|----------------|
| 5 to 10 | STRONG BUY |
| 2 to 4 | BUY |
| -1 to 1 | HOLD |
| -4 to -2 | SELL |
| -10 to -5 | STRONG SELL |

**Triggers:**
- "Is Reliance a good buy?"
- "Fundamentals of TCS"
- "Should I buy HDFC Bank?"
- "PE ratio of Wipro"

## RAG System

### News Sources

- **MoneyControl**: Indian financial news
- **Economic Times**: Market news and analysis

### Ingesting News

```bash
# In CLI
You> ingest
Stock symbols (comma-separated, or empty for general news): TCS, RELIANCE
```

### Searching News

```bash
You> search
Search query: TCS quarterly results
```

## Project Structure

```
portfolio-copilot/
├── src/
│   ├── agents/
│   │   ├── orchestrator.py      # Query routing
│   │   ├── tools/
│   │   │   ├── news_tools.py    # RAG search tools
│   │   │   └── portfolio_tools.py
│   │   └── workflows/
│   │       ├── portfolio_analysis.py
│   │       ├── stock_research.py
│   │       ├── market_context.py
│   │       ├── watchlist_suggestion.py
│   │       └── fundamental_analysis.py
│   ├── data/
│   │   ├── ingestion.py         # News ingestion pipeline
│   │   └── scrapers/
│   │       ├── moneycontrol.py
│   │       ├── economictimes.py
│   │       └── screener.py      # Fundamental data
│   ├── llm/
│   │   ├── claude.py            # Claude API wrapper
│   │   └── prompts.py
│   ├── mcp/
│   │   └── kite_client.py       # Zerodha MCP client
│   ├── rag/
│   │   ├── embeddings.py        # Sentence transformers
│   │   ├── vector_store.py      # ChromaDB
│   │   ├── chunking.py
│   │   └── retriever.py
│   └── ui/
│       └── cli.py               # Rich CLI interface
├── data/
│   └── chroma/                  # Vector store (gitignored)
├── pyproject.toml
├── README.md
└── CLAUDE.md                    # Project instructions
```

## Example Session

```
$ poetry run python -m src.ui.cli

Portfolio Copilot
Type 'help' for commands, or ask me about your portfolio!

You> login
Opening browser for Kite login...

You> holdings
┌──────────┬─────┬───────────┬─────────┬──────────┬──────────┐
│ Symbol   │ Qty │ Avg Price │ LTP     │ P&L      │ Change % │
├──────────┼─────┼───────────┼─────────┼──────────┼──────────┤
│ TCS      │ 10  │ 3,500.00  │ 4,000   │ 5,000.00 │ 1.2%     │
│ RELIANCE │ 5   │ 2,400.00  │ 2,300   │ -500.00  │ -0.5%    │
└──────────┴─────┴───────────┴─────────┴──────────┴──────────┘

You> Is TCS a good buy?

Using Fundamental Analysis

# TCS Fundamental Analysis

## Summary
TCS is India's largest IT services company...

## Recommendation: HOLD

Since you already own 10 shares with ₹5,000 profit:
- Hold your current position
- Consider profit booking at ₹4,200+ levels
...

You> Why is my portfolio down today?

Using Market Context

Your portfolio declined ₹500 today primarily due to:
1. Reliance down 0.5% on crude oil price concerns...
```

## Disclaimer

This tool is for **educational and informational purposes only**. It is:

- **NOT** investment advice
- **NOT** a trading recommendation system
- **NOT** a substitute for professional financial advice

Always consult a qualified financial advisor before making investment decisions. The developers are not responsible for any financial losses incurred from using this tool.

## License

MIT License - See [LICENSE](LICENSE) for details.

## Acknowledgments

- [Anthropic](https://anthropic.com) for Claude API
- [Zerodha](https://zerodha.com) for Kite Connect API
- [Screener.in](https://screener.in) for fundamental data
- [LangChain/LangGraph](https://langchain.com) for agent framework
