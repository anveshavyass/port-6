import html
import os
import re
from urllib.parse import quote

import requests
import streamlit as st
from dotenv import load_dotenv

from backend import chat_history

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
MAX_HISTORY_TURNS = 5

chat_history.init_db()

st.set_page_config(page_title="SmartDoc", page_icon="📖", layout="wide")
st.title("📖 SmartDoc")
st.caption("Upload PDFs, then ask questions grounded only in their content.")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None


def _append_message(message: dict) -> None:
    st.session_state.messages.append(message)
    chat_history.save_message(st.session_state.conversation_id, message)


def backend_reachable() -> bool:
    try:
        resp = requests.get(f"{BACKEND_URL}/health", timeout=3)
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False


def _find_quote_span(excerpt: str, quote: str) -> tuple[int, int] | None:
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
    for block in blocks:
        if block.get("document"):
            st.markdown(f"**📄 {block['document']}**")
        st.markdown(block["answer"])
        if block.get("sources"):
            with st.expander(f"Sources — {block.get('document', 'this document')}"):
                render_sources(block["sources"], block.get("quote"))
        st.divider()


def _format_scope(scope: list[str]) -> str:
    if not scope:
        return "All documents"
    if len(scope) == 1:
        return scope[0]
    return f"{len(scope)} documents ({', '.join(scope)})"


def _history_answer_text(message: dict) -> str:
    if message.get("per_document"):
        parts = [f"{b['document']}: {b['answer']}" for b in message["per_document"] if b.get("document")]
        return " | ".join(parts) if parts else ""
    return message.get("content", "")


def build_history(messages: list[dict]) -> list[dict]:
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
    chats_tab, docs_tab = st.tabs(["💬 Chats", "📄 Documents"])

    with chats_tab:
        if st.button("➕ New chat", use_container_width=True, type="primary"):
            st.session_state.messages = []
            st.session_state.conversation_id = None
            st.rerun()

        st.divider()

        conversations = chat_history.list_conversations()
        if not conversations:
            st.caption("No chats yet — ask a question to start one.")

        for conv in conversations:
            is_current = conv["id"] == st.session_state.conversation_id
            chat_col, delete_col = st.columns([5, 1])
            with chat_col:
                if st.button(
                    conv["title"],
                    key=f"conv_{conv['id']}",
                    use_container_width=True,
                    type="primary" if is_current else "secondary",
                ):
                    st.session_state.conversation_id = conv["id"]
                    st.session_state.messages = chat_history.load_messages(conv["id"])
                    st.rerun()
            with delete_col:
                with st.popover("🗑️"):
                    st.caption(f"Delete “{conv['title']}”?")
                    if st.button("Confirm delete", key=f"del_conv_{conv['id']}"):
                        chat_history.delete_conversation(conv["id"])
                        if is_current:
                            st.session_state.messages = []
                            st.session_state.conversation_id = None
                        st.rerun()

    with docs_tab:
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
        if uploaded_files and st.button("Ingest documents", use_container_width=True):
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

        st.divider()
        with st.expander(f"📚 Ingested documents ({len(docs)})", expanded=len(docs) <= 5):
            if docs:
                for d in docs:
                    with st.container(border=True):
                        st.markdown(f"📄 {d}")
                        with st.popover("🗑️ Remove", use_container_width=True):
                            st.caption(f"Remove “{d}” and delete its file?")
                            if st.button("Confirm remove", key=f"remove_{d}"):
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
            st.caption(f"🔎 Scoped to: {_format_scope(message['scope'])}")
        if message.get("resolved_question"):
            st.caption(f"🔁 Interpreted as: {message['resolved_question']}")
        if message.get("per_document"):
            render_per_document(message["per_document"])
        else:
            st.markdown(message["content"])
            if message.get("sources"):
                with st.expander("Sources"):
                    render_sources(message["sources"], message.get("quote"))

if docs:
    current_scope = st.session_state.get("doc_scope", [])
    with st.popover(f"🔎 {_format_scope(current_scope)}"):
        scope_choice = st.multiselect(
            "Ask about",
            docs,
            key="doc_scope",
            placeholder="All documents",
            help=(
                "Leave empty to check every ingested document independently and report which "
                "ones cover the topic. Pick one document to get a single focused answer, or "
                "pick several to check just that subset independently."
            ),
        )
else:
    scope_choice = []

question = st.chat_input("Ask a question about your documents")

if question:
    if not question.strip():
        st.warning("Please enter a question.")
    else:
        selected_docs = scope_choice

        if st.session_state.conversation_id is None:
            st.session_state.conversation_id = chat_history.create_conversation(question)

        _append_message({"role": "user", "content": question, "scope": selected_docs})
        with st.chat_message("user"):
            st.markdown(question)
            if selected_docs:
                st.caption(f"🔎 Scoped to: {_format_scope(selected_docs)}")

        with st.chat_message("assistant"):
            with st.spinner("Checking documents..."):
                try:
                    history = build_history(st.session_state.messages)
                    resp = requests.post(
                        f"{BACKEND_URL}/query",
                        json={"question": question, "documents": selected_docs, "history": history},
                        timeout=120,
                    )
                    if resp.status_code == 200:
                        result = resp.json()
                        resolved_question = result.get("resolved_question")
                        if resolved_question:
                            st.caption(f"🔁 Interpreted as: {resolved_question}")

                        if "per_document" in result:
                            render_per_document(result["per_document"])
                            _append_message(
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
                            _append_message(
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
                        _append_message({"role": "assistant", "content": f"⚠️ {error_msg}"})
                except requests.exceptions.RequestException as exc:
                    error_msg = f"Could not reach the backend: {exc}"
                    st.error(error_msg)
                    _append_message({"role": "assistant", "content": f"⚠️ {error_msg}"})
