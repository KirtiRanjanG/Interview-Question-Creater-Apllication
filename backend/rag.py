"""RAG pipeline: PDF -> chunks -> embeddings -> Chroma collection -> retrieval + OpenAI answer."""

import os
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHROMA_DIR = Path("chroma_db")
CHROMA_DIR.mkdir(exist_ok=True)

CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

_embeddings = None
_llm = None
_stores: dict[str, Chroma] = {}  # in-memory cache of opened collections

PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You answer questions about a PDF document using ONLY the context below. "
            "If the answer is not in the context, say you could not find it in the document. "
            "Be concise and accurate.\n\nContext:\n{context}",
        ),
        ("human", "{question}"),
    ]
)


def _collection_name(doc_id: str) -> str:
    return f"doc_{doc_id}"  # one Chroma collection per uploaded PDF


def _get_embeddings() -> OpenAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    return _embeddings


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model=CHAT_MODEL, temperature=0)
    return _llm


def ingest_pdf(pdf_path: Path, doc_id: str) -> dict:
    """Load a PDF, split it, embed the chunks and persist them in a Chroma collection."""
    pages = PyPDFLoader(str(pdf_path)).load()
    if not any(p.page_content.strip() for p in pages):
        raise ValueError(
            "No extractable text found. The PDF may be a scanned image (needs OCR)."
        )

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_documents(pages)
    chunks = filter_complex_metadata(chunks)  # Chroma only accepts simple metadata types

    store = Chroma.from_documents(
        chunks,
        _get_embeddings(),
        collection_name=_collection_name(doc_id),
        persist_directory=str(CHROMA_DIR),
    )
    _stores[doc_id] = store

    return {"pages": len(pages), "chunks": len(chunks)}


def _load_store(doc_id: str) -> Chroma:
    if doc_id in _stores:
        return _stores[doc_id]
    store = Chroma(
        collection_name=_collection_name(doc_id),
        embedding_function=_get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )
    if store._collection.count() == 0:
        raise FileNotFoundError(f"No document found for id {doc_id}")
    _stores[doc_id] = store
    return store


def answer_question(doc_id: str, question: str, k: int = 4) -> dict:
    """Retrieve the top-k chunks from Chroma and ask the LLM to answer from them."""
    store = _load_store(doc_id)
    docs = store.similarity_search(question, k=k)

    context = "\n\n".join(
        f"[Page {d.metadata.get('page', 0) + 1}]\n{d.page_content}" for d in docs
    )
    chain = PROMPT | _get_llm() | StrOutputParser()
    answer = chain.invoke({"context": context, "question": question})

    sources = [
        {
            "page": d.metadata.get("page", 0) + 1,
            "snippet": d.page_content[:300].strip(),
        }
        for d in docs
    ]
    return {"answer": answer, "sources": sources}
