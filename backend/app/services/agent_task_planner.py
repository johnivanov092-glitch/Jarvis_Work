from __future__ import annotations

from typing import Any, Dict, List


def build_simple_plan(user_input: str) -> Dict[str, Any]:
    text = (user_input or "").strip()

    if not text:
        return {
            "goal": "",
            "mode": "chat",
            "steps": [],
        }

    lowered = text.lower()

    if any(word in lowered for word in ["файл", "read", "open", "код", "code"]):
        mode = "code"
        steps: List[Dict[str, Any]] = [
            {"id": "step-1", "type": "analyze", "title": "Анализ запроса"},
            {"id": "step-2", "type": "tool", "title": "Подготовка tool execution"},
            {"id": "step-3", "type": "answer", "title": "Формирование результата"},
        ]
    elif any(word in lowered for word in ["исслед", "поиск", "research", "web"]):
        mode = "research"
        steps = [
            {"id": "step-1", "type": "analyze", "title": "Анализ темы"},
            {"id": "step-2", "type": "research", "title": "Сбор данных"},
            {"id": "step-3", "type": "answer", "title": "Финальный вывод"},
        ]
    else:
        mode = "chat"
        steps = [
            {"id": "step-1", "type": "analyze", "title": "Анализ сообщения"},
            {"id": "step-2", "type": "answer", "title": "Формирование ответа"},
        ]

    return {
        "goal": text,
        "mode": mode,
        "steps": steps,
    }
