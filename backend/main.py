import shutil

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend import config
from backend.ingest import delete_document, ingest_pdf, list_ingested_documents
from backend.rag_chain import answer_across_documents, answer_question, resolve_question

app = FastAPI(title="SmartDoc API")


class HistoryTurn(BaseModel):
    question: str
    answer: str


class QueryRequest(BaseModel):
    question: str
    documents: list[str] = []
    history: list[HistoryTurn] = []


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "openai_key_configured": bool(config.OPENAI_API_KEY)}


@app.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    filename = config.safe_filename(file.filename)
    if not filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    dest = config.UPLOAD_DIR / filename
    try:
        with dest.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        chunk_count = ingest_pdf(dest)
    except Exception as exc:  
        raise HTTPException(status_code=500, detail=f"Failed to process '{filename}': {exc}") from exc

    if chunk_count == 0:
        raise HTTPException(
            status_code=422,
            detail=f"'{filename}' produced no extractable text (scanned/empty PDF?).",
        )

    return {"filename": filename, "chunks_added": chunk_count}


@app.get("/documents")
def documents() -> dict:
    return {"documents": list_ingested_documents()}


@app.delete("/documents/{filename}")
def remove_document(filename: str) -> dict:
    try:
        removed_count = delete_document(filename)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to remove '{filename}': {exc}") from exc

    if removed_count == 0:
        raise HTTPException(status_code=404, detail=f"No document named '{filename}' was found.")

    return {"filename": filename, "chunks_removed": removed_count}


@app.post("/query")
def query(payload: QueryRequest) -> dict:
    try:
        history = [turn.model_dump() for turn in payload.history]
        resolved_question = resolve_question(payload.question, history)

        if len(payload.documents) == 1:
            result = answer_question(resolved_question, source_filter=payload.documents[0])
        else:
            result = answer_across_documents(resolved_question, doc_names=payload.documents or None)
        if resolved_question != payload.question.strip():
            result["resolved_question"] = resolved_question
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Upstream LLM/embedding call failed: {exc}") from exc
