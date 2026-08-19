import re
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend import config

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
        collection_metadata={"hnsw:space": "cosine"},
    )


def ingest_pdf(pdf_path: Path) -> int:
    loader = PyPDFLoader(str(pdf_path))
    pages = loader.load() 

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
        chunk.metadata["page"] = chunk.metadata.get("page", 0) + 1

    if not chunks:
        return 0

    vectorstore = get_vectorstore()
    vectorstore.add_documents(chunks)
    return len(chunks)


def list_ingested_documents() -> list[str]:
    vectorstore = get_vectorstore()
    existing = vectorstore.get(include=["metadatas"])
    sources = {m["source_file"] for m in existing["metadatas"] if m.get("source_file")}
    return sorted(sources)


def get_full_document_text(source_file: str) -> str:
    vectorstore = get_vectorstore()
    existing = vectorstore.get(where={"source_file": source_file}, include=["metadatas", "documents"])
    pairs = sorted(
        zip(existing["metadatas"], existing["documents"]),
        key=lambda pair: pair[0].get("chunk_index", 0),
    )
    return "\n\n".join(text for _, text in pairs)


def delete_document(filename: str) -> int:
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
