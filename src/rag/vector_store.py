"""ChromaDB vector store interface."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from src.rag.embeddings import embed_text, embed_texts

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "vector_store"
COLLECTION_NAME = "news_articles"


@dataclass
class Document:
    """A document with metadata for storage."""

    id: str
    content: str
    metadata: dict[str, Any]
    embedding: list[float] | None = None

    @classmethod
    def create(
        cls,
        content: str,
        source: str,
        symbol: str | None = None,
        published_at: datetime | None = None,
        title: str | None = None,
        url: str | None = None,
    ) -> "Document":
        """Create a new document with auto-generated ID."""
        return cls(
            id=str(uuid.uuid4()),
            content=content,
            metadata={
                "source": source,
                "symbol": symbol or "",
                "published_at": published_at.isoformat() if published_at else "",
                "title": title or "",
                "url": url or "",
            },
        )


@dataclass
class SearchResult:
    """A search result with score."""

    document: Document
    score: float


class VectorStore:
    """ChromaDB-based vector store for document storage and retrieval."""

    def __init__(
        self,
        persist_directory: str | Path | None = None,
        collection: str = COLLECTION_NAME,
    ):
        persist_dir = Path(persist_directory) if persist_directory else DATA_DIR
        persist_dir.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection,
            metadata={"hnsw:space": "cosine"},
        )

    def add_document(self, doc: Document) -> None:
        """Add a single document to the store."""
        if doc.embedding is None:
            doc.embedding = embed_text(doc.content)

        self._collection.upsert(
            ids=[doc.id],
            embeddings=[doc.embedding],
            documents=[doc.content],
            metadatas=[doc.metadata],
        )

    def add_documents(self, docs: list[Document]) -> None:
        """Add multiple documents to the store."""
        if not docs:
            return

        # Generate embeddings for docs without them
        texts_to_embed = []
        indices_to_embed = []

        for i, doc in enumerate(docs):
            if doc.embedding is None:
                texts_to_embed.append(doc.content)
                indices_to_embed.append(i)

        if texts_to_embed:
            embeddings = embed_texts(texts_to_embed)
            for idx, embedding in zip(indices_to_embed, embeddings):
                docs[idx].embedding = embedding

        self._collection.upsert(
            ids=[doc.id for doc in docs],
            embeddings=[doc.embedding for doc in docs],
            documents=[doc.content for doc in docs],
            metadatas=[doc.metadata for doc in docs],
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        symbol: str | None = None,
        source: str | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents.

        Args:
            query: Search query text
            top_k: Number of results to return
            symbol: Filter by stock symbol
            source: Filter by news source
        """
        query_embedding = embed_text(query)

        # Build where filter
        where_filter = None
        conditions = []

        if symbol:
            conditions.append({"symbol": {"$eq": symbol}})

        if source:
            conditions.append({"source": {"$eq": source}})

        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$and": conditions}

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        search_results = []

        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                # ChromaDB returns distances, convert to similarity score
                distance = results["distances"][0][i] if results["distances"] else 0
                score = 1 - distance  # Cosine distance to similarity

                search_results.append(
                    SearchResult(
                        document=Document(
                            id=doc_id,
                            content=results["documents"][0][i] if results["documents"] else "",
                            metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                        ),
                        score=score,
                    )
                )

        return search_results

    def delete_by_source(self, source: str) -> None:
        """Delete all documents from a specific source."""
        self._collection.delete(where={"source": {"$eq": source}})

    def count(self) -> int:
        """Get total document count."""
        return self._collection.count()


# Singleton instance
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Get or create the vector store singleton."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
