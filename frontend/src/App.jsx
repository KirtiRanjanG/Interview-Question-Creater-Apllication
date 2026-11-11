import { useEffect, useRef, useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options) {
  const res = await fetch(`${API}${path}`, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
  return body;
}

export default function App() {
  const [doc, setDoc] = useState(null); // { doc_id, filename, pages, chunks }
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef(null);
  const chatEnd = useRef(null);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, asking]);

  async function uploadFile(file) {
    if (!file) return;
    setError("");
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Please choose a PDF file.");
      return;
    }
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const data = await request("/api/upload", { method: "POST", body: form });
      setDoc(data);
      setMessages([]);
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  }

  async function sendQuestion(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q || asking || !doc) return;
    setError("");
    setQuestion("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setAsking(true);
    try {
      const data = await request("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_id: doc.doc_id, question: q }),
      });
      setMessages((m) => [
        ...m,
        { role: "assistant", text: data.answer, sources: data.sources },
      ]);
    } catch (e) {
      setError(e.message);
    } finally {
      setAsking(false);
    }
  }

  function reset() {
    setDoc(null);
    setMessages([]);
    setError("");
    if (fileInput.current) fileInput.current.value = "";
  }

  return (
    <div className="app">
      <header>
        <h1>PDF Q&amp;A</h1>
        <p>Upload a PDF and ask questions about it.</p>
      </header>

      {!doc ? (
        <div
          className={`dropzone ${dragging ? "dragging" : ""}`}
          onClick={() => fileInput.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            uploadFile(e.dataTransfer.files[0]);
          }}
        >
          <input
            ref={fileInput}
            type="file"
            accept="application/pdf,.pdf"
            hidden
            onChange={(e) => uploadFile(e.target.files[0])}
          />
          {uploading ? (
            <p>Processing PDF… this can take a few seconds.</p>
          ) : (
            <>
              <p className="big">Drop a PDF here</p>
              <p>or click to browse (max 20 MB)</p>
            </>
          )}
        </div>
      ) : (
        <>
          <div className="docbar">
            <span>
              <strong>{doc.filename}</strong> · {doc.pages} pages · {doc.chunks} chunks
            </span>
            <button className="ghost" onClick={reset}>
              Upload another
            </button>
          </div>

          <div className="chat">
            {messages.length === 0 && (
              <p className="hint">Ask anything about your document to get started.</p>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                <div className="bubble">{m.text}</div>
                {m.sources?.length > 0 && (
                  <details className="sources">
                    <summary>Sources (pages {[...new Set(m.sources.map((s) => s.page))].join(", ")})</summary>
                    {m.sources.map((s, j) => (
                      <p key={j}>
                        <strong>p.{s.page}</strong> — {s.snippet}…
                      </p>
                    ))}
                  </details>
                )}
              </div>
            ))}
            {asking && (
              <div className="msg assistant">
                <div className="bubble typing">Thinking…</div>
              </div>
            )}
            <div ref={chatEnd} />
          </div>

          <form className="composer" onSubmit={sendQuestion}>
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question about the PDF…"
              disabled={asking}
            />
            <button type="submit" disabled={asking || !question.trim()}>
              Ask
            </button>
          </form>
        </>
      )}

      {error && <div className="error">{error}</div>}
    </div>
  );
}
