"""
autopipeline_service.py вЂ” Autopipelines (cron-Р·Р°РґР°С‡Рё) Elira AI.

Р›С‘РіРєРёР№ РїР»Р°РЅРёСЂРѕРІС‰РёРє РЅР° threading.Timer вЂ” Р±РµР· РІРЅРµС€РЅРёС… Р·Р°РІРёСЃРёРјРѕСЃС‚РµР№.
Р—Р°РґР°С‡Рё С…СЂР°РЅСЏС‚СЃСЏ РІ SQLite, РІС‹РїРѕР»РЅСЏСЋС‚СЃСЏ РІ С„РѕРЅРµ.

РўРёРїС‹ Р·Р°РґР°С‡:
  - prompt: РѕС‚РїСЂР°РІРёС‚СЊ РїСЂРѕРјРїС‚ РІ LLM Рё СЃРѕС…СЂР°РЅРёС‚СЊ СЂРµР·СѓР»СЊС‚Р°С‚
  - web_search: РІС‹РїРѕР»РЅРёС‚СЊ РІРµР±-РїРѕРёСЃРє РїРѕ Р·Р°РїСЂРѕСЃСѓ
  - plugin: Р·Р°РїСѓСЃС‚РёС‚СЊ РїР»Р°РіРёРЅ
  - workflow: Р·Р°РїСѓСЃС‚РёС‚СЊ workflow Engine
  - http: РІС‹Р·РІР°С‚СЊ URL (webhook/API)
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any

from app.core.config import DATA_DIR

logger = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "autopipelines.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_scheduler_thread: threading.Timer | None = None
_running = False
_TICK_INTERVAL = 30  # РїСЂРѕРІРµСЂРєР° РєР°Р¶РґС‹Рµ 30 СЃРµРє


# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
# DATABASE
# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ

def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _connect()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS pipelines (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                task_type TEXT NOT NULL DEFAULT 'prompt',
                task_data TEXT NOT NULL DEFAULT '{}',
                interval_minutes INTEGER NOT NULL DEFAULT 60,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_run TEXT,
                next_run TEXT,
                run_count INTEGER DEFAULT 0,
                last_result TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pipeline_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pipeline_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                ok INTEGER DEFAULT 0,
                result TEXT,
                error TEXT
            );
        """)
        conn.commit()
    finally:
        conn.close()


_init_db()


# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
# CRUD
# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ

def create_pipeline(
    name: str,
    task_type: str = "prompt",
    task_data: dict = None,
    interval_minutes: int = 60,
    enabled: bool = True,
) -> dict:
    """РЎРѕР·РґР°С‘С‚ РЅРѕРІС‹Р№ pipeline."""
    pid = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat()
    next_run = (datetime.utcnow() + timedelta(minutes=interval_minutes)).isoformat()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO pipelines (id, name, task_type, task_data, interval_minutes, enabled, next_run, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (pid, name, task_type, json.dumps(task_data or {}), interval_minutes, int(enabled), next_run, now),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "id": pid, "name": name, "next_run": next_run}


def list_pipelines() -> dict:
    """РЎРїРёСЃРѕРє РІСЃРµС… pipelines."""
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM pipelines ORDER BY created_at DESC").fetchall()
        items = []
        for r in rows:
            d = dict(r)
            try:
                d["task_data"] = json.loads(d.get("task_data") or "{}")
            except Exception:
                d["task_data"] = {}
            d["enabled"] = bool(d.get("enabled"))
            items.append(d)
        return {"ok": True, "pipelines": items, "count": len(items)}
    finally:
        conn.close()


def get_pipeline(pid: str) -> dict:
    """РџРѕР»СѓС‡РёС‚СЊ pipeline РїРѕ id."""
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM pipelines WHERE id = ?", (pid,)).fetchone()
        if not row:
            return {"ok": False, "error": "Pipeline РЅРµ РЅР°Р№РґРµРЅ"}
        d = dict(row)
        try:
            d["task_data"] = json.loads(d.get("task_data") or "{}")
        except Exception:
            d["task_data"] = {}
        d["enabled"] = bool(d.get("enabled"))
        return {"ok": True, **d}
    finally:
        conn.close()


