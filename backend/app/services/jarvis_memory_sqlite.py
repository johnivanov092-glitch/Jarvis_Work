import sqlite3
from pathlib import Path

DB_PATH = Path("data/jarvis_state.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = _connect()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    cur.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    cur.execute("CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK (id = 1), ollama_context INTEGER NOT NULL DEFAULT 8192, default_model TEXT NOT NULL DEFAULT 'qwen3:8b', agent_profile TEXT NOT NULL DEFAULT 'Сбалансированный')")
    cur.execute("INSERT OR IGNORE INTO settings(id, ollama_context, default_model, agent_profile) VALUES(1, 8192, 'qwen3:8b', 'Сбалансированный')")
    conn.commit()
    conn.close()

def list_chats():
    conn = _connect()
    rows = conn.execute("SELECT id, title, created_at, updated_at FROM chats ORDER BY updated_at DESC, id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_chat(title='Новый чат'):
    conn = _connect()
    cur = conn.cursor()
    cur.execute('INSERT INTO chats(title) VALUES (?)', (title or 'Новый чат',))
    chat_id = cur.lastrowid
    row = conn.execute('SELECT * FROM chats WHERE id = ?', (chat_id,)).fetchone()
    conn.commit()
    conn.close()
    return dict(row)

def rename_chat(chat_id, title):
    conn = _connect()
    conn.execute('UPDATE chats SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (title or 'Новый чат', chat_id))
    row = conn.execute('SELECT * FROM chats WHERE id = ?', (chat_id,)).fetchone()
    conn.commit()
    conn.close()
    return dict(row) if row else None

def delete_chat(chat_id):
    conn = _connect()
    conn.execute('DELETE FROM messages WHERE chat_id = ?', (chat_id,))
    conn.execute('DELETE FROM chats WHERE id = ?', (chat_id,))
    conn.commit()
    conn.close()

def get_messages(chat_id):
    conn = _connect()
    rows = conn.execute('SELECT id, chat_id, role, content, created_at FROM messages WHERE chat_id = ? ORDER BY id ASC', (chat_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_message(chat_id, role, content):
    conn = _connect()
    cur = conn.cursor()
    cur.execute('INSERT INTO messages(chat_id, role, content) VALUES (?, ?, ?)', (chat_id, role, content))
    message_id = cur.lastrowid
    conn.execute('UPDATE chats SET updated_at = CURRENT_TIMESTAMP WHERE id = ?', (chat_id,))
    row = conn.execute('SELECT * FROM messages WHERE id = ?', (message_id,)).fetchone()
    conn.commit()
    conn.close()
    return dict(row)
