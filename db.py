import sqlite3
from datetime import datetime

DB_NAME = "chat_history.db"


# ---------- DATABASE CONNECTION ----------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ---------- INITIALIZE DATABASE ----------
def init_db():
    conn = get_db()
    c = conn.cursor()

    # Conversations table
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Messages table
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            role TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
    """)

    conn.commit()
    conn.close()


# ---------- CREATE CONVERSATION ----------
def create_conversation_if_not_exists(conversation_id):
    conn = get_db()
    c = conn.cursor()

    c.execute(
        "INSERT OR IGNORE INTO conversations (id, title) VALUES (?, ?)",
        (conversation_id, "New Chat")
    )

    conn.commit()
    conn.close()


# ---------- SAVE MESSAGE ----------
def save_message(conversation_id, role, content):
    conn = get_db()
    c = conn.cursor()

    # Save message
    c.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
        (conversation_id, role, content)
    )

    # Auto-generate title from FIRST user message
    if role == "user":
        c.execute(
            "SELECT COUNT(*) FROM messages WHERE conversation_id=? AND role='user'",
            (conversation_id,)
        )
        count = c.fetchone()[0]

        if count == 1:
            title = content.strip()[:40]
            c.execute(
                "UPDATE conversations SET title=? WHERE id=?",
                (title, conversation_id)
            )

    conn.commit()
    conn.close()


# ---------- LOAD MESSAGES ----------
def load_conversation(conversation_id):
    conn = get_db()
    c = conn.cursor()

    c.execute(
        "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id ASC",
        (conversation_id,)
    )

    messages = [dict(row) for row in c.fetchall()]
    conn.close()
    return messages


# ---------- LIST ALL CONVERSATIONS ----------
def list_conversations():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT c.id, c.title
        FROM conversations c
        WHERE EXISTS (
            SELECT 1 FROM messages m
            WHERE m.conversation_id = c.id
            AND m.role = 'user'
        )
        ORDER BY c.created_at DESC
    """)

    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ---------- DELETE CONVERSATION (OPTIONAL) ----------
def delete_conversation(conversation_id):
    conn = get_db()
    c = conn.cursor()

    c.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
    c.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))

    conn.commit()
    conn.close()