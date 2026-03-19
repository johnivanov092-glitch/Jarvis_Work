"""
agents_service.py — главный агентный пайплайн.

Изменения:
  • history передаётся в LLM (контекст диалога)
  • reflection включается только для code/project/research (ускорение чата ×2)
  • run_agent_stream() — генератор SSE-событий для стриминга
"""
from __future__ import annotations

from typing import Any, Generator

from app.services.chat_service import run_chat, run_chat_stream
from app.services.planner_v2_service import PlannerV2Service
from app.services.reflection_loop_service import run_reflection_loop
from app.services.run_history_service import RunHistoryService
from app.services.tool_service import run_tool

_HISTORY = RunHistoryService()

# Маршруты, для которых включается reflection loop
_REFLECTION_ROUTES = {"code", "project", "research"}

# Максимум пар (user+assistant) из истории, передаваемых в LLM
_MAX_HISTORY_PAIRS = 10


def _short(value: Any, limit: int = 600) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit] + "..."


def _append_timeline(
    timeline: list[dict[str, Any]],
    step: str,
    title: str,
    status: str,
    detail: str,
) -> None:
    timeline.append(
        {
            "step": step,
            "title": title,
            "status": status,
            "detail": detail,
        }
    )


def _trim_history(history: list[dict[str, Any]], max_pairs: int = _MAX_HISTORY_PAIRS) -> list[dict[str, Any]]:
    """Оставляет последние max_pairs пар user/assistant."""
    if not history:
        return []
    limit = max_pairs * 2
    if len(history) <= limit:
        return list(history)
    return list(history[-limit:])


def _build_prompt(user_input: str, plan: dict[str, Any], context_bundle: str) -> str:
    tools = ", ".join(plan.get("tools", [])) or "no tools"
    route = plan.get("route", "chat")
    strategy = plan.get("strategy", "planner_v2")

    prompt = [
        "Ты главный агент Jarvis.",
        f"Маршрут: {route}",
        f"Стратегия: {strategy}",
        f"Инструменты: {tools}",
        "",
        "Сделай практичный итоговый ответ для пользователя.",
        "Если это задача по проекту или коду — укажи точные файлы, причины и предлагаемые изменения.",
        "Если есть дифф — покажи его кратко и понятно.",
        "Если контекста мало — честно скажи это.",
        "Форматируй ответ с помощью Markdown: заголовки, списки, блоки кода.",
        "",
        f"Запрос пользователя:\n{user_input}",
    ]

    if context_bundle.strip():
        prompt.extend(["", f"Контекст:\n{context_bundle}"])

    return "\n".join(prompt)


