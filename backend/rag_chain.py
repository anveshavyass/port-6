"""Builds the grounded prompt and calls the LLM to answer from retrieved chunks only."""

import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend import config
from backend.ingest import list_ingested_documents
from backend.retrieve import RetrievedChunk, has_relevant_context, retrieve

# The LLM is told to emit this exact token when the excerpts don't answer the question, so
# we can detect "no real answer" deterministically instead of guessing from free-text phrasing
# like "doesn't cover" / "not mentioned" / "no information available".
NOT_COVERED_SENTINEL = "NOT_COVERED"

SYSTEM_PROMPT = (
    "You are SmartDoc, an assistant that answers questions using ONLY the document "
    "excerpts provided below. Follow these rules strictly:\n"
    "1. Base your answer only on the provided excerpts — do not use outside knowledge.\n"
    f"2. If the excerpts do not contain enough information to answer, respond with EXACTLY "
    f"the single word {NOT_COVERED_SENTINEL} and nothing else — no punctuation, no explanation.\n"
    "3. Otherwise, respond in exactly this two-line format and nothing else:\n"
    "ANSWER: <a concise, direct answer to the question>\n"
    "QUOTE: <the exact sentence copied character-for-character from the excerpts above that "
    "most directly supports the answer — do not paraphrase or alter it>\n"
    "4. Do not fabricate document names, page numbers, or facts not present in the excerpts."
)

FOLLOWUP_SYSTEM_PROMPT = (
    "You rewrite a user's latest chat message into a fully self-contained, standalone "
    "question, using ONLY the recent conversation below to resolve pronouns and implied "
    "context — for example 'what about after 5 years?' following a question about PTO "
    "becomes 'How many PTO days do I get after 5 years?'\n"
    "If the latest message is already standalone, or unrelated to the prior conversation, "
    "return it completely unchanged.\n"
    "Output ONLY the resulting question — no explanation, quotes, or prefix."
)


def _parse_structured_answer(text: str) -> tuple[str, str | None]:
    """Splits the LLM's 'ANSWER: ...\\nQUOTE: ...' response into (answer, quote). Falls back
    to treating the whole response as the answer if the model didn't follow the format, so a
    formatting slip degrades gracefully instead of losing the answer entirely."""
    match = re.search(r"ANSWER:\s*(.*?)\s*QUOTE:\s*(.*)\Z", text, re.DOTALL)
    if not match:
        return text.strip(), None
    answer = match.group(1).strip()
    quote = match.group(2).strip().strip('"').strip("“”") or None
    return answer, quote


def _build_context(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for chunk in chunks:
        meta = chunk.document.metadata
        source = f"{meta.get('source_file', 'unknown')} (page {meta.get('page', '?')})"
        blocks.append(f"[Source: {source}]\n{chunk.document.page_content}")
    return "\n\n---\n\n".join(blocks)


def _ask_llm(llm: ChatOpenAI, query: str, chunks: list[RetrievedChunk], not_covered_message: str) -> dict:
    """Calls the LLM with all retrieved chunks as context — giving it the full top-k spread
    helps it find the right answer even when only one or two chunks are truly on-topic.
    But the chunks *cited* back to the user are filtered down to only the individually
    relevant ones: with top-k retrieval, the last couple of results are often just "the
    least-bad remaining matches" rather than actually relevant, and citing those anyway
    is misleading even when the answer itself is correct."""
    context = _build_context(chunks)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Document excerpts:\n\n{context}\n\nQuestion: {query}"),
    ]
    response = llm.invoke(messages)
    raw_text = response.content.strip()

    if raw_text.upper().startswith(NOT_COVERED_SENTINEL):
        return {"answer": not_covered_message, "sources": [], "quote": None}

    answer_text, quote = _parse_structured_answer(raw_text)

    top_similarity = max(c.similarity for c in chunks)
    citable_chunks = [
        c for c in chunks if c.similarity >= top_similarity - config.CITATION_SIMILARITY_MARGIN
    ]
    return {
        "answer": answer_text,
        "sources": [_source_info(c) for c in citable_chunks],
        "quote": quote,
    }


