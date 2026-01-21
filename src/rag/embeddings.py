"""Embedding generation using Sentence Transformers."""

import os
import warnings

# Suppress HuggingFace token warning for local use
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
warnings.filterwarnings("ignore", message=".*HF_TOKEN.*")

from sentence_transformers import SentenceTransformer

DEFAULT_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


class EmbeddingModel:
    """Wrapper for sentence transformer embeddings."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self._model = SentenceTransformer(model_name)
        self._dim = self._model.get_sentence_embedding_dimension()

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        return self._dim

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()


# Singleton instance for reuse
_embedding_model: EmbeddingModel | None = None


def get_embedding_model() -> EmbeddingModel:
    """Get or create the embedding model singleton."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = EmbeddingModel()
    return _embedding_model


def embed_text(text: str) -> list[float]:
    """Convenience function to embed a single text."""
    return get_embedding_model().embed(text)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Convenience function to embed multiple texts."""
    return get_embedding_model().embed_batch(texts)
