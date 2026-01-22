"""Data ingestion pipeline for Indian stock market news."""

import asyncio
from dataclasses import dataclass

from src.data.scrapers.economictimes import EconomicTimesScraper
from src.data.scrapers.moneycontrol import MoneyControlScraper, NewsArticle
from src.rag.chunking import smart_chunk
from src.rag.vector_store import Document, VectorStore, get_vector_store


@dataclass
class IngestionStats:
    """Statistics from an ingestion run."""

    articles_fetched: int
    chunks_created: int
    chunks_stored: int
    errors: list[str]


class NewsIngestionPipeline:
    """Pipeline to fetch, chunk, and store news articles."""

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        chunk_size: int = 512,
        chunk_strategy: str = "sentences",
    ):
        self._store = vector_store or get_vector_store()
        self._chunk_size = chunk_size
        self._chunk_strategy = chunk_strategy

    async def ingest_latest_news(self, limit: int = 20) -> IngestionStats:
        """Fetch and store latest Indian stock market news.

        Args:
            limit: Max articles per source
        """
        stats = IngestionStats(
            articles_fetched=0,
            chunks_created=0,
            chunks_stored=0,
            errors=[],
        )

        # Fetch from Indian sources in parallel
        async with MoneyControlScraper() as mc, EconomicTimesScraper() as et:
            results = await asyncio.gather(
                mc.get_latest_news(limit),
                et.get_latest_news(limit),
                return_exceptions=True,
            )

        all_articles: list[NewsArticle] = []

        for result in results:
            if isinstance(result, Exception):
                stats.errors.append(str(result))
            else:
                all_articles.extend(result)

        stats.articles_fetched = len(all_articles)

        # Process and store articles
        documents = self._process_articles(all_articles)
        stats.chunks_created = len(documents)

        if documents:
            self._store.add_documents(documents)
            stats.chunks_stored = len(documents)

        return stats

    async def ingest_stock_news(
        self, symbols: list[str], limit: int = 10
    ) -> IngestionStats:
        """Fetch and store news for specific Indian stocks.

        Args:
            symbols: List of stock symbols (e.g., ["RELIANCE", "TCS", "GABRIEL"])
            limit: Max articles per symbol per source
        """
        stats = IngestionStats(
            articles_fetched=0,
            chunks_created=0,
            chunks_stored=0,
            errors=[],
        )

        all_articles: list[NewsArticle] = []

        async with MoneyControlScraper() as mc, EconomicTimesScraper() as et:
            for symbol in symbols:
                results = await asyncio.gather(
                    mc.search_news(symbol, limit),
                    et.search_news(symbol, limit),
                    return_exceptions=True,
                )

                for result in results:
                    if isinstance(result, Exception):
                        stats.errors.append(f"{symbol}: {result}")
                    else:
                        # Ensure symbol is set on all articles
                        for article in result:
                            if not article.symbol:
                                article.symbol = symbol.upper()
                        all_articles.extend(result)

        stats.articles_fetched = len(all_articles)

        documents = self._process_articles(all_articles)
        stats.chunks_created = len(documents)

        if documents:
            self._store.add_documents(documents)
            stats.chunks_stored = len(documents)

        return stats

    def _process_articles(self, articles: list[NewsArticle]) -> list[Document]:
        """Convert articles to chunked documents."""
        documents = []

        for article in articles:
            if not article.content or len(article.content) < 50:
                continue

            # Chunk the article content
            chunks = smart_chunk(
                article.content,
                strategy=self._chunk_strategy,
                chunk_size=self._chunk_size,
            )

            for chunk in chunks:
                # Create document with chunk metadata
                doc = Document.create(
                    content=chunk.text,
                    source=article.source,
                    symbol=article.symbol,
                    published_at=article.published_at,
                    title=article.title,
                    url=article.url,
                )
                # Add chunk index to metadata
                doc.metadata["chunk_idx"] = chunk.chunk_idx
                doc.metadata["total_chunks"] = len(chunks)
                documents.append(doc)

        return documents


async def ingest_news(
    symbols: list[str] | None = None,
    limit: int = 10,
) -> IngestionStats:
    """Convenience function to run ingestion.

    Args:
        symbols: Optional list of stock symbols to focus on
        limit: Max articles per source/symbol
    """
    pipeline = NewsIngestionPipeline()

    if symbols:
        return await pipeline.ingest_stock_news(symbols, limit)
    return await pipeline.ingest_latest_news(limit)


# CLI entry point
if __name__ == "__main__":
    import sys

    symbols = sys.argv[1:] if len(sys.argv) > 1 else None

    print(f"Starting ingestion for: {symbols or 'latest news'}")
    stats = asyncio.run(ingest_news(symbols))

    print("\nIngestion complete:")
    print(f"  Articles fetched: {stats.articles_fetched}")
    print(f"  Chunks created: {stats.chunks_created}")
    print(f"  Chunks stored: {stats.chunks_stored}")

    if stats.errors:
        print(f"  Errors: {len(stats.errors)}")
        for err in stats.errors[:5]:
            print(f"    - {err}")
