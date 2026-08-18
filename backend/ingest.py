"""Parses PDFs into clean text, chunks them, embeds the chunks, and persists them in Chroma."""

import re
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend import config

# Some PDF generators (including the one used for this project's sample docs) draw a bulleted
# list item's marker as a separate text element from its content, positioned to its left rather
# than inline. pypdf extracts text in content-stream order, so the bullet glyph and its text come
# out as two separate lines — "●\nTreat colleagues..." instead of "● Treat colleagues...". This
# matches a line that is ONLY a bullet character and joins it with the line that follows.
_BULLET_CHARS = "●•▪◦‣"
_ORPHANED_BULLET_RE = re.compile(rf"^([{_BULLET_CHARS}])[ \t]*\n[ \t]*", re.MULTILINE)


def _clean_extracted_text(text: str) -> str:
    return _ORPHANED_BULLET_RE.sub(r"\1 ", text)


def get_embeddings() -> OpenAIEmbeddings:
    config.require_api_key()
    return OpenAIEmbeddings(model=config.OPENAI_EMBEDDING_MODEL, api_key=config.OPENAI_API_KEY)


def get_vectorstore() -> Chroma:
    return Chroma(
        collection_name=config.COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(config.CHROMA_DIR),
        # Cosine distance keeps the similarity scale intuitive (0-1) for the relevance threshold.
        collection_metadata={"hnsw:space": "cosine"},
    )


def ingest_pdf(pdf_path: Path) -> int:
    """Load, chunk, embed, and persist one PDF. Returns the number of chunks added."""
    loader = PyPDFLoader(str(pdf_path))
    pages = loader.load()  # one Document per page, with page_number in metadata

    for page in pages:
        page.page_content = _clean_extracted_text(page.page_content)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(pages)

    for i, chunk in enumerate(chunks):
        chunk.metadata["source_file"] = pdf_path.name
        chunk.metadata["chunk_index"] = i
        # PyPDFLoader's page number is 0-indexed; store the human-readable version for citations.
        chunk.metadata["page"] = chunk.metadata.get("page", 0) + 1

    if not chunks:
        return 0

    vectorstore = get_vectorstore()
    vectorstore.add_documents(chunks)
    return len(chunks)


def list_ingested_documents() -> list[str]:
    """Distinct source filenames currently stored in the vector DB."""
    vectorstore = get_vectorstore()
    existing = vectorstore.get(include=["metadatas"])
    sources = {m["source_file"] for m in existing["metadatas"] if m.get("source_file")}
    return sorted(sources)


def delete_document(filename: str) -> int:
    """Removes every chunk for one source file from the vector store and deletes the uploaded
    PDF from disk. Returns the number of chunks removed (0 if the filename wasn't found)."""
    filename = config.safe_filename(filename)

    vectorstore = get_vectorstore()
    existing = vectorstore.get(where={"source_file": filename}, include=[])
    ids = existing.get("ids", [])

    if ids:
        vectorstore.delete(ids=ids)

    pdf_path = config.UPLOAD_DIR / filename
    if pdf_path.exists():
        pdf_path.unlink()

    return len(ids)
