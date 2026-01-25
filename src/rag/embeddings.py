"""Embedding generation using Sentence Transformers."""

import logging
import os
import warnings

# Suppress HuggingFace/transformers noise before importing
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

# Suppress various warnings
warnings.filterwarnings("ignore", message=".*HF_TOKEN.*")
warnings.filterwarnings("ignore", message=".*unauthenticated.*")
warnings.filterwarnings("ignore", message=".*LOAD REPORT.*")
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")

# Suppress transformers/sentence-transformers logging noise
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("transformers.modeling_utils").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

# Import with suppressed output
import transformers  # noqa: E402

transformers.logging.set_verbosity_error()

from sentence_transformers import SentenceTransformer  # noqa: E402

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
