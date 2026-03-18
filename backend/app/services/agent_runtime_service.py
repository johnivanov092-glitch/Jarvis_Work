from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from app.services.agent_task_planner import build_simple_plan


def _event(event_type: str, detail: str, status: str = "ok") -> Dict[str, Any]:
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "type": event_type,
        "detail": detail,
        "status": status,
    }


def run_isolated_agent(user_input: str) -> Dict[str, Any]:
    plan = build_simple_plan(user_input)
    events: List[Dict[str, Any]] = []

    if not plan["goal"]:
        events.append(_event("validation", "Пустой запрос", "error"))
        return {
            "ok": False,
            "mode": "chat",
            "plan": plan,
            "events": events,
            "answer": "",
        }

    events.append(_event("planner", f"Режим: {plan['mode']}"))
    for step in plan["steps"]:
        events.append(_event(step["type"], step["title"]))

    answer = (
        f"План построен. Режим: {plan['mode']}. "
        f"Шагов: {len(plan['steps'])}. "
        f"Цель: {plan['goal']}"
    )

    events.append(_event("finish", "Выполнение завершено"))

    return {
        "ok": True,
        "mode": plan["mode"],
        "plan": plan,
        "events": events,
        "answer": answer,
    }
