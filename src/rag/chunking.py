"""Document chunking strategies for RAG."""

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    """A text chunk with position info."""

    text: str
    start_idx: int
    end_idx: int
    chunk_idx: int


def chunk_by_tokens(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
) -> list[Chunk]:
    """Split text into chunks by approximate token count.

    Uses word count as proxy for tokens (rough 1:1 ratio for English).

    Args:
        text: Text to chunk
        chunk_size: Target words per chunk
        overlap: Words to overlap between chunks
    """
    words = text.split()
    chunks = []

    if len(words) <= chunk_size:
        return [Chunk(text=text, start_idx=0, end_idx=len(text), chunk_idx=0)]

    start = 0
    chunk_idx = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words)

        # Calculate character positions
        char_start = len(" ".join(words[:start])) + (1 if start > 0 else 0)
        char_end = char_start + len(chunk_text)

        chunks.append(
            Chunk(
                text=chunk_text,
                start_idx=char_start,
                end_idx=char_end,
                chunk_idx=chunk_idx,
            )
        )

        start += chunk_size - overlap
        chunk_idx += 1

    return chunks


def chunk_by_sentences(
    text: str,
    max_chunk_size: int = 512,
    min_chunk_size: int = 100,
) -> list[Chunk]:
    """Split text into chunks respecting sentence boundaries.

    Args:
        text: Text to chunk
        max_chunk_size: Maximum words per chunk
        min_chunk_size: Minimum words before starting new chunk
    """
    # Split by sentence endings
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current_chunk: list[str] = []
    current_size = 0
    char_position = 0
    chunk_idx = 0

    for sentence in sentences:
        sentence_words = len(sentence.split())

        # If adding this sentence exceeds max, save current chunk
        if current_size + sentence_words > max_chunk_size and current_size >= min_chunk_size:
            chunk_text = " ".join(current_chunk)
            chunks.append(
                Chunk(
                    text=chunk_text,
                    start_idx=char_position - len(chunk_text),
                    end_idx=char_position,
                    chunk_idx=chunk_idx,
                )
            )
            current_chunk = []
            current_size = 0
            chunk_idx += 1

        current_chunk.append(sentence)
        current_size += sentence_words
        char_position += len(sentence) + 1  # +1 for space

    # Don't forget the last chunk
    if current_chunk:
        chunk_text = " ".join(current_chunk)
        chunks.append(
            Chunk(
                text=chunk_text,
                start_idx=char_position - len(chunk_text),
                end_idx=char_position,
                chunk_idx=chunk_idx,
            )
        )

    return chunks


def chunk_by_paragraphs(text: str, max_chunk_size: int = 1024) -> list[Chunk]:
    """Split text by paragraphs, merging small ones.

    Args:
        text: Text to chunk
        max_chunk_size: Maximum words per chunk
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current_chunk: list[str] = []
    current_size = 0
    char_position = 0
    chunk_idx = 0

    for para in paragraphs:
        para_words = len(para.split())

        # If paragraph itself is too large, use sentence chunking
        if para_words > max_chunk_size:
            # Save current chunk first
            if current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                chunks.append(
                    Chunk(
                        text=chunk_text,
                        start_idx=char_position - len(chunk_text),
                        end_idx=char_position,
                        chunk_idx=chunk_idx,
                    )
                )
                current_chunk = []
                current_size = 0
                chunk_idx += 1

            # Chunk the large paragraph
            para_chunks = chunk_by_sentences(para, max_chunk_size)
            for pc in para_chunks:
                pc.chunk_idx = chunk_idx
                chunks.append(pc)
                chunk_idx += 1

            char_position += len(para) + 2
            continue

        # If adding this paragraph exceeds max, save current
        if current_size + para_words > max_chunk_size and current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(
                Chunk(
                    text=chunk_text,
                    start_idx=char_position - len(chunk_text),
                    end_idx=char_position,
                    chunk_idx=chunk_idx,
                )
            )
            current_chunk = []
            current_size = 0
            chunk_idx += 1

        current_chunk.append(para)
        current_size += para_words
        char_position += len(para) + 2  # +2 for \n\n

    # Last chunk
    if current_chunk:
        chunk_text = "\n\n".join(current_chunk)
        chunks.append(
            Chunk(
                text=chunk_text,
                start_idx=max(0, char_position - len(chunk_text) - 2),
                end_idx=char_position,
                chunk_idx=chunk_idx,
            )
        )

    return chunks


def smart_chunk(
    text: str,
    strategy: str = "sentences",
    chunk_size: int = 512,
    overlap: int = 50,
) -> list[Chunk]:
    """Chunk text using specified strategy.

    Args:
        text: Text to chunk
        strategy: One of "tokens", "sentences", "paragraphs"
        chunk_size: Target size per chunk
        overlap: Overlap for token strategy
    """
    if strategy == "tokens":
        return chunk_by_tokens(text, chunk_size, overlap)
    elif strategy == "sentences":
        return chunk_by_sentences(text, chunk_size)
    elif strategy == "paragraphs":
        return chunk_by_paragraphs(text, chunk_size)
    else:
        raise ValueError(f"Unknown chunking strategy: {strategy}")
