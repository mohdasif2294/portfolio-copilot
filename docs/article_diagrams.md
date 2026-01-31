# Diagrams for Medium Article

Render these at [mermaid.live](https://mermaid.live) and export as PNG/SVG for your article.

---

## 1. Overall System Architecture

```mermaid
flowchart TB
    subgraph UI["User Interface"]
        CLI["CLI (Rich)"]
    end

    subgraph Orchestrator["Agent Orchestrator"]
        QD["Query Detector<br/>(Pattern Matching)"]
        Router["Agent Router"]
    end

    subgraph Agents["LangGraph Agents"]
        PA["Portfolio<br/>Analysis"]
        SR["Stock<br/>Research"]
        MC["Market<br/>Context"]
        FA["Fundamental<br/>Analysis"]
        WL["Watchlist<br/>Suggestion"]
    end

    subgraph LLM["LLM Layer"]
        Claude["Claude Sonnet 4<br/>(Anthropic API)"]
        Tools["Tool Definitions<br/>(8 tools)"]
        Streaming["Streaming<br/>Response Handler"]
    end

    subgraph RAG["RAG Pipeline"]
        Retriever["News Retriever"]
        VectorDB["ChromaDB<br/>(Vector Store)"]
        Embeddings["Sentence Transformers<br/>(all-MiniLM-L6-v2)"]
    end

    subgraph DataSources["External Data Sources"]
        Kite["Zerodha Kite<br/>(via MCP)"]
        MC_Scraper["MoneyControl"]
        ET_Scraper["Economic Times"]
        Screener["Screener.in"]
    end

    CLI --> QD
    QD --> Router
    Router --> PA & SR & MC & FA & WL

    PA & SR & MC & FA & WL --> Claude
    Claude <--> Tools
    Tools --> Streaming

    PA & SR & MC --> Retriever
    Retriever --> VectorDB
    VectorDB --> Embeddings

    Tools --> Kite
    MC_Scraper & ET_Scraper --> VectorDB
    Screener --> FA

    Streaming --> CLI

    style Claude fill:#6366f1,color:#fff
    style VectorDB fill:#10b981,color:#fff
    style Kite fill:#f59e0b,color:#fff
```

---

## 2. LangGraph Workflow: Portfolio Analysis Agent

```mermaid
flowchart TD
    Start((Start)) --> FP

    subgraph FP["1. Fetch Portfolio"]
        FP_Action["Call Kite MCP<br/>get_holdings()"]
        FP_State["State Update:<br/>holdings, total_value, total_pnl"]
    end

    FP --> Check{Error?}
    Check -->|Yes| GI
    Check -->|No| AP

    subgraph AP["2. Analyze Performers"]
        AP_Action["Sort by return %<br/>Extract top/bottom 3"]
        AP_State["State Update:<br/>target_stocks"]
    end

    AP --> FN

    subgraph FN["3. Fetch News"]
        FN_Index["Ensure news indexed<br/>(scrape if needed)"]
        FN_Search["Semantic search<br/>for target stocks"]
        FN_State["State Update:<br/>news_context"]
    end

    FN --> GI

    subgraph GI["4. Generate Insights"]
        GI_Prompt["Build analysis prompt<br/>with all context"]
        GI_LLM["Claude generates<br/>natural language insights"]
        GI_State["State Update:<br/>insights"]
    end

    GI --> End((End))

    style FP fill:#3b82f6,color:#fff
    style AP fill:#8b5cf6,color:#fff
    style FN fill:#10b981,color:#fff
    style GI fill:#f59e0b,color:#fff
```

**State Schema:**
```python
class PortfolioState(TypedDict):
    query: str
    analysis_type: str        # "best" | "worst"
    holdings: list            # From Kite MCP
    total_value: float
    total_pnl: float
    target_stocks: list       # Top/bottom performers
    news_context: list        # From RAG
    insights: str             # Final LLM output
    error: str | None
    steps_completed: list     # Audit trail
```

---

## 3. RAG Pipeline Flowchart

```mermaid
flowchart LR
    subgraph Ingestion["Data Ingestion"]
        Sources["News Sources<br/>(MoneyControl, ET)"]
        Fetch["Async Fetch<br/>(httpx + BeautifulSoup)"]
        Filter["Filter<br/>(min 50 chars)"]
    end

    subgraph Chunking["Chunking"]
        Strategy{"Strategy?"}
        Tokens["Token-based<br/>(512 words, 50 overlap)"]
        Sentences["Sentence-based<br/>(respects boundaries)"]
        Paragraphs["Paragraph-based<br/>(merges small paras)"]
    end

    subgraph Embedding["Embedding"]
        Model["all-MiniLM-L6-v2<br/>(384 dimensions)"]
        Batch["Batch Processing"]
    end

    subgraph Storage["Vector Storage"]
        ChromaDB["ChromaDB<br/>(Persistent)"]
        Metadata["Metadata:<br/>symbol, source, date,<br/>title, url, chunk_idx"]
    end

    subgraph Retrieval["Retrieval"]
        Query["User Query"]
        Embed["Embed Query"]
        Search["Cosine Similarity<br/>Search"]
        FilterMeta["Filter by:<br/>symbol, source"]
        Threshold["Score Threshold<br/>(min: 0.3)"]
        Format["Format for LLM<br/>(with citations)"]
    end

    Sources --> Fetch --> Filter
    Filter --> Strategy
    Strategy --> Tokens & Sentences & Paragraphs
    Tokens & Sentences & Paragraphs --> Model
    Model --> Batch --> ChromaDB
    ChromaDB --- Metadata

    Query --> Embed --> Search
    ChromaDB --> Search
    Search --> FilterMeta --> Threshold --> Format

    style ChromaDB fill:#10b981,color:#fff
    style Model fill:#6366f1,color:#fff
```

---

## 4. Tool Calling Loop (LLM Integration)

```mermaid
sequenceDiagram
    participant User
    participant Assistant as PortfolioAssistant
    participant Claude as Claude API
    participant Tools as Tool Executor
    participant Kite as Kite MCP
    participant RAG as RAG System

    User->>Assistant: "What's my portfolio?"
    Assistant->>Assistant: Add to history

    loop Until no more tool calls
        Assistant->>Claude: Stream request<br/>(system prompt + tools + history)

        Claude-->>Assistant: Stream text chunks
        Assistant-->>User: Display streaming text

        alt stop_reason == "tool_use"
            Claude->>Assistant: tool_use blocks

            loop For each tool call
                Assistant->>Tools: Execute tool

                alt Portfolio tool
                    Tools->>Kite: MCP call
                    Kite-->>Tools: Result
                else RAG tool
                    Tools->>RAG: search_news()
                    RAG-->>Tools: Results
                end

                Tools-->>Assistant: JSON result
            end

            Assistant->>Assistant: Add tool results to history
        else stop_reason == "end_turn"
            Assistant-->>User: Final response
        end
    end
```

**Tool Definitions (8 total):**
```
Portfolio Tools (6):
├── get_holdings      - DEMAT holdings
├── get_positions     - Trading positions
├── get_margins       - Account margins
├── get_quotes        - Real-time quotes
├── get_ltp           - Last traded price
└── search_instruments - Symbol search

RAG Tools (2):
├── search_news       - Semantic search
└── ingest_stock_news - Fetch & index news
```

---

## 5. Query Routing / Orchestrator

```mermaid
flowchart TD
    Query["User Query"] --> Detect["Pattern Detection<br/>(25+ regex patterns)"]

    Detect --> PA_Pat{"Portfolio patterns?<br/>'worst performer'<br/>'best stocks'<br/>'portfolio analysis'"}
    Detect --> SR_Pat{"Research patterns?<br/>'tell me about X'<br/>'analyze X stock'<br/>'what is X'"}
    Detect --> MC_Pat{"Market patterns?<br/>'why did portfolio drop'<br/>'market today'<br/>'what happened'"}
    Detect --> FA_Pat{"Fundamental patterns?<br/>'should I buy'<br/>'fundamental analysis'<br/>'is X good'"}
    Detect --> WL_Pat{"Watchlist patterns?<br/>'suggest stocks'<br/>'what to buy'<br/>'recommendations'"}

    PA_Pat -->|Yes| PA_Agent["Portfolio Analysis<br/>Agent"]
    SR_Pat -->|Yes| SR_Agent["Stock Research<br/>Agent"]
    MC_Pat -->|Yes| MC_Agent["Market Context<br/>Agent"]
    FA_Pat -->|Yes| FA_Agent["Fundamental Analysis<br/>Agent"]
    WL_Pat -->|Yes| WL_Agent["Watchlist<br/>Agent"]

    PA_Pat & SR_Pat & MC_Pat & FA_Pat & WL_Pat -->|No match| Default["Default: Chat Mode<br/>(Direct LLM)"]

    style PA_Agent fill:#3b82f6,color:#fff
    style SR_Agent fill:#8b5cf6,color:#fff
    style MC_Agent fill:#10b981,color:#fff
    style FA_Agent fill:#f59e0b,color:#fff
    style WL_Agent fill:#ec4899,color:#fff
```

---

## 6. Chunking Strategies Comparison

```mermaid
flowchart LR
    subgraph Input["Input: News Article"]
        Text["'The Reserve Bank of India announced<br/>new monetary policy measures today.<br/>Interest rates remain unchanged at 6.5%.<br/>The decision impacts banking stocks...'"]
    end

    subgraph Token["Token-based Chunking"]
        T1["Chunk 1: words 0-511"]
        T2["Chunk 2: words 462-973<br/>(50 word overlap)"]
        T3["Chunk 3: words 924-1435"]
    end

    subgraph Sentence["Sentence-based Chunking"]
        S1["Chunk 1: Complete sentences<br/>until ~512 words"]
        S2["Chunk 2: Next batch of<br/>complete sentences"]
    end

    subgraph Paragraph["Paragraph-based Chunking"]
        P1["Chunk 1: Full paragraphs<br/>(merged if small)"]
        P2["Chunk 2: Large para →<br/>sentence fallback"]
    end

    Input --> Token & Sentence & Paragraph

    style Token fill:#ef4444,color:#fff
    style Sentence fill:#10b981,color:#fff
    style Paragraph fill:#3b82f6,color:#fff
```

| Strategy | Pros | Cons | Best For |
|----------|------|------|----------|
| **Tokens** | Consistent size, predictable | May split mid-sentence | Large documents, batch processing |
| **Sentences** | Preserves meaning | Variable chunk sizes | News articles, Q&A |
| **Paragraphs** | Preserves context | Can be too large | Long-form content, reports |

---

## 7. Fundamental Analysis Scoring

```mermaid
flowchart TD
    subgraph Input["Stock Data"]
        Screener["Screener.in API<br/>(P/E, ROE, Debt, etc.)"]
        News["Recent News<br/>(RAG search)"]
    end

    subgraph Scoring["5-Dimension Scoring"]
        V["Valuation<br/>(-10 to +10)"]
        P["Profitability<br/>(-10 to +10)"]
        G["Growth<br/>(-10 to +10)"]
        F["Financial Health<br/>(-10 to +10)"]
        PR["Promoter Holding<br/>(-10 to +10)"]
    end

    subgraph Output["Recommendation"]
        Total["Total Score<br/>(sum of 5 dimensions)"]

        SB["Score > 15:<br/>STRONG BUY"]
        B["Score 5-15:<br/>BUY"]
        H["Score -5 to 5:<br/>HOLD"]
        S["Score -15 to -5:<br/>SELL"]
        SS["Score < -15:<br/>STRONG SELL"]
    end

    Screener --> V & P & G & F & PR
    News --> V
    V & P & G & F & PR --> Total
    Total --> SB & B & H & S & SS

    style Total fill:#6366f1,color:#fff
    style SB fill:#10b981,color:#fff
    style SS fill:#ef4444,color:#fff
```

---

## How to Export for Medium

1. **Go to [mermaid.live](https://mermaid.live)**
2. **Paste each diagram code** (between the ```mermaid tags)
3. **Click "Actions" → "Export PNG"** (or SVG for crisp scaling)
4. **Recommended settings:**
   - Background: White or Transparent
   - Scale: 2x for retina displays
5. **Upload to Medium** using the image upload feature

---

## Alternative: ASCII Diagrams

If you prefer simple ASCII for code blocks:

### Tool Calling Loop (ASCII)
```
┌─────────┐    ┌─────────────┐    ┌──────────┐
│  User   │───▶│  Assistant  │───▶│  Claude  │
└─────────┘    └─────────────┘    └──────────┘
                     │                  │
                     │   tool_use?      │
                     │◀─────────────────┤
                     │                  │
                     ▼                  │
              ┌─────────────┐           │
              │Tool Executor│           │
              └─────────────┘           │
                     │                  │
        ┌────────────┼────────────┐     │
        ▼            ▼            ▼     │
   ┌────────┐  ┌──────────┐  ┌─────┐   │
   │Kite MCP│  │RAG Search│  │ ... │   │
   └────────┘  └──────────┘  └─────┘   │
        │            │            │     │
        └────────────┼────────────┘     │
                     │                  │
                     │  tool_results    │
                     │─────────────────▶│
                     │                  │
                     │   final text     │
                     │◀─────────────────┤
                     ▼
               ┌─────────┐
               │  User   │
               └─────────┘
```

### RAG Pipeline (ASCII)
```
INGESTION:
┌──────────────┐   ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ News Sources │──▶│  Fetch  │──▶│  Filter  │──▶│  Chunk   │──▶│  Embed   │
│ (MC, ET)     │   │ (async) │   │ (>50chr) │   │ (512w)   │   │ (384d)   │
└──────────────┘   └─────────┘   └──────────┘   └──────────┘   └──────────┘
                                                                     │
                                                                     ▼
                                                              ┌──────────┐
                                                              │ ChromaDB │
                                                              │ + meta   │
                                                              └──────────┘
                                                                     │
RETRIEVAL:                                                           │
┌───────────┐   ┌─────────┐   ┌──────────┐   ┌──────────┐           │
│   Query   │──▶│  Embed  │──▶│  Search  │◀──────────────────────────┘
│           │   │         │   │ (cosine) │
└───────────┘   └─────────┘   └──────────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │ Filter/Score │
                            │ (>0.3, meta) │
                            └──────────────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │ Format for   │
                            │     LLM      │
                            └──────────────┘
```

---

## 8. CLI Mockups

Use these for your Medium article to show the application in action.

### Startup & Login Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Terminal - Portfolio Copilot                                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  $ python -m src.ui.cli                                                      │
│                                                                              │
│  Portfolio Copilot                                                           │
│  Type 'help' for commands, or ask me about your portfolio!                   │
│                                                                              │
│  Not logged in. Run 'login' to connect to Kite.                              │
│                                                                              │
│  You: login                                                                  │
│  ⠋ Getting login URL...                                                      │
│                                                                              │
│  Warning: AI systems are unpredictable.                                      │
│  By continuing, you interact with Zerodha at your own risk.                  │
│                                                                              │
│  Login URL: https://kite.zerodha.com/connect/login?...                       │
│                                                                              │
│  Open in browser? [y/n] (y): y                                               │
│  Browser opened. Complete login there.                                       │
│                                                                              │
│  Press Enter after completing login in browser...                            │
│  ⠋ Verifying login...                                                        │
│  Successfully logged in as Asif Khan!                                        │
│                                                                              │
│  You: █                                                                      │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Holdings Display

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Terminal - Portfolio Copilot                                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  You: holdings                                                               │
│  ⠋ Fetching holdings from Kite...                                            │
│                                                                              │
│  ┌─────────────────────── Portfolio Holdings ────────────────────────┐       │
│  │ Symbol      │  Qty │ Avg Price │    LTP │       P&L │  Change % │       │
│  ├─────────────┼──────┼───────────┼────────┼───────────┼───────────┤       │
│  │ RELIANCE    │   10 │   2,450.00│ 2,892.50│   +4,425.00│    +1.23% │       │
│  │ TCS         │    5 │   3,200.00│ 4,125.75│   +4,628.75│    +0.85% │       │
│  │ INFY        │   15 │   1,450.00│ 1,523.40│   +1,101.00│    -0.42% │       │
│  │ HDFCBANK    │    8 │   1,650.00│ 1,712.30│     +498.40│    +0.65% │       │
│  │ GABRIEL     │  100 │     425.00│   312.50│ -11,250.00│    -2.15% │       │
│  │ TATAMOTORS  │   20 │     650.00│   892.40│   +4,848.00│    +1.87% │       │
│  └─────────────┴──────┴───────────┴────────┴───────────┴───────────┘       │
│                                                                              │
│  You: █                                                                      │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Portfolio Analysis Agent

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Terminal - Portfolio Copilot                                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  You: What are my worst performing stocks?                                   │
│                                                                              │
│  Using Portfolio Analysis                                                    │
│  ⠋ Running agent workflow...                                                 │
│                                                                              │
│  ══════════════════════════════════════════════════════════════════════════  │
│                                                                              │
│  ## Portfolio Analysis: Worst Performers                                     │
│                                                                              │
│  Based on your current holdings, here are your **3 worst performing**        │
│  stocks by return percentage:                                                │
│                                                                              │
│  | Stock    | Return   | P&L         | Qty |                                 │
│  |----------|----------|-------------|-----|                                 │
│  | GABRIEL  | -26.5%   | -₹11,250.00 | 100 |                                 │
│  | YESBANK  | -18.2%   | -₹3,640.00  | 200 |                                 │
│  | VEDL     | -12.8%   | -₹1,920.00  | 50  |                                 │
│                                                                              │
│  ### Key Insights                                                            │
│                                                                              │
│  **GABRIEL (-26.5%)**: Auto ancillary stocks have faced headwinds due        │
│  to weak Q3 results. Recent news indicates margin pressure from raw          │
│  material costs. Consider averaging down if fundamentals remain intact.      │
│                                                                              │
│  **YESBANK (-18.2%)**: Banking sector uncertainty continues. The stock       │
│  has been volatile following RBI's recent commentary on asset quality.       │
│                                                                              │
│  **VEDL (-12.8%)**: Metal prices correction and global demand concerns       │
│  have impacted commodity stocks. Seasonal recovery expected in Q4.           │
│                                                                              │
│  ══════════════════════════════════════════════════════════════════════════  │
│                                                                              │
│  You: █                                                                      │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Fundamental Analysis Agent

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Terminal - Portfolio Copilot                                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  You: fundamentals                                                           │
│  Which stock to analyze? (Is Reliance a good buy?): Should I buy TCS?        │
│                                                                              │
│  Fundamental Analysis Agent                                                  │
│  ⠋ Fetching fundamentals from screener.in...                                 │
│                                                                              │
│  ══════════════════════════════════════════════════════════════════════════  │
│                                                                              │
│  ## Fundamental Analysis: TCS                                                │
│                                                                              │
│  ### Scoring Breakdown                                                       │
│                                                                              │
│  | Dimension         | Score | Notes                        |                │
│  |-------------------|-------|------------------------------|                │
│  | Valuation         |  +2   | P/E 28.5 (industry avg: 25)  |                │
│  | Profitability     |  +8   | ROE 45%, ROCE 52% (strong)   |                │
│  | Growth            |  +4   | Revenue CAGR 12%, steady     |                │
│  | Financial Health  |  +7   | Debt-free, strong cash flow  |                │
│  | Promoter Holding  |  +6   | 72% promoter stake, stable   |                │
│  |-------------------|-------|------------------------------|                │
│  | **Total**         | **+27** |                            |                │
│                                                                              │
│  ### Recommendation: ✅ STRONG BUY                                           │
│                                                                              │
│  TCS demonstrates excellent fundamentals with industry-leading               │
│  profitability metrics and zero debt. The premium valuation is               │
│  justified by consistent execution and strong cash generation.               │
│                                                                              │
│  **Recent News Context:**                                                    │
│  - Q3 results beat estimates with 8.2% YoY profit growth                     │
│  - Won $500M deal with UK-based financial services firm                      │
│  - Management guides for continued momentum in BFSI vertical                 │
│                                                                              │
│  ══════════════════════════════════════════════════════════════════════════  │
│                                                                              │
│  You: █                                                                      │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### News Ingestion & RAG Search

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Terminal - Portfolio Copilot                                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  You: ingest                                                                 │
│  Stock symbols (comma-separated, or empty for general news): RELIANCE, TCS   │
│  ⠋ Fetching and indexing news...                                             │
│                                                                              │
│  Ingestion complete!                                                         │
│    Articles fetched: 24                                                      │
│    Chunks stored: 67                                                         │
│                                                                              │
│  You: search                                                                 │
│  Search query: Reliance quarterly results                                    │
│  ⠋ Searching...                                                              │
│                                                                              │
│  Found 5 results:                                                            │
│                                                                              │
│  1. Reliance Q3 Results: Net Profit Rises 18% to ₹18,549 Crore               │
│     Source: MoneyControl | Score: 0.89                                       │
│     Reliance Industries reported an 18% year-on-year rise in                 │
│     consolidated net profit to ₹18,549 crore for Q3 FY24...                  │
│                                                                              │
│  2. RIL's Retail and Jio Drive Growth Amid Refining Weakness                 │
│     Source: EconomicTimes | Score: 0.82                                      │
│     The oil-to-telecom conglomerate saw its consumer businesses              │
│     offset weakness in the traditional O2C segment...                        │
│                                                                              │
│  3. Reliance Industries: Analysts Upgrade Target Price Post Q3               │
│     Source: MoneyControl | Score: 0.76                                       │
│     Following strong Q3 results, brokerages have revised their               │
│     target prices for RIL, with consensus now at ₹3,100...                   │
│                                                                              │
│  You: █                                                                      │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Market Context Agent

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Terminal - Portfolio Copilot                                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  You: Why did my portfolio drop today?                                       │
│                                                                              │
│  Using Market Context                                                        │
│  ⠋ Running agent workflow...                                                 │
│                                                                              │
│  ══════════════════════════════════════════════════════════════════════════  │
│                                                                              │
│  ## Market Context Analysis                                                  │
│                                                                              │
│  Your portfolio is down **₹12,450 (-1.47%)** today.                          │
│                                                                              │
│  ### Market Overview                                                         │
│  - **NIFTY 50:** -1.82% (22,147.50)                                          │
│  - **SENSEX:** -1.75% (73,128.45)                                            │
│  - **BANKNIFTY:** -2.10% (46,892.30)                                         │
│                                                                              │
│  ### Biggest Losers in Your Portfolio Today                                  │
│  | Stock      | Day Change | Impact    |                                     │
│  |------------|------------|-----------|                                     │
│  | HDFCBANK   | -2.85%     | -₹4,890   |                                     │
│  | RELIANCE   | -1.65%     | -₹4,772   |                                     │
│  | TCS        | -0.92%     | -₹1,897   |                                     │
│                                                                              │
│  ### What's Happening                                                        │
│                                                                              │
│  The broader market selloff is driven by:                                    │
│                                                                              │
│  1. **Global cues**: US Fed's hawkish commentary on interest rates           │
│     triggered risk-off sentiment across emerging markets.                    │
│                                                                              │
│  2. **FII Outflows**: Foreign investors sold ₹3,200 crore in cash            │
│     segment today, continuing the January selling trend.                     │
│                                                                              │
│  3. **Banking Sector Pressure**: RBI's draft norms on project                │
│     financing hit banking stocks hardest, explaining HDFCBANK's drop.        │
│                                                                              │
│  Your portfolio's 16% banking exposure amplified today's losses.             │
│                                                                              │
│  ══════════════════════════════════════════════════════════════════════════  │
│                                                                              │
│  You: █                                                                      │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Natural Language Chat with Tool Calling

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Terminal - Portfolio Copilot                                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  You: What's my total portfolio value and which sector am I most exposed to? │
│  ⠋ Thinking...                                                               │
│                                                                              │
│  Assistant                                                                   │
│                                                                              │
│  Based on your current holdings, here's your portfolio summary:              │
│                                                                              │
│  **Total Portfolio Value:** ₹8,45,230.50                                     │
│  **Total P&L:** +₹52,340.00 (+6.6%)                                          │
│                                                                              │
│  ### Sector Exposure                                                         │
│                                                                              │
│  | Sector          | Value      | % of Portfolio |                          │
│  |-----------------|------------|----------------|                          │
│  | IT Services     | ₹3,25,400  | 38.5%          |                          │
│  | Oil & Gas       | ₹2,89,250  | 34.2%          |                          │
│  | Banking         | ₹1,37,000  | 16.2%          |                          │
│  | Auto Ancillary  | ₹31,250    | 3.7%           |                          │
│  | Metals          | ₹62,330    | 7.4%           |                          │
│                                                                              │
│  You're most heavily exposed to **IT Services** (38.5%) through your         │
│  TCS and Infosys holdings. Consider diversifying into other sectors          │
│  like pharma or FMCG to reduce concentration risk.                           │
│                                                                              │
│  You: █                                                                      │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Help Command

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Terminal - Portfolio Copilot                                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  You: help                                                                   │
│                                                                              │
│  Available Commands:                                                         │
│    login        - Login to your Kite account                                 │
│    whoami       - Show current login status                                  │
│    holdings     - Show your portfolio holdings (table view)                  │
│    analyze      - Run portfolio analysis agent                               │
│    research     - Run stock research agent                                   │
│    context      - Run market context agent                                   │
│    watchlist    - Run watchlist suggestion agent                             │
│    fundamentals - Run fundamental analysis (screener.in)                     │
│    ingest       - Fetch and index news articles                              │
│    search       - Search indexed news articles                               │
│    status       - Show vector store status                                   │
│    tools        - List available MCP tools                                   │
│    clear        - Clear conversation history                                 │
│    help         - Show this help message                                     │
│    exit         - Exit the application                                       │
│                                                                              │
│  Agent Triggers (auto-detected):                                             │
│    Portfolio:    "Analyze my portfolio", "worst performing stocks"           │
│    Research:     "Tell me about Reliance", "Research TCS"                    │
│    Context:      "Why is my portfolio down?", "market today"                 │
│    Watchlist:    "Suggest stocks to watch", "what should I buy"              │
│    Fundamentals: "Is Reliance a good buy?", "fundamentals of TCS"            │
│                                                                              │
│  Or just ask anything about your portfolio!                                  │
│                                                                              │
│  You: █                                                                      │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Tips for Medium Screenshots

Instead of ASCII mockups, you can take **actual screenshots** of your CLI:

1. **Use a nice terminal theme** (e.g., Dracula, One Dark, Tokyo Night)
2. **Set a clean font** (JetBrains Mono, Fira Code, or SF Mono)
3. **Use a screenshot tool** with padding:
   - macOS: `Cmd+Shift+4` then add shadow in Preview
   - [Carbon](https://carbon.now.sh) for code blocks
   - [CleanShot X](https://cleanshot.com) for polished screenshots
4. **Crop to focus** on the relevant interaction
5. **Add annotations** if needed (arrows, highlights)

### Recommended Terminal Settings for Screenshots
```
Font: JetBrains Mono, 14pt
Background: #1a1b26 (dark) or #fafafa (light)
Foreground: #c0caf5
Window size: 80 columns x 30 rows
```
