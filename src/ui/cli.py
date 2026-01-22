#!/usr/bin/env python3
"""CLI interface for Portfolio CoPilot."""

import asyncio
import webbrowser
from collections.abc import Awaitable, Callable
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.table import Table

from src.llm.claude import PortfolioAssistant
from src.mcp.kite_client import AuthenticationError, KiteClient

console = Console()


def format_value(value: float, suffix: str = "") -> str:
    """Format numeric value with color based on sign."""
    color = "green" if value >= 0 else "red"
    return f"[{color}]{value:.2f}{suffix}[/{color}]"


def display_holdings(holdings: list[dict]) -> None:
    """Display holdings in a formatted table."""
    if not holdings:
        console.print("[yellow]No holdings found.[/yellow]")
        return

    table = Table(title="Portfolio Holdings")
    table.add_column("Symbol", style="cyan")
    table.add_column("Qty", justify="right")
    table.add_column("Avg Price", justify="right", style="dim")
    table.add_column("LTP", justify="right")
    table.add_column("P&L", justify="right")
    table.add_column("Change %", justify="right")

    for h in holdings:
        table.add_row(
            h.get("tradingsymbol", "N/A"),
            str(h.get("quantity", 0)),
            f"{h.get('average_price', 0):.2f}",
            f"{h.get('last_price', 0):.2f}",
            format_value(h.get("pnl", 0)),
            format_value(h.get("day_change_percentage", 0), "%"),
        )

    console.print(table)


async def run_with_error_handling(
    coro: Awaitable[Any],
    error_context: str,
    check_auth: bool = True,
) -> Any:
    """Run async operation with consistent error handling."""
    try:
        return await coro
    except AuthenticationError:
        if check_auth:
            console.print("[red]Not logged in. Run 'login' first.[/red]")
        return None
    except Exception as e:
        console.print(f"[red]Error {error_context}: {e}[/red]")
        return None


async def handle_login(client: KiteClient, _assistant: PortfolioAssistant) -> None:
    """Handle login flow."""
    # Check if already logged in
    with console.status("[bold green]Checking login status..."):
        if await client.is_logged_in():
            try:
                profile = await client.get_profile()
                user_name = profile.get("user_name", "User")
                console.print(f"[green]Already logged in as {user_name}![/green]")
                return
            except Exception:
                pass

    with console.status("[bold green]Getting login URL..."):
        result = await client.login()

    if not result.url:
        console.print("[red]Failed to get login URL.[/red]")
        return

    console.print("\n[bold yellow]Warning:[/bold yellow] AI systems are unpredictable.")
    console.print("By continuing, you interact with Zerodha at your own risk.\n")
    console.print(f"[bold]Login URL:[/bold] {result.url}\n")

    open_browser = Prompt.ask("Open in browser?", choices=["y", "n"], default="y")
    if open_browser == "y":
        webbrowser.open(result.url)
        console.print("[dim]Browser opened. Complete login there.[/dim]")

    # Wait for user to complete login
    console.print("\n[dim]Press Enter after completing login in browser...[/dim]")
    Prompt.ask("", default="")

    # Verify login succeeded
    with console.status("[bold green]Verifying login..."):
        if await client.is_logged_in():
            client.mark_logged_in()
            try:
                profile = await client.get_profile()
                user_name = profile.get("user_name", "User")
                console.print(f"[green]Successfully logged in as {user_name}![/green]")
            except Exception:
                console.print("[green]Successfully logged in![/green]")
        else:
            console.print("[yellow]Login not detected yet. Try running 'login' again or use any command - it will prompt if needed.[/yellow]")


async def handle_holdings(client: KiteClient, _assistant: PortfolioAssistant) -> None:
    """Fetch and display portfolio holdings."""
    with console.status("[bold green]Fetching holdings from Kite..."):
        holdings = await run_with_error_handling(
            client.get_holdings(),
            "fetching holdings",
        )
    if holdings is not None:
        display_holdings(holdings)


async def handle_tools(client: KiteClient, _assistant: PortfolioAssistant) -> None:
    """List available MCP tools."""
    with console.status("[bold green]Fetching available tools..."):
        tools = await run_with_error_handling(
            client.list_tools(),
            "fetching tools",
            check_auth=False,
        )
    if tools is not None:
        console.print("[bold]Available MCP Tools:[/bold]")
        for tool in tools:
            console.print(f"  - {tool}")


