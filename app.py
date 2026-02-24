from flask import Flask, render_template, request, redirect, url_for, session
import os, faiss, pickle, uuid
from dotenv import load_dotenv

from groq import Groq
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from db import (
    init_db,
    save_message,
    load_conversation,
    delete_conversation,
    list_conversations,
    create_conversation_if_not_exists
)

# ---------- SETUP ----------
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
embed_model = SentenceTransformer("all-MiniLM-L6-v2")

FAISS_DIR = "faiss_index"
INDEX_PATH = f"{FAISS_DIR}/index.faiss"
CHUNKS_PATH = f"{FAISS_DIR}/chunks.pkl"

init_db()

# ---------- AI FUNCTIONS ----------
def normal_chat(query):
    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": query}]
    )
    return res.choices[0].message.content

def ingest_pdf(path):
    reader = PdfReader(path)
    text = ""

    for page in reader.pages:
        if page.extract_text():
            text += page.extract_text()

    chunks = [text[i:i+500] for i in range(0, len(text), 500)]
    embeddings = embed_model.encode(chunks)

    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)

    os.makedirs(FAISS_DIR, exist_ok=True)
    faiss.write_index(index, INDEX_PATH)

    with open(CHUNKS_PATH, "wb") as f:
        pickle.dump(chunks, f)

def rag_answer(query):
    index = faiss.read_index(INDEX_PATH)

    with open(CHUNKS_PATH, "rb") as f:
        chunks = pickle.load(f)

    q_vec = embed_model.encode([query])
    _, ids = index.search(q_vec, k=3)

    context = "\n".join(chunks[i] for i in ids[0])

    prompt = f"""
Answer ONLY from the context below.

Context:
{context}

Question:
{query}
"""

    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content

# ---------- ROUTES ----------
@app.route("/", methods=["GET"])
def index():
    cid = request.args.get("cid") or str(uuid.uuid4())
    create_conversation_if_not_exists(cid)

    return render_template(
        "index.html",
        messages=load_conversation(cid),
        chats=list_conversations(),
        current_id=cid,
        doc_status=session.get("doc_status"),
        doc_name=session.get("doc_name"),
        doc_error=session.get("doc_error")
    )

@app.route("/chat", methods=["POST"])
def chat():
    cid = request.form.get("conversation_id")

    # FILE UPLOAD
    file = request.files.get("file")
    if file and file.filename:
        try:
            session["doc_status"] = "uploading"
            session.pop("doc_error", None)

            os.makedirs("uploads", exist_ok=True)
            path = f"uploads/{file.filename}"
            file.save(path)

            ingest_pdf(path)

            session["doc_status"] = "ready"
            session["doc_name"] = file.filename

        except Exception as e:
            session["doc_status"] = "error"
            session["doc_error"] = str(e)

    # CHAT
    query = request.form.get("query")
    if query:
        save_message(cid, "user", query)

        if os.path.exists(INDEX_PATH):
            answer = rag_answer(query)
        else:
            answer = normal_chat(query)

        save_message(cid, "assistant", answer)

    return redirect(url_for("index", cid=cid))

@app.route("/new")
def new_chat():
    session.pop("doc_status", None)
    session.pop("doc_name", None)
    session.pop("doc_error", None)
    return redirect(url_for("index", cid=str(uuid.uuid4())))

@app.route("/delete/<cid>")
def delete_chat(cid):
    delete_conversation(cid)
    return redirect(url_for("new_chat"))

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)