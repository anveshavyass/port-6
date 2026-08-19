# SmartDoc — Document Q&A Assistant

**Turn a library of PDF documents into a grounded, cited Q&A assistant — ask in plain English, get answers sourced back to the exact file, page, and paragraph.**

[![Backend](https://img.shields.io/badge/backend-FastAPI-009688)](backend)
[![Frontend](https://img.shields.io/badge/frontend-Streamlit-FF4B4B)](app.py)
[![Vector DB](https://img.shields.io/badge/vectors-ChromaDB-542CFF)](backend/ingest.py)
[![History](https://img.shields.io/badge/history-SQLite-003B57)](backend/chat_history.py)
[![LLM](https://img.shields.io/badge/LLM-GPT--4o--mini-412991)](backend/rag_chain.py)
[![Tests](https://img.shields.io/badge/tests-pytest-0a9edc)](tests)

## Problem statement

Answering a question by hand-searching PDF policies, manuals, and SOPs is slow, and pasting a
whole document into a chatbot invites the model to guess when the document doesn't actually cover
the question. SmartDoc retrieves only the passages relevant to a question, forces the LLM to
answer from those passages alone, and cites exactly where each answer came from — so a wrong
answer is either grounded and traceable, or the system says so instead of guessing.

## What it does

1. Ingests uploaded PDFs — chunks, embeds, and persists them to a vector store.
2. Resolves follow-up questions into standalone ones using recent chat history.
3. Retrieves the top-5 most similar chunks, scoped to one, several, or all documents.
4. Gates on similarity — returns "not covered" without calling the LLM if nothing's relevant.
5. Otherwise, GPT answers using only the retrieved excerpts, with an extractable supporting quote.
6. Cites only chunks near the best match, not everything retrieved, to avoid wrong citations.
7. Answers whole-document summary requests from the full text instead of retrieved chunks.
8. Queries multiple selected documents independently and reports per-document.
9. Persists every conversation to SQLite so it can be reopened or deleted later.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Classification / answers / summaries | **OpenAI GPT-4o-mini** | Cheap, fast, good enough with strict prompt rules |
| Embeddings | **OpenAI `text-embedding-3-small`** | Cheap, fast, same vendor as the chat model |
| Vector store | **ChromaDB**, persisted to disk | Semantic search beats keyword search on paraphrases; no server needed at this scale |
| Chat history | **SQLite**, no ORM | Two simple tables; nothing to abstract |
| Backend | **FastAPI** | Async, typed, easy to test |
| Frontend | **Streamlit** | Chat UI + file upload with no separate frontend build |
| Secrets | `.env` (git-ignored) | No hardcoded keys anywhere in source |

## Core concepts

- **Chunking** — each PDF page is split into ~400-character pieces with 70 characters of overlap,
  breaking on paragraph/sentence boundaries where possible. Small chunks keep each embedding
  focused on one idea; overlap stops a sentence from being cut in half at a chunk boundary.
- **Embeddings** — every chunk (and every question) is converted to a vector via
  `text-embedding-3-small`. Vectors that are close together represent similar meaning, even if the
  wording differs.
- **Retrieval** — a question's vector is compared against all stored chunk vectors by cosine
  similarity; the top 5 closest chunks are pulled back as candidate context.
- **Relevance gate** — if those top chunks aren't similar enough to the question, the app skips
  the LLM entirely and says the topic isn't covered, instead of risking a made-up answer.
- **Grounded answering** — the LLM sees only the retrieved chunks (never the whole document) and
  must answer from them alone, replying with a fixed `NOT_COVERED` token if they don't actually
  answer the question.
- **Citation margin** — of the chunks sent to the LLM, only those within a small similarity margin
  of the single best match are shown as sources, so a same-document-but-wrong-section chunk isn't
  cited just because it was retrieved.
- **Follow-up resolution** — before retrieval, a quick LLM pass rewrites context-dependent
  questions (e.g. "what about after 5 years?") into a standalone question using recent chat turns.

## Sample documents

- Source: 5 synthetic PDFs for a fictional company ("Clearwave Technologies"), generated (not
  hand-written) so the facts inside are consistent and known in advance — good material for
  demoing citations and testing retrieval.
- Location: [`sample_docs/`](sample_docs) — two HR policies, a product manual, an onboarding
  guide, and an SOP, covering exactly the document types this project targets.
- Regenerate or edit them anytime: `pip install reportlab && python scripts/generate_sample_docs.py`
- Also tested against 3 real internal documents — Calfus policies pulled from GreytHR — which
  ingested cleanly and answered questions as expected, confirming the pipeline works beyond the
  synthetic sample set.

## Repo structure

```
Port_6/
├── README.md
├── requirements.txt
├── app.py                        
├── scripts/
│   └── generate_sample_docs.py   
├── sample_docs/                  
├── backend/
│   ├── main.py                   
│   ├── config.py                
│   ├── ingest.py                
│   ├── retrieve.py              
│   ├── rag_chain.py             
│   └── chat_history.py           
├── data/
│   ├── uploads/                 
│   ├── chroma_db/               
│   └── chat_history.db           
└── tests/
    └── test_pipeline.py
```

## API reference

Base URL: `http://localhost:8000` (Streamlit frontend talks to it over plain HTTP).

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check; also reports whether `OPENAI_API_KEY` is configured |
| `POST` | `/upload` | Upload and ingest a PDF (multipart, field `file`) |
| `GET` | `/documents` | List ingested document filenames |
| `DELETE` | `/documents/{filename}` | Remove a document and its vector store chunks |
| `POST` | `/query` | Ask a question — `{"question", "documents": [], "history": []}` → answer + citations, or `{"per_document": [...]}` when scoped to multiple documents |

## Interface

One Streamlit app, two sidebar tabs:

- **Documents** — upload PDFs, see what's ingested, remove a document (deletes both the file and
  its vector store chunks).
- **Chats** — start a new conversation, reopen a previous one, or delete it. Each is persisted to
  SQLite independently of the document library.

Above the chat box, a scope picker chooses whether a question is answered against all documents,
one, or a chosen subset — multi-document scope answers each document independently rather than
blending them into a single context.

## Setup

### Prerequisites

- Python 3.9+
- An `OPENAI_API_KEY`

### 1. Backend

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cat > .env <<EOF
OPENAI_API_KEY=sk-...
EOF
uvicorn backend.main:app --reload
```

### 2. Frontend

```bash
streamlit run app.py
```

Open the URL it prints (usually `http://localhost:8501`), upload PDFs in the sidebar, then ask
questions in the chat box.

## Testing & reliability

```bash
pytest tests/ -v
```
Run this command to test the system.
