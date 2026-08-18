"""Similarity search over the persisted vector store, plus a relevance gate for the LLM call."""

from dataclasses import dataclass

from langchain_core.documents import Document

from backend import config
from backend.ingest import get_vectorstore


@dataclass
class RetrievedChunk:
    document: Document
    similarity: float  # 0 (unrelated) to 1 (identical), higher is better — used internally only


def retrieve(
    query: str, k: int = config.TOP_K, source_filter: str | None = None
) -> list[RetrievedChunk]:
    """If source_filter is set, restricts the search to chunks from that one document."""
    vectorstore = get_vectorstore()
    metadata_filter = {"source_file": source_filter} if source_filter else None
    results = vectorstore.similarity_search_with_score(query, k=k, filter=metadata_filter)

    chunks = []
    for doc, distance in results:
        # Chroma's cosine space returns a distance in [0, 2]; convert to a 0-1 similarity score.
        similarity = max(0.0, 1.0 - (distance / 2.0))
        chunks.append(RetrievedChunk(document=doc, similarity=similarity))
    return chunks


def has_relevant_context(chunks: list[RetrievedChunk]) -> bool:
    """Whether retrieval found anything solid enough to answer from."""
    if not chunks:
        return False
    avg_similarity = sum(c.similarity for c in chunks) / len(chunks)
    return avg_similarity >= config.MIN_RELEVANCE_SIMILARITY
