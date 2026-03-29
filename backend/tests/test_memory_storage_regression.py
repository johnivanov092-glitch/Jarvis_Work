from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"


def _create_legacy_smart_memory(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'fact',
                source TEXT NOT NULL DEFAULT 'auto',
                importance INTEGER NOT NULL DEFAULT 5,
                access_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO memories (text, category, source, importance)
            VALUES ('legacy alpha fact', 'fact', 'legacy', 7)
            """
        )
        conn.commit()
    finally:
        conn.close()


def _create_legacy_rag(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE rag_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                category TEXT DEFAULT 'fact',
                embedding TEXT DEFAULT '',
                importance INTEGER DEFAULT 5,
                access_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO rag_items (text, category, embedding, importance)
            VALUES ('legacy rag item', 'fact', '[0.1, 0.2, 0.3]', 6)
            """
        )
        conn.commit()
    finally:
        conn.close()


def _create_legacy_elira_state(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                ollama_context INTEGER NOT NULL DEFAULT 8192,
                default_model TEXT NOT NULL DEFAULT 'gemma3:4b',
                agent_profile TEXT NOT NULL DEFAULT 'default'
            )
            """
        )
        conn.execute("INSERT INTO chats (title) VALUES ('Legacy chat')")
        conn.execute(
            "INSERT INTO messages (chat_id, role, content) VALUES (1, 'user', 'legacy message')"
        )
        conn.execute(
            """
            INSERT INTO settings (id, ollama_context, default_model, agent_profile)
            VALUES (1, 8192, 'gemma3:4b', 'default')
            """
        )
        conn.commit()
    finally:
        conn.close()


class MemoryStorageRegressionTest(unittest.TestCase):
    def test_legacy_data_adoption_and_profile_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as data_dir, tempfile.TemporaryDirectory() as legacy_dir:
            data_path = Path(data_dir)
            legacy_path = Path(legacy_dir)

            _create_legacy_smart_memory(legacy_path / "smart_memory.db")
            _create_legacy_rag(legacy_path / "rag_memory.db")
            _create_legacy_elira_state(legacy_path / "elira_state.db")
            (legacy_path / "run_history.json").write_text(
                json.dumps(
                    [
                        {
                            "run_id": "legacy-run",
                            "user_input": "legacy question",
                            "started_at": "2026-03-29T00:00:00",
                            "finished_at": "2026-03-29T00:00:05",
                            "ok": True,
                            "route": "chat",
                            "model": "gemma3:4b",
                            "answer_len": 42,
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            script = textwrap.dedent(
                f"""
                import json
                import sys
                sys.path.insert(0, r"{BACKEND_ROOT}")

                from fastapi.testclient import TestClient
                from app.main import app
                from app.services.elira_memory_sqlite import list_chats
                from app.services.rag_memory_service import rag_stats
                from app.services.run_history_service import RunHistoryService
                from app.services.smart_memory import get_stats

                client = TestClient(app)
                client.post("/api/memory/add", json={{"profile": "second", "text": "profile beta fact", "source": "manual"}})

                payload = {{
                    "default_items": client.get("/api/memory/items/default").json()["count"],
                    "second_items": client.get("/api/memory/items/second").json()["count"],
                    "profiles": client.get("/api/memory/profiles").json()["profiles"],
                    "memory_stats": get_stats(),
                    "rag_total": rag_stats()["total"],
                    "chat_count": len(list_chats()),
                    "run_count": len(RunHistoryService().list_runs(10)),
                    "dashboard_total_runs": client.get("/api/dashboard/stats").json()["total_runs"],
                }}
                print(json.dumps(payload, ensure_ascii=False))
                """
            )

            env = os.environ.copy()
            env["ELIRA_DATA_DIR"] = str(data_path)
            env["ELIRA_LEGACY_DATA_DIR"] = str(legacy_path)

            proc = subprocess.run(
                [sys.executable, "-c", script],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout.strip())

            self.assertEqual(payload["default_items"], 1)
            self.assertEqual(payload["second_items"], 1)
            self.assertEqual(payload["rag_total"], 1)
            self.assertEqual(payload["chat_count"], 1)
            self.assertEqual(payload["run_count"], 1)
            self.assertEqual(payload["dashboard_total_runs"], 1)
            self.assertEqual(payload["memory_stats"]["by_profile"]["default"], 1)
            self.assertEqual(payload["memory_stats"]["by_profile"]["second"], 1)
            self.assertEqual(
                sorted(profile["name"] for profile in payload["profiles"]),
                ["default", "second"],
            )


if __name__ == "__main__":
    unittest.main()
