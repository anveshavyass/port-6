import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend import config
from backend.ingest import get_full_document_text, list_ingested_documents
from backend.retrieve import RetrievedChunk, has_relevant_context, retrieve

NOT_COVERED_SENTINEL = "NOT_COVERED"

SYSTEM_PROMPT = (
    "You are SmartDoc, an assistant that answers questions using ONLY the document "
    "excerpts provided below. Follow these rules strictly:\n"
    "1. Base your answer only on the provided excerpts — do not use outside knowledge.\n"
    f"2. If the excerpts do not contain enough information to answer, respond with EXACTLY "
    f"the single word {NOT_COVERED_SENTINEL} and nothing else — no punctuation, no explanation, "
    f"and never wrapped in the ANSWER/QUOTE format below.\n"
    "3. Otherwise (i.e. only when the excerpts DO answer the question), respond in exactly "
    "this two-line format and nothing else:\n"
    "ANSWER: <a concise, direct answer to the question>\n"
    "QUOTE: <the exact sentence copied character-for-character from the excerpts above that "
    "most directly supports the answer — do not paraphrase or alter it>\n"
    "4. Do not fabricate document names, page numbers, or facts not present in the excerpts."
)

SUMMARY_SYSTEM_PROMPT = (
    "You are SmartDoc. Write a concise summary of the ENTIRE document provided below: its "
    "purpose, its main sections, and the key facts a reader would need. Base the summary "
    "only on the text given — do not use outside knowledge or invent details not present in it."
)

_SUMMARY_INTENT_RE = re.compile(
    r"\b(summarize|summarise|summary|overview|tl;?dr)\b"
    r"|what('?s| is) (this|the) document (about|cover)"
    r"|what does (this|the) document (cover|contain|say)",
    re.IGNORECASE,
)


def is_summary_request(question: str) -> bool:
    return bool(_SUMMARY_INTENT_RE.search(question))


def summarize_document(doc_name: str) -> dict:
    full_text = get_full_document_text(doc_name)
    if not full_text:
        return {"answer": f"'{doc_name}' has no ingested content to summarize.", "sources": [], "quote": None}

    config.require_api_key()
    llm = ChatOpenAI(model=config.OPENAI_CHAT_MODEL, temperature=0, api_key=config.OPENAI_API_KEY)
    messages = [
        SystemMessage(content=SUMMARY_SYSTEM_PROMPT),
        HumanMessage(content=f"Document: {doc_name}\n\n{full_text}"),
    ]
    response = llm.invoke(messages)
    return {"answer": response.content.strip(), "sources": [], "quote": None}


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
    if answer_text.upper().startswith(NOT_COVERED_SENTINEL):
        return {"answer": not_covered_message, "sources": [], "quote": None}

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
    query = query.strip()
    if not query:
        return {"answer": "Please enter a question.", "sources": [], "quote": None}

    if source_filter and is_summary_request(query):
        return summarize_document(source_filter)

    scope = f"'{source_filter}'" if source_filter else "the uploaded documents"
    not_covered_message = (
        f"I don't have enough relevant information in {scope} to answer this. "
        "Try rephrasing, or confirm this topic is actually covered there."
    )

    chunks = retrieve(query, source_filter=source_filter)

    if not has_relevant_context(chunks):
        return {"answer": not_covered_message, "sources": [], "quote": None}

    config.require_api_key()
    llm = ChatOpenAI(model=config.OPENAI_CHAT_MODEL, temperature=0, api_key=config.OPENAI_API_KEY)
    return _ask_llm(llm, query, chunks, not_covered_message)


def answer_across_documents(query: str, doc_names: list[str] | None = None) -> dict:
    """Answers against doc_names independently, or every ingested document if doc_names is
    None — used both for the unscoped "All documents" case and for a specific multi-document
    selection, since either way there's no single "most relevant" chunk to blend across files."""
    query = query.strip()
    if not query:
        return {
            "per_document": [
                {"document": None, "answer": "Please enter a question.", "sources": [], "quote": None}
            ]
        }

    if doc_names is None:
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
    summary_mode = is_summary_request(query)
    llm = None
    results = []

    for doc_name in doc_names:
        if summary_mode:
            results.append({"document": doc_name, **summarize_document(doc_name)})
            continue

        chunks = retrieve(query, source_filter=doc_name)

        if not has_relevant_context(chunks):
            results.append(
                {"document": doc_name, "answer": not_covered_message, "sources": [], "quote": None}
            )
            continue

        if llm is None: 
            config.require_api_key()
            llm = ChatOpenAI(model=config.OPENAI_CHAT_MODEL, temperature=0, api_key=config.OPENAI_API_KEY)

        result = _ask_llm(llm, query, chunks, not_covered_message)
        results.append({"document": doc_name, **result})

    return {"per_document": results}


def _source_info(chunk: RetrievedChunk) -> dict:
    meta = chunk.document.metadata
    return {
        "source_file": meta.get("source_file", "unknown"),
        "page": meta.get("page", "?"),
        "paragraph": meta.get("chunk_index", 0) + 1,
        "excerpt": chunk.document.page_content.strip(),
    }
