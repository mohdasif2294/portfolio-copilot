"""Retriever for semantic search over news articles."""

from dataclasses import dataclass

from src.rag.vector_store import SearchResult, VectorStore, get_vector_store


@dataclass
class RetrievalResult:
    """A formatted retrieval result for LLM consumption."""

    content: str
    title: str
    source: str
    url: str
    symbol: str | None
    score: float

    def to_context_string(self) -> str:
        """Format as context string for LLM."""
        header = f"[{self.source}]"
        if self.symbol:
            header += f" [{self.symbol}]"
        if self.title:
            header += f" {self.title}"

        return f"{header}\n{self.content}\nSource: {self.url}"


class NewsRetriever:
    """Retriever for news articles with formatting for LLM context."""

    def __init__(self, vector_store: VectorStore | None = None):
        self._store = vector_store or get_vector_store()

    def search(
        self,
        query: str,
        top_k: int = 5,
        symbol: str | None = None,
        source: str | None = None,
        min_score: float = 0.3,
    ) -> list[RetrievalResult]:
        """Search for relevant news articles.

        Args:
            query: Search query
            top_k: Max results to return
            symbol: Filter by stock symbol
            source: Filter by news source
            min_score: Minimum similarity score threshold
        """
        results = self._store.search(
            query=query,
            top_k=top_k,
            symbol=symbol,
            source=source,
        )

        # Filter by score and convert to RetrievalResult
        retrieval_results = []

        for r in results:
            if r.score < min_score:
                continue

            retrieval_results.append(
                RetrievalResult(
                    content=r.document.content,
                    title=r.document.metadata.get("title", ""),
                    source=r.document.metadata.get("source", "unknown"),
                    url=r.document.metadata.get("url", ""),
                    symbol=r.document.metadata.get("symbol") or None,
                    score=r.score,
                )
            )

        return retrieval_results

    def search_for_context(
        self,
        query: str,
        top_k: int = 3,
        symbol: str | None = None,
        max_context_length: int = 2000,
    ) -> str:
        """Search and format results as context string for LLM.

        Args:
            query: Search query
            top_k: Max results
            symbol: Optional stock symbol filter
            max_context_length: Max characters in combined context
        """
        results = self.search(query, top_k=top_k, symbol=symbol)

        if not results:
            return ""

        context_parts = []
        total_length = 0

        for r in results:
            context_str = r.to_context_string()

            if total_length + len(context_str) > max_context_length:
                break

            context_parts.append(context_str)
            total_length += len(context_str)

        return "\n\n---\n\n".join(context_parts)

    def get_document_count(self) -> int:
        """Get total number of documents in store."""
        return self._store.count()


# Singleton retriever
_retriever: NewsRetriever | None = None


def get_retriever() -> NewsRetriever:
    """Get or create the retriever singleton."""
    global _retriever
    if _retriever is None:
        _retriever = NewsRetriever()
    return _retriever


def search_news(
    query: str,
    top_k: int = 5,
    symbol: str | None = None,
) -> list[RetrievalResult]:
    """Convenience function to search news.

    Args:
        query: Search query
        top_k: Max results
        symbol: Optional stock filter
    """
    return get_retriever().search(query, top_k=top_k, symbol=symbol)


def get_news_context(
    query: str,
    symbol: str | None = None,
    top_k: int = 3,
) -> str:
    """Get formatted news context for LLM.

    Args:
        query: Search query
        symbol: Optional stock filter
        top_k: Max results
    """
    return get_retriever().search_for_context(query, top_k=top_k, symbol=symbol)