async def handle_clear(_client: KiteClient, assistant: PortfolioAssistant) -> None:
    """Clear conversation history."""
    assistant.clear_history()
    console.print("[dim]Conversation history cleared.[/dim]")


async def handle_whoami(client: KiteClient, _assistant: PortfolioAssistant) -> None:
    """Show current login status and user info."""
    with console.status("[bold green]Checking login status..."):
        try:
            if await client.is_logged_in():
                profile = await client.get_profile()
                console.print("\n[bold]Login Status:[/bold] [green]Logged In[/green]")
                console.print(f"  User ID: {profile.get('user_id', 'N/A')}")
                console.print(f"  Name: {profile.get('user_name', 'N/A')}")
                console.print(f"  Email: {profile.get('email', 'N/A')}")
                console.print(f"  Broker: {profile.get('broker', 'N/A')}")
                console.print()
            else:
                console.print("\n[bold]Login Status:[/bold] [red]Not Logged In[/red]")
                console.print("  Run 'login' to connect to your Kite account.\n")
        except Exception as e:
            console.print(f"\n[red]Error checking status: {e}[/red]\n")


async def handle_ingest(_client: KiteClient, _assistant: PortfolioAssistant) -> None:
    """Ingest latest news into vector store."""
    from src.data.ingestion import ingest_news

    symbols_input = Prompt.ask(
        "Stock symbols (comma-separated, or empty for general news)",
        default="",
    )

    symbols = [s.strip().upper() for s in symbols_input.split(",") if s.strip()]

    with console.status("[bold green]Fetching and indexing news..."):
        stats = await ingest_news(symbols=symbols or None, limit=10)

    console.print("\n[green]Ingestion complete![/green]")
    console.print(f"  Articles fetched: {stats.articles_fetched}")
    console.print(f"  Chunks stored: {stats.chunks_stored}")

    if stats.errors:
        console.print(f"  [yellow]Errors: {len(stats.errors)}[/yellow]")


async def handle_search(_client: KiteClient, _assistant: PortfolioAssistant) -> None:
    """Search news in vector store."""
    from src.rag.retriever import get_retriever

    query = Prompt.ask("Search query")
    if not query:
        return

    retriever = get_retriever()
    doc_count = retriever.get_document_count()

    if doc_count == 0:
        console.print("[yellow]No news indexed yet. Run 'ingest' first.[/yellow]")
        return

    with console.status("[bold green]Searching..."):
        results = retriever.search(query, top_k=5)

    if not results:
        console.print("[yellow]No matching results found.[/yellow]")
        return

    console.print(f"\n[bold]Found {len(results)} results:[/bold]\n")

    for i, r in enumerate(results, 1):
        console.print(f"[cyan]{i}. {r.title or 'Untitled'}[/cyan]")
        console.print(f"   [dim]Source: {r.source} | Score: {r.score:.2f}[/dim]")
        console.print(f"   {r.content[:200]}...")
        console.print()


async def handle_analyze(client: KiteClient, _assistant: PortfolioAssistant) -> None:
    """Run portfolio analysis agent."""
    from src.agents.orchestrator import AgentOrchestrator

    query = Prompt.ask(
        "What would you like to analyze?",
        default="Analyze my worst performing stocks",
    )

    orchestrator = AgentOrchestrator(client)

    console.print("\n[bold magenta]Portfolio Analysis Agent[/bold magenta]")

    with console.status("[bold green]Running analysis workflow..."):
        result = await orchestrator.run_agent("portfolio_analysis", query)

    console.print()
    console.print(Markdown(result["response"]))
    console.print()


async def handle_research(client: KiteClient, _assistant: PortfolioAssistant) -> None:
    """Run stock research agent."""
    from src.agents.orchestrator import AgentOrchestrator

    query = Prompt.ask(
        "Which stock to research?",
        default="Tell me about Reliance",
    )

    orchestrator = AgentOrchestrator(client)

    console.print("\n[bold magenta]Stock Research Agent[/bold magenta]")

    with console.status("[bold green]Researching stock..."):
        result = await orchestrator.run_agent("stock_research", query)

    console.print()
    console.print(Markdown(result["response"]))
    console.print()