def update_pipeline(pid: str, **kwargs) -> dict:
    """РћР±РЅРѕРІР»СЏРµС‚ РїРѕР»СЏ pipeline."""
    allowed = {"name", "task_type", "task_data", "interval_minutes", "enabled"}
    updates = []
    values = []
    for k, v in kwargs.items():
        if k not in allowed:
            continue
        if k == "task_data":
            v = json.dumps(v) if isinstance(v, dict) else v
        if k == "enabled":
            v = int(v)
        updates.append(f"{k} = ?")
        values.append(v)

    if not updates:
        return {"ok": False, "error": "РќРµС‡РµРіРѕ РѕР±РЅРѕРІР»СЏС‚СЊ"}

    conn = _connect()
    try:
        values.append(pid)
        conn.execute(f"UPDATE pipelines SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
        return {"ok": True, "id": pid, "updated": list(kwargs.keys())}
    finally:
        conn.close()


def delete_pipeline(pid: str) -> dict:
    """РЈРґР°Р»СЏРµС‚ pipeline Рё РµРіРѕ Р»РѕРіРё."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM pipelines WHERE id = ?", (pid,))
        conn.execute("DELETE FROM pipeline_logs WHERE pipeline_id = ?", (pid,))
        conn.commit()
        return {"ok": True, "deleted": pid}
    finally:
        conn.close()


def get_pipeline_logs(pid: str, limit: int = 20) -> dict:
    """РСЃС‚РѕСЂРёСЏ РІС‹РїРѕР»РЅРµРЅРёСЏ pipeline."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM pipeline_logs WHERE pipeline_id = ? ORDER BY started_at DESC LIMIT ?",
            (pid, limit),
        ).fetchall()
        return {"ok": True, "logs": [dict(r) for r in rows], "count": len(rows)}
    finally:
        conn.close()


# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
# Р’Р«РџРћР›РќР•РќРР• Р—РђР”РђР§
# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ

def _execute_task(task_type: str, task_data: dict) -> dict:
    """Р’С‹РїРѕР»РЅСЏРµС‚ Р·Р°РґР°С‡Сѓ РїРѕ С‚РёРїСѓ."""
    try:
        if task_type == "prompt":
            prompt = task_data.get("prompt", "")
            model = task_data.get("model", "")
            if not prompt:
                return {"ok": False, "error": "РќРµС‚ РїСЂРѕРјРїС‚Р°"}
            from app.services.agents_service import run_agent
            result = run_agent(
                model_name=model or "gemma3:4b",
                profile_name=task_data.get("profile", "РЈРЅРёРІРµСЂСЃР°Р»СЊРЅС‹Р№"),
                user_input=prompt,
                use_memory=False,
                use_web_search=task_data.get("web_search", False),
            )
            answer = result.get("answer", "")[:2000]
            return {"ok": True, "answer": answer, "length": len(answer)}

        elif task_type == "web_search":
            query = task_data.get("query", "")
            if not query:
                return {"ok": False, "error": "РќРµС‚ Р·Р°РїСЂРѕСЃР°"}
            from app.services.web_multisearch_service import multi_search
            return multi_search(query, max_results=task_data.get("max_results", 5))

        elif task_type == "plugin":
            name = task_data.get("plugin_name", "")
            if not name:
                return {"ok": False, "error": "РќРµС‚ РёРјРµРЅРё РїР»Р°РіРёРЅР°"}
            from app.services.plugin_system import run_plugin
            return run_plugin(name, task_data.get("args", {}))

        elif task_type == "workflow":
            workflow_id = str(task_data.get("workflow_id", "")).strip()
            if not workflow_id:
                return {"ok": False, "error": "РќРµС‚ workflow_id"}
            from app.services.workflow_engine import start_workflow_run

            run = start_workflow_run(
                workflow_id=workflow_id,
                workflow_input=task_data.get("input", {}) if isinstance(task_data.get("input", {}), dict) else {},
                context=task_data.get("context", {}) if isinstance(task_data.get("context", {}), dict) else {},
                trigger_source="autopipeline",
            )
            return {
                "ok": run.get("status") == "completed",
                "run_id": run.get("run_id", ""),
                "workflow_id": workflow_id,
                "status": run.get("status", ""),
                "error": run.get("error", {}).get("message", "") if isinstance(run.get("error"), dict) else "",
            }

        elif task_type == "http":
            import requests
            url = task_data.get("url", "")
            method = task_data.get("method", "GET").upper()
            if not url:
                return {"ok": False, "error": "РќРµС‚ URL"}
            resp = requests.request(method, url, timeout=30, json=task_data.get("body"))
            return {"ok": True, "status": resp.status_code, "body": resp.text[:2000]}

        else:
            return {"ok": False, "error": f"РќРµРёР·РІРµСЃС‚РЅС‹Р№ С‚РёРї: {task_type}"}

    except Exception as e:
        return {"ok": False, "error": str(e)}


