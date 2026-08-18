# SmartDoc — Document Q&A Assistant

A RAG (Retrieval-Augmented Generation) assistant that answers plain-English questions over a
library of PDF documents, with source citations on every answer.

## How it works

```
PDF upload → parse text (PyPDFLoader) → chunk (400 chars, 70 overlap) →
embed (OpenAI text-embedding-3-small) → store in ChromaDB (persisted to disk)

User question → embed question → similarity search (top 5 chunks) →
if similarity too low: return "not covered" without calling the LLM →
otherwise: GPT answers using ONLY the retrieved chunks → answer + citations
  (only chunks close to the top match are cited — see "Why these choices" below)
```

## Why these choices

- **ChromaDB over keyword search**: semantic embeddings match paraphrases and synonyms
  ("termination clause" ↔ "how this agreement ends"), which substring/keyword search cannot.
- **Chunk size 400 / overlap 70** *(started at 800/150, see below)*: small enough to keep each
  chunk's embedding focused on roughly one section, large enough to hold a complete thought.
  Overlap prevents losing meaning when a sentence is split across a chunk boundary.
  **Why it changed from 800/150:** at 800 characters, `pypdf`'s text extraction doesn't reliably
  preserve the blank-line breaks between a PDF's original sections, so the splitter's paragraph
  separator rarely fired — it fell back to single newlines and kept packing text until it hit
  800 characters regardless of topic, producing chunks that blended 3-4 unrelated sections
  together. That hurt retrieval (a chunk's embedding is now a blur of multiple topics instead of
  one) *and* citations (the "paragraph" shown to the user was actually several unrelated
  paragraphs stitched together). Cutting the size to 400 keeps each chunk much closer to one
  actual section.
- **Relevance gate before the LLM call**: retrieved chunks below a similarity threshold are
  treated as "not relevant enough" — the app returns "not covered by the documents" directly
  instead of calling the LLM, which is the main defense against hallucinating on out-of-scope
  questions.
- **The LLM's own verdict decides citations, not just the similarity gate**: chunks from the same
  document share enough vocabulary that even an unrelated section can clear the relevance gate
  (e.g. "social media policy" scored 0.68 similarity against the *Anti-Harassment* section, not
  just the *Social Media* section). So the LLM is instructed to emit an exact `NOT_COVERED` token
  when the excerpts don't actually answer the question — checked before any chunk is cited — and
  on top of that, only chunks within a small margin of the *best* match in that retrieval are
  cited at all, not every chunk that was merely retrieved. This is the concrete answer to "where
  is your system most likely to give a wrong answer": a topically-adjacent chunk in the same
  document can outrank the truly relevant one if the question is phrased ambiguously.

## Setup

1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. `cp .env.example .env` and add your `OPENAI_API_KEY`

## Run

Two processes, in separate terminals:

```bash
uvicorn backend.main:app --reload
streamlit run app.py
```

Open the Streamlit URL it prints (usually `http://localhost:8501`), upload PDFs in the sidebar,
then ask questions in the chat box. Each ingested document has a 🗑️ button next to it in the
sidebar to remove it (and its chunks) from the vector store.

## Sample documents

`sample_docs/` contains 5 synthetic PDFs for a fictional company ("Clearwave Technologies") —
two HR policies, a product manual, an onboarding guide, and an SOP — covering exactly the
document types this mission targets. They're generated (not hand-written) so the facts inside
are consistent and known in advance, which makes them good material for demoing citations and
testing retrieval:

```
sample_docs/
├── 01_HR_Time_Off_Leave_Policy.pdf
├── 02_HR_Code_of_Conduct_Policy.pdf
├── 03_Product_Manual_TicketDesk_Admin_Guide.pdf
├── 04_New_Hire_Onboarding_Guide.pdf
└── 05_SOP_IT_Helpdesk_Incident_Escalation.pdf
```

Upload these via the Streamlit sidebar to test the pipeline. Example questions to try:

- "How many PTO days do I get after 3 years?" → *20 days* (`01_HR_Time_Off_Leave_Policy.pdf`)
- "What's the response time for a Sev 1 incident?" → *15 minutes* (`05_SOP_IT_Helpdesk_Incident_Escalation.pdf`)
- "What's the API rate limit for TicketDesk?" → *100 requests/min per key* (`03_Product_Manual...`)
- "What's Clearwave's stock ticker symbol?" → **out of scope** — none of the documents cover this;
  the app should say so rather than guessing (this is the hallucination check, M6S5).

Regenerate or edit them anytime:

```bash
pip install reportlab
python scripts/generate_sample_docs.py
```

## Tests

```bash
pytest tests/ -v
```

## Project structure

```
smartdoc/
├── app.py                  # Streamlit UI
├── scripts/
│   └── generate_sample_docs.py  # regenerates the synthetic PDFs in sample_docs/
├── sample_docs/             # 5 synthetic test PDFs (see above)
├── backend/
│   ├── config.py           # env vars, chunk size/overlap, relevance threshold
│   ├── ingest.py            # PDF parsing, chunking, embedding, persistence, deletion
│   ├── retrieve.py          # similarity search + relevance gate
│   ├── rag_chain.py         # prompt construction + LLM call
│   └── main.py               # FastAPI endpoints (/upload, /query, /documents, DELETE /documents/{filename})
├── data/
│   ├── uploads/              # raw PDFs
│   └── chroma_db/             # persisted vector store
└── tests/
    └── test_pipeline.py
```

## Known limitations

- Scanned/image-only PDFs with no extractable text will fail ingestion (no OCR yet).
- Non-English documents work only as well as the embedding model and GPT handle that language —
  not specifically tuned for multilingual retrieval.
- The relevance gate is similarity-based, not a full hallucination check — it prevents answering
  from irrelevant context, but doesn't verify every factual claim in a generated answer.
