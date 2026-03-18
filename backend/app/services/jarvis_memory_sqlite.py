import sqlite3
from pathlib import Path

DB_PATH = Path("data/jarvis_state.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn, table: str, column: str, ddl: str):
    columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db():
    conn = _connect()
    cur = conn.cursor()

    cur.execute(
        "CREATE TABLE IF NOT EXISTS chats ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "updated_at TEXT DEFAULT CURRENT_TIMESTAMP"
        ")"
    )
    _ensure_column(conn, "chats", "pinned", "pinned INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "chats", "memory_saved", "memory_saved INTEGER NOT NULL DEFAULT 0")

    cur.execute(
        "CREATE TABLE IF NOT EXISTS messages ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "chat_id INTEGER NOT NULL, "
        "role TEXT NOT NULL, "
        "content TEXT NOT NULL, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP"
        ")"
    )

    cur.execute(
        "CREATE TABLE IF NOT EXISTS settings ("
        "id INTEGER PRIMARY KEY CHECK (id = 1), "
        "ollama_context INTEGER NOT NULL DEFAULT 8192, "
        "default_model TEXT NOT NULL DEFAULT 'qwen3:8b', "
        "agent_profile TEXT NOT NULL DEFAULT 'Сбалансированный'"
        ")"
    )
    cur.execute(
        "INSERT OR IGNORE INTO settings(id, ollama_context, default_model, agent_profile) "
        "VALUES(1, 8192, 'qwen3:8b', 'Сбалансированный')"
    )

    conn.commit()
    conn.close()


def _chat_row(conn, chat_id: int):
    return conn.execute(
        "SELECT id, title, pinned, memory_saved, created_at, updated_at "
        "FROM chats WHERE id = ?",
        (chat_id,),
    ).fetchone()


def list_chats():
    conn = _connect()
    rows = conn.execute(
        "SELECT id, title, pinned, memory_saved, created_at, updated_at "
        "FROM chats ORDER BY pinned DESC, updated_at DESC, id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_chat(title="Новый чат"):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO chats(title, pinned, memory_saved) VALUES (?, 0, 0)",
        (title or "Новый чат",),
    )
    chat_id = cur.lastrowid
    row = _chat_row(conn, chat_id)
    conn.commit()
    conn.close()
    return dict(row)


def update_chat(chat_id: int, title=None, pinned=None, memory_saved=None):
    conn = _connect()
    current = _chat_row(conn, chat_id)
    if not current:
        conn.close()
        return None

    next_title = current["title"] if title is None else (title or "Новый чат")
    next_pinned = current["pinned"] if pinned is None else int(bool(pinned))
    next_memory_saved = current["memory_saved"] if memory_saved is None else int(bool(memory_saved))

    conn.execute(
        "UPDATE chats "
        "SET title = ?, pinned = ?, memory_saved = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (next_title, next_pinned, next_memory_saved, chat_id),
    )
    row = _chat_row(conn, chat_id)
    conn.commit()
    conn.close()
    return dict(row) if row else None


def rename_chat(chat_id, title):
    return update_chat(chat_id, title=title)


def set_chat_pinned(chat_id, pinned):
    return update_chat(chat_id, pinned=pinned)


def set_chat_memory_saved(chat_id, memory_saved):
    return update_chat(chat_id, memory_saved=memory_saved)


def delete_chat(chat_id):
    conn = _connect()
    conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()


def get_messages(chat_id):
    conn = _connect()
    rows = conn.execute(
        "SELECT id, chat_id, role, content, created_at "
        "FROM messages WHERE chat_id = ? ORDER BY id ASC",
        (chat_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_message(chat_id, role, content):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages(chat_id, role, content) VALUES (?, ?, ?)",
        (chat_id, role, content),
    )
    message_id = cur.lastrowid
    conn.execute(
        "UPDATE chats SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (chat_id,),
    )
    row = conn.execute(
        "SELECT * FROM messages WHERE id = ?",
        (message_id,),
    ).fetchone()
    conn.commit()
    conn.close()
    return dict(row)