def run_pipeline_now(pid: str) -> dict:
    """Р—Р°РїСѓСЃРєР°РµС‚ pipeline РІСЂСѓС‡РЅСѓСЋ РїСЂСЏРјРѕ СЃРµР№С‡Р°СЃ."""
    p = get_pipeline(pid)
    if not p.get("ok"):
        return p

    started = datetime.utcnow().isoformat()
    result = _execute_task(p["task_type"], p.get("task_data", {}))
    finished = datetime.utcnow().isoformat()

    # РЎРѕС…СЂР°РЅСЏРµРј Р»РѕРі
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO pipeline_logs (pipeline_id, started_at, finished_at, ok, result, error) VALUES (?,?,?,?,?,?)",
            (pid, started, finished, int(result.get("ok", False)),
             json.dumps(result, ensure_ascii=False)[:5000], result.get("error", "")),
        )
        # РћР±РЅРѕРІР»СЏРµРј pipeline
        next_run = (datetime.utcnow() + timedelta(minutes=p.get("interval_minutes", 60))).isoformat()
        conn.execute(
            "UPDATE pipelines SET last_run = ?, next_run = ?, run_count = run_count + 1, last_result = ?, last_error = ? WHERE id = ?",
            (finished, next_run, json.dumps(result, ensure_ascii=False)[:2000], result.get("error", ""), pid),
        )
        conn.commit()
    finally:
        conn.close()

    return {"ok": True, "pipeline_id": pid, "result": result}


# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
# РџР›РђРќРР РћР’Р©РРљ (С„РѕРЅРѕРІС‹Р№ С‚РёРє)
# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ

def _tick():
    """РџСЂРѕРІРµСЂСЏРµС‚ Рё Р·Р°РїСѓСЃРєР°РµС‚ РїСЂРѕСЃСЂРѕС‡РµРЅРЅС‹Рµ pipelines."""
    global _scheduler_thread
    if not _running:
        return

    now = datetime.utcnow().isoformat()
    conn = _connect()
    try:
        due = conn.execute(
            "SELECT id FROM pipelines WHERE enabled = 1 AND next_run <= ?", (now,)
        ).fetchall()
    finally:
        conn.close()

    for row in due:
        try:
            run_pipeline_now(row["id"])
            logger.info(f"Autopipeline {row['id']} executed")
        except Exception as e:
            logger.error(f"Autopipeline {row['id']} error: {e}")

    # РџРµСЂРµРїР»Р°РЅРёСЂСѓРµРј СЃР»РµРґСѓСЋС‰РёР№ С‚РёРє
    _scheduler_thread = threading.Timer(_TICK_INTERVAL, _tick)
    _scheduler_thread.daemon = True
    _scheduler_thread.start()


def start_scheduler():
    """Р—Р°РїСѓСЃРєР°РµС‚ С„РѕРЅРѕРІС‹Р№ РїР»Р°РЅРёСЂРѕРІС‰РёРє."""
    global _running, _scheduler_thread
    if _running:
        return {"ok": True, "status": "already_running"}
    _running = True
    _scheduler_thread = threading.Timer(_TICK_INTERVAL, _tick)
    _scheduler_thread.daemon = True
    _scheduler_thread.start()
    logger.info("Autopipeline scheduler started")
    return {"ok": True, "status": "started", "interval": _TICK_INTERVAL}


def stop_scheduler():
    """РћСЃС‚Р°РЅР°РІР»РёРІР°РµС‚ РїР»Р°РЅРёСЂРѕРІС‰РёРє."""
    global _running, _scheduler_thread
    _running = False
    if _scheduler_thread:
        _scheduler_thread.cancel()
        _scheduler_thread = None
    logger.info("Autopipeline scheduler stopped")
    return {"ok": True, "status": "stopped"}


def scheduler_status() -> dict:
    """РЎС‚Р°С‚СѓСЃ РїР»Р°РЅРёСЂРѕРІС‰РёРєР°."""
    return {"ok": True, "running": _running, "tick_interval": _TICK_INTERVAL}


# РђРІС‚РѕР·Р°РїСѓСЃРє РїСЂРё РёРјРїРѕСЂС‚Рµ
start_scheduler()
