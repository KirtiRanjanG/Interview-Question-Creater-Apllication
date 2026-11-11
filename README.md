# PDF Q&A (LangChain + ChromaDB + FastAPI + OpenAI + React)

Upload a PDF, then ask questions about it. Answers are grounded in the document and cite page numbers.

## How it works

1. **Upload** → FastAPI saves the PDF, `PyPDFLoader` extracts text per page.
2. **Chunk** → `RecursiveCharacterTextSplitter` (1000 chars, 150 overlap).
3. **Embed + store** → OpenAI embeddings stored in a ChromaDB collection per PDF (persisted in `backend/chroma_db/`).
4. **Ask** → question is embedded, top 4 chunks are retrieved from Chroma, and the OpenAI chat model answers using only that context.

## Run the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then put your OPENAI_API_KEY in .env
uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. To point at a different backend, set `VITE_API_URL` (e.g. in `frontend/.env`).

## Endpoints

| Method | Path          | Body                          | Returns                                   |
|--------|---------------|-------------------------------|-------------------------------------------|
| POST   | `/api/upload` | multipart `file` (PDF)        | `doc_id`, `filename`, `pages`, `chunks`   |
| POST   | `/api/ask`    | `{ "doc_id", "question" }`    | `answer`, `sources[{page, snippet}]`      |
| GET    | `/api/health` | –                             | `{ "status": "ok" }`                      |

## Notes / ideas to extend

- Scanned PDFs have no text layer and are rejected (add OCR, e.g. `pytesseract`, to support them).
- Add chat history to the prompt for follow-up questions.
- Query across several PDFs at once and stream answers with Server-Sent Events.
- Add auth and per-user storage before deploying, and delete old collections/uploads on a schedule.
- Use Python 3.11-3.13; very new Python versions often lack prebuilt wheels for dependencies like `chromadb`.
