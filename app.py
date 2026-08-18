"""SmartDoc — Streamlit chat UI over the FastAPI RAG backend."""

import html
import os
import re
from urllib.parse import quote

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
ALL_DOCS_OPTION = "All documents"
# How many recent Q&A turns to send back for follow-up resolution (e.g. "what about after 5
# years?"). Capped independently of the backend's own FOLLOWUP_HISTORY_TURNS — the two
# services don't share a config module, since either could run on its own host.
MAX_HISTORY_TURNS = 5

st.set_page_config(page_title="SmartDoc", page_icon="📖", layout="wide")
st.title("📖 SmartDoc — Ask your documents")

if "messages" not in st.session_state:
    st.session_state.messages = []


def backend_reachable() -> bool:
    try:
        resp = requests.get(f"{BACKEND_URL}/health", timeout=3)
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False


def _find_quote_span(excerpt: str, quote: str) -> tuple[int, int] | None:
    """Locates the LLM-supplied supporting quote inside the raw excerpt. Matches whitespace
    loosely (line-wrapped PDF text won't have the same spacing the model copied), so a quote
    is still found even when the model reproduced it with different line breaks."""
    words = quote.split()
    if not words:
        return None
    pattern = r"\s+".join(re.escape(w) for w in words)
    match = re.search(pattern, excerpt, re.IGNORECASE)
    return (match.start(), match.end()) if match else None


def render_sources(sources: list[dict], quote: str | None = None) -> None:
    for src in sources:
        st.markdown(f"**{src['source_file']}** — page {src['page']}, paragraph {src['paragraph']}")
        excerpt = src["excerpt"]
        span = _find_quote_span(excerpt, quote) if quote else None
        # Raw HTML in a pre-wrapped div, not st.text/st.markdown: st.text can't highlight a
        # span, and st.markdown misreads raw PDF lines like "4. Reporting Procedure" as a new
        # ordered list. Escaping everything outside the <mark> keeps the excerpt exact either
        # way, so this replaces the plain-text rendering rather than sitting alongside it.
        if span:
            start, end = span
            body = (
                f"{html.escape(excerpt[:start])}"
                f'<mark style="background-color:#ffe066;color:#1a1a1a;padding:0 2px;'
                f'border-radius:2px;">{html.escape(excerpt[start:end])}</mark>'
                f"{html.escape(excerpt[end:])}"
            )
        else:
            body = html.escape(excerpt)
        st.markdown(
            f'<div style="white-space:pre-wrap;font-family:monospace;font-size:0.85rem;'
            f'line-height:1.4;">{body}</div>',
            unsafe_allow_html=True,
        )


def render_per_document(blocks: list[dict]) -> None:
    """Renders the 'All documents' response: one section per ingested document."""
    for block in blocks:
        if block.get("document"):
            st.markdown(f"**📄 {block['document']}**")
        st.markdown(block["answer"])
        if block.get("sources"):
            with st.expander(f"Sources — {block.get('document', 'this document')}"):
                render_sources(block["sources"], block.get("quote"))
        st.divider()


def _history_answer_text(message: dict) -> str:
    """Condenses an assistant turn into one line for the follow-up resolver — the full
    per-document breakdown isn't needed to resolve a pronoun, just the gist of what was said."""
    if message.get("per_document"):
        parts = [f"{b['document']}: {b['answer']}" for b in message["per_document"] if b.get("document")]
        return " | ".join(parts) if parts else ""
    return message.get("content", "")


def build_history(messages: list[dict]) -> list[dict]:
    """Pairs up completed user/assistant turns (skipping the just-appended, not-yet-answered
    question) for the backend's follow-up resolver."""
    turns = []
    i = 0
    while i < len(messages) - 1:
        if messages[i]["role"] == "user" and messages[i + 1]["role"] == "assistant":
            turns.append(
                {"question": messages[i]["content"], "answer": _history_answer_text(messages[i + 1])}
            )
            i += 2
        else:
            i += 1
    return turns[-MAX_HISTORY_TURNS:]