def _collect_tool_context(
    *,
    profile_name: str,
    user_input: str,
    tools: list[str],
    tool_results: list[dict[str, Any]],
    timeline: list[dict[str, Any]],
) -> str:
    context_parts: list[str] = []

    for tool_name in tools:
        try:
            if tool_name == "memory_search":
                result = run_tool(
                    "search_memory",
                    {"profile": profile_name, "query": user_input, "limit": 5},
                )
                tool_results.append({"tool": "search_memory", "result": result})
                _append_timeline(
                    timeline,
                    "tool_memory",
                    "Tool: search_memory",
                    "done",
                    f"Найдено записей: {result.get('count', 0)}",
                )
                items = result.get("items", [])
                if items:
                    context_parts.append(
                        "Memory:\n" + "\n".join(f"- {item.get('text', '')}" for item in items)
                    )

            elif tool_name == "library_context":
                result = run_tool("build_library_context", {})
                tool_results.append({"tool": "build_library_context", "result": result})
                has_context = bool(result.get("context"))
                _append_timeline(
                    timeline,
                    "tool_library",
                    "Tool: build_library_context",
                    "done" if has_context else "warning",
                    "Контекст библиотеки собран" if has_context else "Контекст библиотеки пуст",
                )
                if result.get("context"):
                    context_parts.append("Library:\n" + str(result["context"]))

            elif tool_name == "web_search":
                # Один вызов DuckDuckGo вместо 5 дублей
                from app.services.web_service import search_web
                web_result = search_web(user_input, max_results=8)
                tool_results.append({"tool": "web_search", "result": web_result})

                sources = web_result.get("sources", [])
                engines_used = web_result.get("engines_used", [])
                engines_str = ", ".join(engines_used) if engines_used else "none"
                _append_timeline(
                    timeline,
                    "tool_web_search",
                    f"Tool: web_search ({engines_str})",
                    "done" if sources else "warning",
                    f"Найдено {len(sources)} источников через {len(engines_used)} движков",
                )

                if sources:
                    web_lines = []
                    for src in sources[:6]:
                        title = src.get("title", "")
                        snippet = src.get("snippet", "")
                        url = src.get("url", "")
                        web_lines.append(f"- [{title}]({url}): {snippet}")
                    context_parts.append("Web:\n" + "\n".join(web_lines))

            elif tool_name == "project_mode":
                tree = run_tool("list_project_tree", {"max_depth": 3, "max_items": 200})
                search = run_tool("search_project", {"query": user_input, "max_hits": 20})

                tool_results.append({"tool": "list_project_tree", "result": tree})
                tool_results.append({"tool": "search_project", "result": search})

                _append_timeline(
                    timeline,
                    "tool_project_tree",
                    "Tool: list_project_tree",
                    "done",
                    f"Элементов дерева: {tree.get('count', 0)}",
                )
                _append_timeline(
                    timeline,
                    "tool_project_search",
                    "Tool: search_project",
                    "done",
                    f"Хитов: {search.get('count', 0)}",
                )

                snippets = search.get("items") or search.get("results") or []
                if snippets:
                    rendered: list[str] = []
                    for item in snippets[:10]:
                        if isinstance(item, dict):
                            path = item.get("path", "")
                            excerpt = item.get("snippet", "") or item.get("preview", "")
                            rendered.append(f"- {path}: {excerpt}")
                        else:
                            rendered.append(f"- {item}")
                    context_parts.append("Project:\n" + "\n".join(rendered))

            elif tool_name == "project_patch":
                _append_timeline(
                    timeline,
                    "tool_project_patch",
                    "Tool: project_patch",
                    "ready",
                    "Patch mode доступен: preview_project_patch / apply_project_patch / replace_in_file",
                )
                context_parts.append(
                    "Patch mode:\n"
                    "- Используй preview_project_patch для предпросмотра diff\n"
                    "- Используй apply_project_patch для записи полного нового файла\n"
                    "- Используй replace_in_file для точечной замены блока"
                )

            elif tool_name == "python_executor":
                _append_timeline(
                    timeline,
                    "tool_python",
                    "Tool: python_executor",
                    "skipped",
                    "Маршрут для Python определён, но выполнение требует явного кода.",
                )

        except Exception as exc:
            _append_timeline(
                timeline,
                f"tool_{tool_name}",
                f"Tool: {tool_name}",
                "error",
                str(exc),
            )

    return "\n\n".join(part for part in context_parts if part.strip())


# ═══════════════════════════════════════════════════════════════════
# run_agent — обычный (полный ответ)
# ═══════════════════════════════════════════════════════════════════

