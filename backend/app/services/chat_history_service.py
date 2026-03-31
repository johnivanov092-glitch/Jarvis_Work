import sqlite3
import json
import uuid
from datetime import datetime
from app.core.config import DATA_DIR

DB_PATH = DATA_DIR / "chats.db"

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)")
    conn.commit()
    conn.close()

def save_message(session_id: str, role: str, content: str):
    if not session_id or not content:
        return
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    msg_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO messages (id, session_id, role, content, created_at) VALUES (?,?,?,?,?)",
        (msg_id, session_id, role, content, now)
    )
    conn.commit()
    conn.close()

def get_history(session_id: str, limit: int = 20):
    if not session_id:
        return []
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
        (session_id, limit)
    ).fetchall()
    history = []
    for r in rows:
        role = r["role"]
        # ╨а╨╛╨бтАВ╨а╤Ш╨а┬░╨а┬╗╨а╤С╨а┬╖╨а┬░╨бтАЖ╨а╤С╨б╨П ╨б╨В╨а╤Х╨а┬╗╨а┬╡╨а╨Е
        if role in ("human", "user"): role = "user"
        if role in ("ai", "bot", "assistant"): role = "assistant"
        history.append({"role": role, "content": r["content"]})
    conn.close()
    return history