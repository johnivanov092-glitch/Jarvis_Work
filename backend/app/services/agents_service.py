"""
agents_service.py v5

Фиксы:
  • Очистка поискового запроса от мусора ("дай мне", "на сегодня" и т.д.)
  • Поиск только ddgs
  • Естественный промпт без технических маршрутов
  • Фазы прогресса
  • Reflection только для code/project
"""
from __future__ import annotations
import re
from typing import Any, Generator

from app.services.chat_service import run_chat, run_chat_stream
from app.services.planner_v2_service import PlannerV2Service
from app.services.reflection_loop_service import run_reflection_loop
from app.services.run_history_service import RunHistoryService
from app.services.tool_service import run_tool

_HISTORY = RunHistoryService()
_REFLECTION_ROUTES = {"code", "project"}
_MAX_HISTORY_PAIRS = 10

# Слова-мусор, которые ухудшают поисковый запрос
_QUERY_NOISE = [
    r"^дай\s+мне\s+", r"^покажи\s+мне\s+", r"^найди\s+мне\s+",
    r"^скажи\s+мне\s+", r"^расскажи\s+мне\s+", r"^подскажи\s+мне\s+",
    r"^можешь\s+", r"^пожалуйста\s+", r"^please\s+",
    r"^give\s+me\s+", r"^show\s+me\s+", r"^find\s+me\s+",
    r"^tell\s+me\s+", r"^can\s+you\s+",
    r"\s+на\s+сегодня\s*$", r"\s+на\s+сегодняшний\s+день\s*$",
    r"\s+сейчас\s*$", r"\s+прямо\s+сейчас\s*$",
]


def _clean_search_query(query: str) -> str:
    """Очищает запрос от мусорных слов для лучших результатов поиска."""
    q = query.strip()
    for pattern in _QUERY_NOISE:
        q = re.sub(pattern, "", q, flags=re.IGNORECASE).strip()
    # Добавляем "2025" если запрос про текущие данные
    current_markers = ["курс", "цена", "стоимость", "погода", "новости", "счёт", "счет", "результат"]
    if any(m in q.lower() for m in current_markers) and "2025" not in q and "2024" not in q:
        q += " 2025"
    return q or query


def _short(v, limit=600):
    t = str(v or ""); return t if len(t) <= limit else t[:limit] + "..."

def _tl(timeline, step, title, status, detail):
    timeline.append({"step": step, "title": title, "status": status, "detail": detail})

def _trim_history(h, max_pairs=_MAX_HISTORY_PAIRS):
    if not h: return []
    limit = max_pairs * 2
    return list(h[-limit:]) if len(h) > limit else list(h)


def _build_prompt(user_input, context_bundle):
    """Естественный промпт без техно-жаргона."""
    parts = [user_input]
    if context_bundle.strip():
        parts.append(f"\n\nВот информация которая поможет тебе ответить:\n{context_bundle}")
    return "\n".join(parts)


def _do_web_search(query, timeline, tool_results):
    """Веб-поиск через ddgs с очисткой запроса."""
    search_query = _clean_search_query(query)

    try:
        DDGS = None
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            raw = list(ddgs.text(search_query, max_results=8))

        for r in raw:
            url = r.get("href") or r.get("url") or ""
            if not url:
                continue
            results.append({
                "title": r.get("title", ""),
                "url": url,
                "snippet": r.get("body", ""),
            })

        tool_results.append({"tool": "web_search", "result": {"query": search_query, "original": query, "count": len(results)}})
        _tl(timeline, "tool_web", f"Поиск: «{search_query}»", "done" if results else "warning", f"{len(results)} результатов")

        if results:
            lines = []
            for s in results[:6]:
                lines.append(f"Источник: {s['title']}\nURL: {s['url']}\nОписание: {s['snippet']}")
            return "Результаты из интернета:\n\n" + "\n\n".join(lines)
        return ""

    except Exception as e:
        _tl(timeline, "tool_web", "Поиск", "error", str(e))
        return ""


def _collect_context(*, profile_name, user_input, tools, tool_results, timeline):
    parts = []

    for tool_name in tools:
        try:
            if tool_name == "memory_search":
                result = run_tool("search_memory", {"profile": profile_name, "query": user_input, "limit": 5})
                tool_results.append({"tool": "search_memory", "result": result})
                items = result.get("items", [])
                _tl(timeline, "tool_memory", "Память", "done", f"{result.get('count', 0)}")
                if items:
                    parts.append("Из памяти:\n" + "\n".join(f"- {i.get('text','')}" for i in items))

            elif tool_name == "library_context":
                result = run_tool("build_library_context", {})
                tool_results.append({"tool": "library", "result": result})
                if result.get("context"):
                    parts.append("Из библиотеки:\n" + str(result["context"]))
                    _tl(timeline, "tool_library", "Библиотека", "done", "Загружено")

            elif tool_name == "web_search":
                web_ctx = _do_web_search(user_input, timeline, tool_results)
                if web_ctx:
                    parts.append(web_ctx)

            elif tool_name == "project_mode":
                tree = run_tool("list_project_tree", {"max_depth": 3, "max_items": 200})
                search = run_tool("search_project", {"query": user_input, "max_hits": 20})
                tool_results.append({"tool": "project", "result": {"tree": tree.get("count", 0), "hits": search.get("count", 0)}})
                _tl(timeline, "tool_project", "Проект", "done", f"Файлов: {tree.get('count',0)}")
                snippets = search.get("items") or search.get("results") or []
                if snippets:
                    rendered = []
                    for item in snippets[:10]:
                        if isinstance(item, dict):
                            rendered.append(f"- {item.get('path','')}: {item.get('snippet','') or item.get('preview','')}")
                        else:
                            rendered.append(f"- {item}")
                    parts.append("Из проекта:\n" + "\n".join(rendered))

            elif tool_name == "project_patch":
                _tl(timeline, "tool_patch", "Патчинг", "ready", "")

            elif tool_name == "python_executor":
                _tl(timeline, "tool_python", "Python", "ready", "")

        except Exception as exc:
            _tl(timeline, f"tool_{tool_name}", tool_name, "error", str(exc))

    return "\n\n".join(p for p in parts if p.strip())