async def handle_context(client: KiteClient, _assistant: PortfolioAssistant) -> None:
    """Run market context agent."""
    from src.agents.orchestrator import AgentOrchestrator

    query = Prompt.ask(
        "What would you like to understand?",
        default="Why did my portfolio move today?",
    )

    orchestrator = AgentOrchestrator(client)

    console.print("\n[bold magenta]Market Context Agent[/bold magenta]")

    with console.status("[bold green]Analyzing market context..."):
        result = await orchestrator.run_agent("market_context", query)

    console.print()
    console.print(Markdown(result["response"]))
    console.print()


async def handle_watchlist(client: KiteClient, _assistant: PortfolioAssistant) -> None:
    """Run watchlist suggestion agent."""
    from src.agents.orchestrator import AgentOrchestrator

    query = Prompt.ask(
        "What kind of stocks are you looking for?",
        default="Suggest stocks for my watchlist",
    )

    orchestrator = AgentOrchestrator(client)

    console.print("\n[bold magenta]Watchlist Suggestion Agent[/bold magenta]")

    with console.status("[bold green]Generating watchlist suggestions..."):
        result = await orchestrator.run_agent("watchlist", query)

    console.print()
    console.print(Markdown(result["response"]))
    console.print()


async def handle_fundamentals(client: KiteClient, _assistant: PortfolioAssistant) -> None:
    """Run fundamental analysis agent."""
    from src.agents.orchestrator import AgentOrchestrator

    query = Prompt.ask(
        "Which stock to analyze?",
        default="Is Reliance a good buy?",
    )

    orchestrator = AgentOrchestrator(client)

    console.print("\n[bold magenta]Fundamental Analysis Agent[/bold magenta]")

    with console.status("[bold green]Fetching fundamentals from screener.in..."):
        result = await orchestrator.run_agent("fundamental_analysis", query)

    console.print()
    console.print(Markdown(result["response"]))
    console.print()


async def handle_status(_client: KiteClient, _assistant: PortfolioAssistant) -> None:
    """Show status of the vector store."""
    from src.rag.vector_store import get_vector_store

    store = get_vector_store()
    count = store.count()

    console.print("\n[bold]Vector Store Status[/bold]")
    console.print(f"  Total documents: {count}")

    if count == 0:
        console.print("  [yellow]No news indexed yet. Run 'ingest' first.[/yellow]\n")
        return

    # Get sample documents by doing a broad search
    collection = store._collection
    results = collection.peek(limit=10)

    if results and results["ids"]:
        # Count by source
        sources: dict[str, int] = {}
        symbols: dict[str, int] = {}

        for meta in results["metadatas"]:
            src = meta.get("source", "unknown")
            sources[src] = sources.get(src, 0) + 1

            sym = meta.get("symbol", "")
            if sym:
                symbols[sym] = symbols.get(sym, 0) + 1

        console.print(f"\n[bold]Sources (sample of {len(results['ids'])}):[/bold]")
        for src, cnt in sources.items():
            console.print(f"  - {src}: {cnt}")

        if symbols:
            console.print("\n[bold]Symbols:[/bold]")
            for sym, cnt in symbols.items():
                console.print(f"  - {sym}: {cnt}")

        console.print("\n[bold]Recent documents:[/bold]")
        for i, (doc_id, content, meta) in enumerate(
            zip(results["ids"][:5], results["documents"][:5], results["metadatas"][:5])
        ):
            title = meta.get("title", "Untitled")[:50]
            source = meta.get("source", "?")
            console.print(f"  {i+1}. [{source}] {title}...")

    console.print()


