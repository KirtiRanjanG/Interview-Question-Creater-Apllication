import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # must run before rag imports so OPENAI_API_KEY is available

from fastapi import FastAPI, File, HTTPException, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import rag  # noqa: E402

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_BYTES = 20 * 1024 * 1024  # 20 MB

app = FastAPI(title="PDF Q&A API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    doc_id: str
    question: str = Field(min_length=1, max_length=2000)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/upload")
def upload(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Please upload a PDF file.")

    data = file.file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "PDF is too large (max 20 MB).")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "File does not look like a valid PDF.")

    doc_id = uuid.uuid4().hex
    path = UPLOAD_DIR / f"{doc_id}.pdf"
    path.write_bytes(data)

    try:
        stats = rag.ingest_pdf(path, doc_id)
    except ValueError as e:
        path.unlink(missing_ok=True)
        raise HTTPException(422, str(e))
    except Exception as e:  # e.g. bad API key, network, corrupt PDF
        path.unlink(missing_ok=True)
        raise HTTPException(500, f"Failed to process PDF: {e}")

    return {"doc_id": doc_id, "filename": file.filename, **stats}


@app.post("/api/ask")
def ask(req: AskRequest):
    try:
        return rag.answer_question(req.doc_id, req.question)
    except FileNotFoundError:
        raise HTTPException(404, "Document not found. Please upload it again.")
    except Exception as e:
        raise HTTPException(500, f"Failed to answer: {e}")
