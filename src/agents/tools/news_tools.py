"""News and RAG tools for agent workflows."""

from typing import Any

from src.data.ingestion import ingest_news
from src.rag.retriever import get_retriever


def search_stock_news(
    symbols: list[str],
    query: str | None = None,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Search for news about specific stocks.

    Args:
        symbols: List of stock symbols to search for
        query: Optional additional search query
        top_k: Results per symbol

    Returns:
        List of news articles with metadata
    """
    retriever = get_retriever()
    all_results = []

    for symbol in symbols:
        # Search for each symbol
        search_query = f"{symbol} {query}" if query else symbol
        results = retriever.search(
            query=search_query,
            symbol=symbol,
            top_k=top_k,
        )

        for r in results:
            all_results.append({
                "symbol": symbol,
                "title": r.title,
                "content": r.content[:500],
                "source": r.source,
                "url": r.url,
                "score": r.score,
            })

    return all_results


async def ensure_news_indexed(symbols: list[str]) -> dict[str, Any]:
    """Ensure news is indexed for given symbols.

    Ingests news if none found in vector store.

    Args:
        symbols: List of stock symbols

    Returns:
        Dict with ingestion stats
    """
    retriever = get_retriever()

    # Check if we have any news for these symbols
    has_news = False
    for symbol in symbols:
        results = retriever.search(query=symbol, top_k=1, symbol=symbol)
        if results:
            has_news = True
            break

    if not has_news:
        # Ingest news for these symbols
        stats = await ingest_news(symbols=symbols, limit=5)
        return {
            "ingested": True,
            "articles_fetched": stats.articles_fetched,
            "chunks_stored": stats.chunks_stored,
        }

    return {"ingested": False, "message": "News already indexed"}


def get_news_context_string(news_articles: list[dict[str, Any]]) -> str:
    """Format news articles as context string for LLM.

    Args:
        news_articles: List of news article dicts

    Returns:
        Formatted string for LLM context
    """
    if not news_articles:
        return "No recent news found for these stocks."

    parts = []
    for article in news_articles:
        symbol = article.get("symbol", "")
        title = article.get("title", "Untitled")
        content = article.get("content", "")
        source = article.get("source", "unknown")

        parts.append(f"[{source}] {symbol}: {title}\n{content}")

    return "\n\n---\n\n".join(parts)
