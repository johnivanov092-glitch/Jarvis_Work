from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/jarvis/task", tags=["jarvis-task-runner"])


class TaskRunPayload(BaseModel):
    goal: str = Field(min_length=1)
    mode: str = Field(default="code")
    current_path: Optional[str] = None
    staged_paths: List[str] = []


def build_plan(goal: str, current_path: str | None, staged_paths: List[str]) -> List[dict]:
    items: List[dict] = []

    if current_path:
        items.append({
            "action": "modify",
            "path": current_path,
            "reason": "Текущий файл выбран как главный кандидат на изменение.",
        })

    for path in staged_paths[:10]:
        if path and path != current_path:
            items.append({
                "action": "modify",
                "path": path,
                "reason": "Файл уже staged и включён в текущую задачу.",
            })

    goal_l = goal.lower()

    if any(word in goal_l for word in ["create", "создай", "добав", "новый файл", "component", "компонент"]):
        if not any(item["path"] == "frontend/src/components/NewTaskPanel.jsx" for item in items):
            items.append({
                "action": "create",
                "path": "frontend/src/components/NewTaskPanel.jsx",
                "reason": "По формулировке задачи вероятно нужен новый UI-компонент.",
            })

    if any(word in goal_l for word in ["api", "route", "router", "роут", "эндпоинт", "backend"]):
        if not any(item["path"] == "backend/app/api/routes/new_task_route.py" for item in items):
            items.append({
                "action": "create",
                "path": "backend/app/api/routes/new_task_route.py",
                "reason": "Задача выглядит как backend/API-изменение.",
            })

    if not items:
        items.append({
            "action": "inspect",
            "path": current_path or "project",
            "reason": "Сначала нужно уточнить область проекта и выбрать файлы.",
        })

    return items


@router.post("/run")
def run_task(payload: TaskRunPayload):
    plan_items = build_plan(payload.goal, payload.current_path, payload.staged_paths)
    started = datetime.utcnow().isoformat()

    logs = [
        "Task Runner started.",
        f"Mode: {payload.mode}",
        f"Goal: {payload.goal}",
        f"Plan built with {len(plan_items)} item(s).",
        "Preview stage prepared.",
        "Apply stage is ready for user confirmation.",
        "Verify stage is ready after patch apply.",
    ]

    preview_targets = [item["path"] for item in plan_items if item["action"] in {"modify", "create"}]

    return {
        "status": "ok",
        "mode": payload.mode,
        "goal": payload.goal,
        "started_at": started,
        "plan": plan_items,
        "preview_targets": preview_targets,
        "logs": logs,
        "next_steps": [
            "Проверь plan.",
            "Открой нужные файлы и подготовь preview patch.",
            "Сделай apply для выбранных файлов.",
            "Запусти verify.",
        ],
    }
