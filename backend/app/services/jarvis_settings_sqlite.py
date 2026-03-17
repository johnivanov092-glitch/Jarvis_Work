import sqlite3
from pathlib import Path

DB_PATH = Path("data/jarvis_state.db")

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_settings():
    conn = _connect()
    row = conn.execute('SELECT ollama_context, default_model, agent_profile FROM settings WHERE id = 1').fetchone()
    conn.close()
    return dict(row) if row else {"ollama_context": 8192, "default_model": "qwen3:8b", "agent_profile": "Сбалансированный"}

def save_settings(ollama_context, default_model, agent_profile):
    conn = _connect()
    conn.execute('UPDATE settings SET ollama_context = ?, default_model = ?, agent_profile = ? WHERE id = 1', (int(ollama_context), default_model, agent_profile))
    conn.commit()
    row = conn.execute('SELECT ollama_context, default_model, agent_profile FROM settings WHERE id = 1').fetchone()
    conn.close()
    return dict(row)