with st.sidebar:
    st.header("Upload documents")

    if not backend_reachable():
        st.error(
            "Can't reach the backend API. Start it with:\n\n"
            "`uvicorn backend.main:app --reload`"
        )
    else:
        health = requests.get(f"{BACKEND_URL}/health", timeout=3).json()
        if not health.get("openai_key_configured"):
            st.warning("OPENAI_API_KEY is not set on the backend. Add it to .env and restart.")

    uploaded_files = st.file_uploader(
        "Upload PDF documents", type=["pdf"], accept_multiple_files=True
    )
    if uploaded_files and st.button("Ingest documents"):
        for uploaded_file in uploaded_files:
            with st.spinner(f"Processing {uploaded_file.name}..."):
                try:
                    resp = requests.post(
                        f"{BACKEND_URL}/upload",
                        files={"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")},
                        timeout=120,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        st.success(f"{data['filename']}: {data['chunks_added']} chunks added")
                    else:
                        st.error(f"{uploaded_file.name}: {resp.json().get('detail', resp.text)}")
                except requests.exceptions.RequestException as exc:
                    st.error(f"{uploaded_file.name}: connection error — {exc}")

    try:
        docs_resp = requests.get(f"{BACKEND_URL}/documents", timeout=5)
        docs = docs_resp.json().get("documents", []) if docs_resp.status_code == 200 else []
    except requests.exceptions.RequestException:
        docs = []

    # Placed near the top of the sidebar, above the (potentially long) ingested-documents
    # list, so it's never pushed out of view. The sidebar scrolls independently of the chat
    # history, so this stays visible no matter how far down the conversation you've scrolled
    # — a plain CSS "sticky" bar above the chat can't do that, because Streamlit's chat
    # container wraps it in an element with no room for it to stick within.
    st.divider()
    st.subheader("Ask about")
    if docs:
        scope_choice = st.selectbox(
            "Scope",
            [ALL_DOCS_OPTION] + docs,
            key="doc_scope",
            label_visibility="collapsed",
            help=(
                "'All documents' checks every ingested document independently and reports "
                "which ones cover the topic. Pick one document to restrict the question to "
                "just that file."
            ),
        )
    else:
        scope_choice = ALL_DOCS_OPTION

    st.divider()
    st.subheader("Ingested documents")
    if docs:
        for d in docs:
            # Filename on its own row, full-width remove button on the row below — nothing
            # sits beside anything, so there is nothing for a long filename to collide with.
            with st.container(border=True):
                st.markdown(f"📄 {d}")
                if st.button("🗑️ Remove", key=f"remove_{d}", use_container_width=True):
                    try:
                        del_resp = requests.delete(
                            f"{BACKEND_URL}/documents/{quote(d, safe='')}", timeout=30
                        )
                        if del_resp.status_code == 200:
                            st.success(f"Removed {d}")
                            st.rerun()
                        else:
                            st.error(del_resp.json().get("detail", del_resp.text))
                    except requests.exceptions.RequestException as exc:
                        st.error(f"Connection error: {exc}")
    else:
        st.caption("No documents ingested yet.")

if not docs:
    st.info("Upload at least one PDF in the sidebar to start asking questions.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("scope"):
            st.caption(f"🔎 Scoped to: {message['scope']}")
        if message.get("resolved_question"):
            st.caption(f"🔁 Interpreted as: {message['resolved_question']}")
        if message.get("per_document"):
            render_per_document(message["per_document"])
        else:
            st.markdown(message["content"])
            if message.get("sources"):
                with st.expander("Sources"):
                    render_sources(message["sources"], message.get("quote"))

question = st.chat_input("Ask a question about your documents")

if question:
    if not question.strip():
        st.warning("Please enter a question.")
    else:
        selected_doc = None if scope_choice == ALL_DOCS_OPTION else scope_choice

        st.session_state.messages.append(
            {"role": "user", "content": question, "scope": selected_doc}
        )
        with st.chat_message("user"):
            st.markdown(question)
            if selected_doc:
                st.caption(f"🔎 Scoped to: {selected_doc}")

        with st.chat_message("assistant"):
            with st.spinner("Checking documents..."):
                try:
                    history = build_history(st.session_state.messages)
                    resp = requests.post(
                        f"{BACKEND_URL}/query",
                        json={"question": question, "document": selected_doc, "history": history},
                        # Unscoped queries check every document independently — allow more time.
                        timeout=120,
                    )
                    if resp.status_code == 200:
                        result = resp.json()
                        resolved_question = result.get("resolved_question")
                        if resolved_question:
                            st.caption(f"🔁 Interpreted as: {resolved_question}")

                        if "per_document" in result:
                            render_per_document(result["per_document"])
                            st.session_state.messages.append(
                                {
                                    "role": "assistant",
                                    "content": "",
                                    "per_document": result["per_document"],
                                    "resolved_question": resolved_question,
                                }
                            )
                        else:
                            answer = result["answer"]
                            st.markdown(answer)
                            if result.get("sources"):
                                with st.expander("Sources"):
                                    render_sources(result["sources"], result.get("quote"))
                            st.session_state.messages.append(
                                {
                                    "role": "assistant",
                                    "content": answer,
                                    "sources": result.get("sources", []),
                                    "quote": result.get("quote"),
                                    "resolved_question": resolved_question,
                                }
                            )
                    else:
                        error_msg = resp.json().get("detail", "Unknown error from backend.")
                        st.error(error_msg)
                        st.session_state.messages.append(
                            {"role": "assistant", "content": f"⚠️ {error_msg}"}
                        )
                except requests.exceptions.RequestException as exc:
                    error_msg = f"Could not reach the backend: {exc}"
                    st.error(error_msg)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": f"⚠️ {error_msg}"}
                    )
