# Quickstart Guide

Get Portfolio Copilot running in 5 minutes.

## Prerequisites

- Python 3.12+
- Zerodha Kite account with [API access](https://kite.trade)
- [Anthropic API key](https://console.anthropic.com)

## Step 1: Install

```bash
# Clone the repo
git clone https://github.com/yourusername/portfolio-copilot.git
cd portfolio-copilot

# Install with Poetry
poetry install
```

## Step 2: Configure

Create a `.env` file:

```bash
cp .env.example .env
```

Add your API keys:

```bash
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
KITE_API_KEY=your_kite_api_key
KITE_API_SECRET=your_kite_api_secret
```

## Step 3: Run

```bash
poetry run python -m src.ui.cli
```

## Step 4: Login to Kite

```
Portfolio Copilot
Type 'help' for commands, or ask me about your portfolio!

You> login
```

This opens your browser for Zerodha OAuth login.

## Step 5: Start Asking Questions

### View Holdings
```
You> holdings
```

### Analyze Portfolio
```
You> What are my worst performing stocks?
```

### Research a Stock
```
You> Tell me about Reliance
```

### Check Fundamentals
```
You> Is TCS a good buy?
```

### Get Market Context
```
You> Why is my portfolio down today?
```

### Get Watchlist Suggestions
```
You> Suggest stocks for my watchlist
```

## Quick Commands Reference

| Command | What it does |
|---------|--------------|
| `login` | Connect to Zerodha |
| `holdings` | Show portfolio table |
| `analyze` | Analyze portfolio |
| `research` | Research a stock |
| `fundamentals` | Check if stock is good/bad |
| `context` | Explain market movements |
| `watchlist` | Get stock suggestions |
| `ingest` | Index news articles |
| `search` | Search indexed news |
| `help` | Show all commands |
| `exit` | Quit |

## Natural Language Examples

The AI understands natural language. Try these:

```
You> Analyze my portfolio performance
You> Which of my stocks is performing the worst?
You> Should I buy HDFC Bank?
You> What's happening with Infosys?
You> Why did my portfolio drop today?
You> What stocks should I add to my watchlist?
You> Is Reliance overvalued?
You> Give me the fundamentals of TCS
```

## Indexing News (Optional)

For better research insights, index recent news:

```
You> ingest
Stock symbols (comma-separated): TCS, RELIANCE, HDFCBANK
```

Then search:

```
You> search
Search query: TCS quarterly results
```

## Troubleshooting

### "Not logged in" error
Run `login` command first.

### "ANTHROPIC_API_KEY not set"
Check your `.env` file has the correct API key.

### News search returns empty
Run `ingest` to index news first.

### Screener.in data missing
Some smaller stocks may not be on screener.in.

## Next Steps

- Read the [Architecture Guide](architecture.md) to understand how it works
- Check the [API Reference](api-reference.md) for programmatic usage
- Explore the [CLAUDE.md](../CLAUDE.md) for development roadmap