def run_agent(*, model_name, profile_name, user_input, use_memory=True, use_library=True, history=None):
    history = _trim_history(history or [])
    timeline, tool_results = [], []
    planner = PlannerV2Service()
    run = _HISTORY.start_run(user_input)

    try:
        plan = planner.plan(user_input)
        _HISTORY.add_event(run["run_id"], "planner", plan)
        route = plan.get("route", "chat")

        selected = [t for t in plan.get("tools", [])
                     if not (t == "memory_search" and not use_memory)
                     and not (t == "library_context" and not use_library)]

        ctx = _collect_context(profile_name=profile_name, user_input=user_input, tools=selected, tool_results=tool_results, timeline=timeline)
        prompt = _build_prompt(user_input, ctx)

        draft = run_chat(model_name=model_name, profile_name=profile_name, user_input=prompt, history=history)
        if not draft.get("ok"):
            raise RuntimeError("; ".join(draft.get("warnings", [])) or "LLM failed")
        answer = draft.get("answer", "")

        if route in _REFLECTION_ROUTES and answer.strip():
            ref = run_reflection_loop(model_name=model_name, profile_name=profile_name, user_input=user_input, draft_text=answer, review_text="Улучши ответ: сделай конкретнее.", context=ctx)
            answer = ref.get("answer") or answer

        result = {"ok": True, "answer": answer, "timeline": timeline, "tool_results": tool_results, "meta": {"model_name": model_name, "profile_name": profile_name, "route": route, "tools": selected, "run_id": run["run_id"]}}
        _HISTORY.finish_run(run["run_id"], result)
        return result
    except Exception as exc:
        err = {"ok": False, "answer": "", "timeline": timeline + [{"step": "error", "title": "Ошибка", "status": "error", "detail": str(exc)}], "tool_results": tool_results, "meta": {"error": str(exc), "run_id": run["run_id"]}}
        _HISTORY.finish_run(run["run_id"], err)
        return err


def run_agent_stream(*, model_name, profile_name, user_input, use_memory=True, use_library=True, history=None):
    history = _trim_history(history or [])
    timeline, tool_results = [], []
    planner = PlannerV2Service()
    run = _HISTORY.start_run(user_input)

    try:
        plan = planner.plan(user_input)
        _HISTORY.add_event(run["run_id"], "planner", plan)
        route = plan.get("route", "chat")

        selected = [t for t in plan.get("tools", [])
                     if not (t == "memory_search" and not use_memory)
                     and not (t == "library_context" and not use_library)]

        has_web = "web_search" in selected
        if has_web:
            yield {"token": "", "done": False, "phase": "searching", "message": "Ищу в интернете..."}
        elif selected:
            yield {"token": "", "done": False, "phase": "tools", "message": "Подготовка..."}

        ctx = _collect_context(profile_name=profile_name, user_input=user_input, tools=selected, tool_results=tool_results, timeline=timeline)

        yield {"token": "", "done": False, "phase": "thinking", "message": "Генерирую ответ..."}

        prompt = _build_prompt(user_input, ctx)

        full_text = ""
        for token in run_chat_stream(model_name=model_name, profile_name=profile_name, user_input=prompt, history=history):
            full_text += token
            yield {"token": token, "done": False}

        if route in _REFLECTION_ROUTES and full_text.strip():
            yield {"token": "", "done": False, "phase": "reflecting", "message": "Проверяю ответ..."}
            ref = run_reflection_loop(model_name=model_name, profile_name=profile_name, user_input=user_input, draft_text=full_text, review_text="Улучши ответ.", context=ctx)
            refined = ref.get("answer", "")
            if refined and refined != full_text:
                full_text = refined
                yield {"token": "", "done": False, "phase": "reflection_replace", "full_text": refined}

        meta = {"model_name": model_name, "profile_name": profile_name, "route": route, "tools": selected, "run_id": run["run_id"]}
        _HISTORY.finish_run(run["run_id"], {"ok": True, "answer": full_text, "meta": meta})
        yield {"token": "", "done": True, "full_text": full_text, "meta": meta, "timeline": timeline}

    except Exception as exc:
        _HISTORY.finish_run(run["run_id"], {"ok": False, "error": str(exc)})
        yield {"token": "", "done": True, "error": str(exc), "full_text": ""}
