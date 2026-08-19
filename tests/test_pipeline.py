from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend import config
from backend.ingest import _clean_extracted_text
from backend.rag_chain import _build_context
from backend.retrieve import RetrievedChunk, has_relevant_context


def make_chunk(similarity: float, text: str = "sample text", source: str = "doc.pdf", page: int = 1):
    doc = Document(page_content=text, metadata={"source_file": source, "page": page})
    return RetrievedChunk(document=doc, similarity=similarity)


def test_chunking_respects_configured_size_and_overlap():
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    long_text = "This is a sentence about company policy. " * 100
    chunks = splitter.split_text(long_text)

    assert len(chunks) > 1
    assert all(len(c) <= config.CHUNK_SIZE + config.CHUNK_OVERLAP for c in chunks)


def test_chunking_short_text_is_a_single_chunk():
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP
    )
    chunks = splitter.split_text("A short paragraph that fits in one chunk.")
    assert len(chunks) == 1


def test_has_relevant_context_true_above_threshold():
    chunks = [make_chunk(0.8), make_chunk(0.7)]
    assert has_relevant_context(chunks) is True


def test_has_relevant_context_false_below_threshold():
    chunks = [make_chunk(0.2), make_chunk(0.1)]
    assert has_relevant_context(chunks) is False


def test_has_relevant_context_false_on_empty_input():
    assert has_relevant_context([]) is False


def test_build_context_includes_source_and_page():
    chunks = [make_chunk(0.9, text="Refunds are processed within 5 days.", source="policy.pdf", page=3)]
    context = _build_context(chunks)
    assert "policy.pdf" in context
    assert "page 3" in context
    assert "Refunds are processed within 5 days." in context


def test_clean_extracted_text_joins_orphaned_bullet_with_its_text():
    raw = "2. Professional Conduct Standards\n●\nTreat colleagues with respect.\n●\nPerform job duties honestly."
    cleaned = _clean_extracted_text(raw)
    assert "●\n" not in cleaned
    assert "● Treat colleagues with respect." in cleaned
    assert "● Perform job duties honestly." in cleaned


def test_clean_extracted_text_leaves_normal_lines_untouched():
    raw = "A normal paragraph.\nAnother normal line with no bullets."
    assert _clean_extracted_text(raw) == raw