def resolve_question(question: str, history: list[dict]) -> str:
    """Rewrites a possibly context-dependent follow-up (e.g. 'what about after 5 years?')
    into a standalone question using recent chat history, so retrieval isn't run on a
    pronoun or implied reference that the embedding model has no way to resolve on its own.
    Skips the LLM call entirely when there's no history — the common case for a first
    question, and the case where history resolution would have nothing to work with."""
    question = question.strip()
    if not history:
        return question

    config.require_api_key()
    llm = ChatOpenAI(model=config.OPENAI_CHAT_MODEL, temperature=0, api_key=config.OPENAI_API_KEY)

    recent = history[-config.FOLLOWUP_HISTORY_TURNS :]
    transcript = "\n".join(f"Q: {turn['question']}\nA: {turn['answer']}" for turn in recent)

    messages = [
        SystemMessage(content=FOLLOWUP_SYSTEM_PROMPT),
        HumanMessage(content=f"Recent conversation:\n{transcript}\n\nLatest message: {question}"),
    ]
    response = llm.invoke(messages)
    rewritten = response.content.strip().strip('"').strip("“”")
    return rewritten or question


def answer_question(query: str, source_filter: str | None = None) -> dict:
    """Returns a dict: answer, sources (list). If source_filter is set, retrieval is
    restricted to that one ingested document instead of searching all of them."""
    query = query.strip()
    if not query:
        return {"answer": "Please enter a question.", "sources": [], "quote": None}

    scope = f"'{source_filter}'" if source_filter else "the uploaded documents"
    not_covered_message = (
        f"I don't have enough relevant information in {scope} to answer this. "
        "Try rephrasing, or confirm this topic is actually covered there."
    )

    chunks = retrieve(query, source_filter=source_filter)

    # If retrieval didn't find anything solid, skip the LLM call entirely rather than
    # risk a confidently-wrong answer.
    if not has_relevant_context(chunks):
        return {"answer": not_covered_message, "sources": [], "quote": None}

    config.require_api_key()
    llm = ChatOpenAI(model=config.OPENAI_CHAT_MODEL, temperature=0, api_key=config.OPENAI_API_KEY)
    return _ask_llm(llm, query, chunks, not_covered_message)


def answer_across_documents(query: str) -> dict:
    """Answers the question against every ingested document independently, so the response
    is explicit about which documents actually cover the topic and which don't — rather than
    one blended answer that silently favors whichever chunk happens to rank highest overall.

    Returns {"per_document": [{"document": str, "answer": str, "sources": list}, ...]}.
    """
    query = query.strip()
    if not query:
        return {
            "per_document": [
                {"document": None, "answer": "Please enter a question.", "sources": [], "quote": None}
            ]
        }

    doc_names = list_ingested_documents()
    if not doc_names:
        return {
            "per_document": [
                {
                    "document": None,
                    "answer": "No documents have been uploaded yet.",
                    "sources": [],
                    "quote": None,
                }
            ]
        }

    not_covered_message = "This document does not cover this topic."
    llm = None
    results = []

    for doc_name in doc_names:
        chunks = retrieve(query, source_filter=doc_name)

        if not has_relevant_context(chunks):
            results.append(
                {"document": doc_name, "answer": not_covered_message, "sources": [], "quote": None}
            )
            continue

        if llm is None:  # only construct once, and only if at least one doc needs it
            config.require_api_key()
            llm = ChatOpenAI(model=config.OPENAI_CHAT_MODEL, temperature=0, api_key=config.OPENAI_API_KEY)

        result = _ask_llm(llm, query, chunks, not_covered_message)
        results.append({"document": doc_name, **result})

    return {"per_document": results}


def _source_info(chunk: RetrievedChunk) -> dict:
    """Full citation for one retrieved chunk: document, page, paragraph number (its position
    within the document), and the complete excerpt — not a truncated fragment, since each
    chunk is already sized to be one coherent paragraph (see CHUNK_SIZE in config.py)."""
    meta = chunk.document.metadata
    return {
        "source_file": meta.get("source_file", "unknown"),
        "page": meta.get("page", "?"),
        "paragraph": meta.get("chunk_index", 0) + 1,
        "excerpt": chunk.document.page_content.strip(),
    }
