"""Central configuration for SmartDoc. Loads secrets from .env — never hardcode keys here."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
CHROMA_DIR = BASE_DIR / "data" / "chroma_db"
COLLECTION_NAME = "smartdoc_chunks"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# Chunking — see README for the size/overlap reasoning. Kept small deliberately: PDF text
# extraction often loses the blank-line breaks between the source document's sections, so a
# larger chunk size packs multiple unrelated sections into one chunk — which pollutes both
# the embedding (a blurred multi-topic vector retrieves worse) and the citation shown to the
# user (a "paragraph" that's actually 3 unrelated sections stitched together).
CHUNK_SIZE = 400
CHUNK_OVERLAP = 70

# Retrieval — TOP_K bumped up slightly to compensate for the smaller chunk size above.
TOP_K = 5
# Below this average similarity, retrieved chunks are too weak to answer from — skip the LLM
# call and say the documents don't cover the question, rather than risking a hallucinated answer.
MIN_RELEVANCE_SIMILARITY = 0.40
# Within one document, every chunk shares enough vocabulary that even unrelated sections can
# clear MIN_RELEVANCE_SIMILARITY above — a flat threshold can't tell "the actual match" apart
# from "next-best guesses in the same document". A chunk is only cited if its similarity is
# within this margin of the *best* chunk retrieved for this query, so citations reflect the
# top cluster of genuinely relevant chunks rather than everything the retriever returned.
CITATION_SIMILARITY_MARGIN = 0.05

# How many recent chat turns to feed the follow-up resolver (see rag_chain.resolve_question).
# Bounded so a long-running conversation doesn't grow that prompt — and its cost — unbounded.
FOLLOWUP_HISTORY_TURNS = 3


def require_api_key() -> None:
    """Raise a clear, actionable error instead of letting a downstream SDK call fail cryptically."""
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key."
        )


def safe_filename(name: str) -> str:
    """Strips any directory component from a client-supplied filename before it touches disk,
    so a crafted name like '../../etc/passwd' can't escape UPLOAD_DIR."""
    return Path(name).name