def run_agent(
    *,
    model_name: str,
    profile_name: str,
    user_input: str,
    use_memory: bool = True,
    use_library: bool = True,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    history = _trim_history(history or [])
    timeline: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    planner = PlannerV2Service()
    run = _HISTORY.start_run(user_input)

    try:
        plan = planner.plan(user_input)
        _HISTORY.add_event(run["run_id"], "planner", plan)

        _append_timeline(
            timeline,
            "planner",
            "Planner V2",
            "done",
            f"route={plan.get('route')} tools={', '.join(plan.get('tools', []))}",
        )

        selected_tools: list[str] = []
        for tool in plan.get("tools", []):
            if tool == "memory_search" and not use_memory:
                continue
            if tool == "library_context" and not use_library:
                continue
            selected_tools.append(tool)

        context_bundle = _collect_tool_context(
            profile_name=profile_name,
            user_input=user_input,
            tools=selected_tools,
            tool_results=tool_results,
            timeline=timeline,
        )

        prompt = _build_prompt(user_input, plan, context_bundle)

        # Передаём ИСТОРИЮ в LLM
        draft_result = run_chat(
            model_name=model_name,
            profile_name=profile_name,
            user_input=prompt,
            history=history,
        )

        if not draft_result.get("ok"):
            raise RuntimeError("; ".join(draft_result.get("warnings", [])) or "LLM call failed")

        draft_answer = draft_result.get("answer", "")
        _append_timeline(
            timeline,
            "draft_answer",
            "Draft answer",
            "done",
            _short(draft_answer),
        )

        route = plan.get("route", "chat")
        final_answer = draft_answer

        # Reflection только для сложных маршрутов
        if route in _REFLECTION_ROUTES:
            review_text = (
                "Проверь ответ на ясность, конкретность и практическую пользу. "
                "Если ответ про проект или код, проверь наличие ссылок на файлы, патч-стратегии и чётких шагов."
            )

            reflection = run_reflection_loop(
                model_name=model_name,
                profile_name=profile_name,
                user_input=user_input,
                draft_text=draft_answer,
                review_text=review_text,
                context=context_bundle,
            )

            final_answer = reflection.get("answer") or draft_answer
            _append_timeline(
                timeline,
                "reflection",
                "Reflection loop",
                "done" if reflection.get("ok") else "warning",
                _short(final_answer),
            )
        else:
            _append_timeline(
                timeline,
                "reflection",
                "Reflection loop",
                "skipped",
                "Пропущен для маршрута chat (ускорение)",
            )

        result = {
            "ok": True,
            "answer": final_answer,
            "timeline": timeline,
            "tool_results": tool_results,
            "meta": {
                "model_name": model_name,
                "profile_name": profile_name,
                "route": route,
                "tools": selected_tools,
                "run_id": run["run_id"],
                "strategy": plan.get("strategy", "planner_v2"),
            },
        }
        _HISTORY.finish_run(run["run_id"], result)
        return result

    except Exception as exc:
        error_result = {
            "ok": False,
            "answer": "",
            "timeline": timeline + [
                {
                    "step": "agent_error",
                    "title": "Ошибка агента",
                    "status": "error",
                    "detail": str(exc),
                }
            ],
            "tool_results": tool_results,
            "meta": {
                "error": str(exc),
                "run_id": run["run_id"],
            },
        }
        _HISTORY.finish_run(run["run_id"], error_result)
        return error_result


# ═══════════════════════════════════════════════════════════════════
# run_agent_stream — SSE-генератор
# ═══════════════════════════════════════════════════════════════════

def run_agent_stream(
    *,
    model_name: str,
    profile_name: str,
    user_input: str,
    use_memory: bool = True,
    use_library: bool = True,
    history: list[dict[str, Any]] | None = None,
) -> Generator[dict[str, Any], None, None]:
    """
    Генератор событий для SSE.
    Отдаёт:
      {"token": "...", "done": false}   — каждый токен
      {"token": "", "done": true, "full_text": "...", "meta": {...}} — финал
    """
    history = _trim_history(history or [])
    timeline: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    planner = PlannerV2Service()
    run = _HISTORY.start_run(user_input)

    try:
        plan = planner.plan(user_input)
        _HISTORY.add_event(run["run_id"], "planner", plan)

        _append_timeline(timeline, "planner", "Planner V2", "done",
                         f"route={plan.get('route')} tools={', '.join(plan.get('tools', []))}")

        selected_tools: list[str] = []
        for tool in plan.get("tools", []):
            if tool == "memory_search" and not use_memory:
                continue
            if tool == "library_context" and not use_library:
                continue
            selected_tools.append(tool)

        # Собираем контекст из инструментов
        context_bundle = _collect_tool_context(
            profile_name=profile_name,
            user_input=user_input,
            tools=selected_tools,
            tool_results=tool_results,
            timeline=timeline,
        )

        # Уведомляем фронт о том, что инструменты отработали
        yield {"token": "", "done": False, "phase": "tools_done", "timeline": timeline}

        prompt = _build_prompt(user_input, plan, context_bundle)
        route = plan.get("route", "chat")

        # Стримим токены из LLM
        full_text = ""
        for token in run_chat_stream(
            model_name=model_name,
            profile_name=profile_name,
            user_input=prompt,
            history=history,
        ):
            full_text += token
            yield {"token": token, "done": False}

        _append_timeline(timeline, "draft_answer", "Draft answer", "done", _short(full_text))

        # Reflection для сложных маршрутов (НЕ стримится — отдаётся целиком)
        if route in _REFLECTION_ROUTES and full_text.strip():
            review_text = (
                "Проверь ответ на ясность, конкретность и практическую пользу. "
                "Если ответ про код — проверь ссылки на файлы и чёткие шаги."
            )
            reflection = run_reflection_loop(
                model_name=model_name,
                profile_name=profile_name,
                user_input=user_input,
                draft_text=full_text,
                review_text=review_text,
                context=context_bundle,
            )
            refined = reflection.get("answer", "")
            if refined and refined != full_text:
                full_text = refined
                # Отправляем замену целиком
                yield {"token": "", "done": False, "phase": "reflection_replace", "full_text": refined}

            _append_timeline(timeline, "reflection", "Reflection loop",
                             "done" if reflection.get("ok") else "warning", _short(full_text))

        # Финальный пакет
        meta = {
            "model_name": model_name,
            "profile_name": profile_name,
            "route": route,
            "tools": selected_tools,
            "run_id": run["run_id"],
            "strategy": plan.get("strategy", "planner_v2"),
        }

        result = {
            "ok": True,
            "answer": full_text,
            "timeline": timeline,
            "tool_results": tool_results,
            "meta": meta,
        }
        _HISTORY.finish_run(run["run_id"], result)

        yield {
            "token": "",
            "done": True,
            "full_text": full_text,
            "meta": meta,
            "timeline": timeline,
        }

    except Exception as exc:
        _HISTORY.finish_run(run["run_id"], {"ok": False, "error": str(exc)})
        yield {
            "token": "",
            "done": True,
            "error": str(exc),
            "full_text": "",
        }
