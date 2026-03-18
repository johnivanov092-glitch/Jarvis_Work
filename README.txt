PHASE 18 — ISOLATED AGENT RUNTIME PACK

Это безопасное расширение.
Оно НЕ трогает текущий визуал агента и НЕ лезет в JarvisChatShell.
Оно добавляет отдельный backend runtime endpoint и отдельный frontend api helper.

Структура для копирования:

backend/
  app/
    services/
      agent_task_planner.py
      agent_runtime_service.py
    api/
      routes/
        agent_runtime.py
    main.py   <- подключить router из backend/app/main.py.patch.txt

frontend/
  src/
    api/
      agentRuntime.js

Что дает:
- отдельный endpoint /api/agent-runtime/run
- построение простого плана
- список runtime events
- отдельный answer
- изоляцию от текущего chat UI

Как проверить:
POST http://127.0.0.1:8000/api/agent-runtime/run

Body:
{
  "user_input": "проанализируй код и предложи план"
}