def show_help() -> None:
    """Display help message."""
    console.print(
        """
[bold]Available Commands:[/bold]
  login       - Login to your Kite account
  whoami      - Show current login status
  holdings    - Show your portfolio holdings (table view)
  analyze     - Run portfolio analysis agent
  research    - Run stock research agent
  context     - Run market context agent
  watchlist   - Run watchlist suggestion agent
  fundamentals - Run fundamental analysis (screener.in)
  ingest      - Fetch and index news articles
  search      - Search indexed news articles
  status      - Show vector store status
  tools       - List available MCP tools
  clear       - Clear conversation history
  help        - Show this help message
  exit        - Exit the application

[bold]Agent Triggers (auto-detected):[/bold]
  Portfolio:    "Analyze my portfolio", "worst performing stocks"
  Research:     "Tell me about Reliance", "Research TCS"
  Context:      "Why is my portfolio down?", "market today"
  Watchlist:    "Suggest stocks to watch", "what should I buy"
  Fundamentals: "Is Reliance a good buy?", "fundamentals of TCS"

[bold]Or just ask anything about your portfolio![/bold]
        """
    )


async def handle_chat(
    user_input: str,
    assistant: PortfolioAssistant,
    client: KiteClient,
) -> None:
    """Handle natural language chat with Claude or agents."""
    from src.agents.orchestrator import AgentOrchestrator

    # Check if an agent should handle this query
    orchestrator = AgentOrchestrator(client)
    should_use, agent_type = orchestrator.should_use_agent(user_input)

    if should_use and agent_type:
        # Use agent workflow
        console.print(f"\n[bold magenta]Using {agent_type.replace('_', ' ').title()}[/bold magenta]")

        with console.status("[bold green]Running agent workflow..."):
            result = await orchestrator.run_agent(agent_type, user_input)

        console.print()
        console.print(Markdown(result["response"]))
        console.print()
        return

    # Regular Claude chat - collect full response
    response_text = ""

    try:
        with console.status("[bold green]Thinking..."):
            async for event in assistant.chat(user_input):
                if event.type == "text":
                    response_text += event.text
                elif event.type == "done":
                    break

        # Print response with markdown formatting
        console.print("\n[bold cyan]Assistant[/bold cyan]")
        console.print(Markdown(response_text))
        console.print()

    except AuthenticationError:
        console.print("\n[red]Not logged in. Run 'login' first.[/red]\n")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]\n")


async def check_login_status(client: KiteClient) -> None:
    """Check and display login status at startup."""
    try:
        if await client.is_logged_in():
            profile = await client.get_profile()
            user_name = profile.get("user_name", "User")
            console.print(f"[green]Logged in as {user_name}[/green]\n")
        else:
            console.print("[yellow]Not logged in. Run 'login' to connect to Kite.[/yellow]\n")
    except Exception:
        console.print("[dim]Run 'login' to connect to your Kite account.[/dim]\n")


async def async_main() -> None:
    """Async main entry point."""
    console.print("[bold green]Portfolio Copilot[/bold green]")
    console.print("Type 'help' for commands, or ask me about your portfolio!\n")

    # Command handlers
    commands: dict[str, Callable[[KiteClient, PortfolioAssistant], Awaitable[None]]] = {
        "login": handle_login,
        "whoami": handle_whoami,
        "holdings": handle_holdings,
        "analyze": handle_analyze,
        "research": handle_research,
        "context": handle_context,
        "watchlist": handle_watchlist,
        "fundamentals": handle_fundamentals,
        "tools": handle_tools,
        "ingest": handle_ingest,
        "search": handle_search,
        "status": handle_status,
        "clear": handle_clear,
    }

    async with KiteClient() as client:
        assistant = PortfolioAssistant(client)

        # Check login status at startup
        await check_login_status(client)

        while True:
            try:
                loop = asyncio.get_running_loop()
                user_input = await loop.run_in_executor(
                    None, lambda: Prompt.ask("[bold blue]You[/bold blue]")
                )
                cmd = user_input.lower().strip()

                if cmd in ["exit", "quit", "q"]:
                    console.print("[yellow]Goodbye![/yellow]")
                    break

                if cmd == "help":
                    show_help()
                    continue

                if not cmd:
                    continue

                handler = commands.get(cmd)
                if handler:
                    await handler(client, assistant)
                    continue

                # Natural language chat with Claude or agents
                await handle_chat(user_input, assistant, client)

            except KeyboardInterrupt:
                console.print("\n[yellow]Goodbye![/yellow]")
                break


def main() -> None:
    """Main CLI entry point."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
