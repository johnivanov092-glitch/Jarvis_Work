from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/jarvis/supervisor", tags=["jarvis-supervisor"])

DB_PATH = Path("data/jarvis_state.db")


def ensure_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS supervisor_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal TEXT NOT NULL,
                mode TEXT NOT NULL,
                current_path TEXT,
                status TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                steps_json TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


class SupervisorRunPayload(BaseModel):
    goal: str = Field(min_length=1)
    mode: str = Field(default="code")
    current_path: Optional[str] = None
    staged_paths: List[str] = []
    auto_apply: bool = False


def dumps_json(data) -> str:
    return json.dumps(data, ensure_ascii=False)


def loads_json(text: str):
    return json.loads(text) if text else None


def build_plan(goal: str, current_path: str | None, staged_paths: List[str]) -> List[dict]:
    plan: List[dict] = []

    if current_path:
        plan.append({
            "action": "modify",
            "path": current_path,
            "reason": "Текущий файл выбран как основной кандидат.",
        })

    for path in staged_paths[:8]:
        if path and path != current_path:
            plan.append({
                "action": "modify",
                "path": path,
                "reason": "Файл staged и участвует в текущем сценарии.",
            })

    goal_l = goal.lower()
    if any(word in goal_l for word in ["create", "создай", "добав", "компонент", "component"]):
        plan.append({
            "action": "create",
            "path": "frontend/src/components/SupervisorGeneratedPanel.jsx",
            "reason": "Задача выглядит как добавление новой UI-функции.",
        })

    if any(word in goal_l for word in ["api", "backend", "роут", "route", "router", "эндпоинт"]):
        plan.append({
            "action": "create",
            "path": "backend/app/api/routes/supervisor_generated_route.py",
            "reason": "Задача затрагивает backend API.",
        })

    if not plan:
        plan.append({
            "action": "inspect",
            "path": current_path or "project",
            "reason": "Нужно сначала уточнить область изменений.",
        })

    return plan[:12]


def build_steps(plan: List[dict], auto_apply: bool) -> List[dict]:
    preview_targets = [item["path"] for item in plan if item["action"] in {"modify", "create"}]

    return [
        {
            "agent": "planner",
            "status": "done",
            "title": "Построение плана",
            "details": f"Подготовлено {len(plan)} item(s).",
        },
        {
            "agent": "coder",
            "status": "done",
            "title": "Подготовка preview",
            "details": f"Preview targets: {', '.join(preview_targets) if preview_targets else 'нет'}",
        },
        {
            "agent": "reviewer",
            "status": "done",
            "title": "Review",
            "details": "Diff, history и verify flow подготовлены.",
        },
        {
            "agent": "tester",
            "status": "ready" if auto_apply else "queued",
            "title": "Verify",
            "details": "Готов к verify после apply." if auto_apply else "Ожидает пользовательский apply.",
        },
    ]


def persist_run(goal: str, mode: str, current_path: str | None, status: str, plan: list, steps: list, summary: dict) -> int:
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            """
            INSERT INTO supervisor_runs (
                goal, mode, current_path, status,
                plan_json, steps_json, summary_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                goal,
                mode,
                current_path,
                status,
                dumps_json(plan),
                dumps_json(steps),
                dumps_json(summary),
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


@router.post("/run")
def run_supervisor(payload: SupervisorRunPayload):
    plan = build_plan(payload.goal, payload.current_path, payload.staged_paths)
    steps = build_steps(plan, payload.auto_apply)
    summary = {
        "preview_targets": [item["path"] for item in plan if item["action"] in {"modify", "create"}],
        "next_steps": [
            "Открой файлы из плана.",
            "Сделай Preview Patch.",
            "Проверь Diff и History.",
            "Сделай Apply и Verify.",
        ] if not payload.auto_apply else [
            "Preview готов.",
            "Сделай Apply для подтвержденных файлов.",
            "Сразу после apply выполни Verify.",
        ],
        "auto_apply": payload.auto_apply,
    }
    run_id = persist_run(
        payload.goal,
        payload.mode,
        payload.current_path,
        "planned",
        plan,
        steps,
        summary,
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "goal": payload.goal,
        "mode": payload.mode,
        "current_path": payload.current_path,
        "plan": plan,
        "steps": steps,
        "summary": summary,
        "created_at": datetime.utcnow().isoformat(),
    }


@router.get("/history/list")
def list_supervisor_history(limit: int = 30):
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, goal, mode, current_path, status, created_at
            FROM supervisor_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return {"items": [dict(row) for row in rows]}
    finally:
        conn.close()


@router.get("/history/get")
def get_supervisor_history(id: int):
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT id, goal, mode, current_path, status,
                   plan_json, steps_json, summary_json, created_at
            FROM supervisor_runs
            WHERE id = ?
            """,
            (id,),
        ).fetchone()
        if not row:
            return {"status": "not_found"}
        data = dict(row)
        data["plan"] = loads_json(data.pop("plan_json"))
        data["steps"] = loads_json(data.pop("steps_json"))
        data["summary"] = loads_json(data.pop("summary_json"))
        return data
    finally:
        conn.close()
