"""RAG module for news retrieval and context augmentation."""

from src.rag.embeddings import embed_text, embed_texts, get_embedding_model
from src.rag.retriever import get_news_context, get_retriever, search_news
from src.rag.vector_store import Document, VectorStore, get_vector_store

__all__ = [
    "Document",
    "VectorStore",
    "get_vector_store",
    "embed_text",
    "embed_texts",
    "get_embedding_model",
    "search_news",
    "get_news_context",
    "get_retriever",
]
