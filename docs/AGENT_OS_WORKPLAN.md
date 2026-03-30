# Agent OS — Рабочий план координации

> Этот файл — единый источник правды для всех агентов (Claude Code, Codex).
> Читай перед началом работы. Обновляй после каждого завершённого этапа.

---

## Статус фаз

| Фаза | Описание | Исполнитель | Ветка | Статус | Зависимости |
|-------|---------|------------|-------|--------|-------------|
| 1 | Agent Registry + Persistent State | Claude Code | `feat/agent-os-phase1-registry` | **DONE** | — |
| 2 | Tool Registry с JSON Schema | Claude Code | `feat/agent-os-phase2-tools` | **TODO** | Phase 1 |
| 3 | Event Bus + межагентные сообщения | Codex | `feat/agent-os-phase3-eventbus` | **TODO** | Phase 1 (core), Phase 2 (tool.executed — заглушка) |
| 4 | Workflow Engine | Свободный | `feat/agent-os-phase4-workflows` | **TODO** | Phase 1 + 2 + 3 |
| 5 | Monitoring + Sandboxing | Свободный | `feat/agent-os-phase5-monitoring` | **TODO** | Phase 3 |

---

## Правила работы

1. **Раздельные ветки** — каждый агент работает в своей ветке, никогда в чужой
2. **Мерж в main** — каждая фаза мержится по готовности, зависимые бранчуются от свежего main
3. **Обновляй этот файл** — после завершения фазы поставь DONE, после взятия — IN PROGRESS + имя исполнителя
4. **Паттерн кода** — Phase 1 служит шаблоном: schema → service → routes → main.py → tests
5. **БД** — каждый сервис создаёт свой `.db` через `sqlite_data_file()` из `app/core/data_files.py`
6. **Тесты** — `backend/tests/test_agent_os_phaseN.py`, все должны проходить
7. **Пуш** — сразу после коммита, часто, ветки именуются `feat/agent-os-phaseN-*`

---

## Phase 1: Agent Registry (DONE)

**Файлы созданы:**
- `backend/app/schemas/agent_registry.py`
- `backend/app/services/agent_registry.py`
- `backend/app/api/routes/agent_registry_routes.py`
- `backend/tests/test_agent_os_phase1.py` (15 тестов)

**Модифицированы:**
- `backend/app/main.py` — роутер + seed
- `backend/app/services/agents_service.py` — `agent_id` в `run_agent()`

**БД:** `data/agent_registry.db` (agents, agent_state, agent_runs)

**API:** `/api/agent-os/agents/*`

---

## Phase 2: Tool Registry (Claude Code)

**Цель:** Заменить if/elif цепочку в `tool_service.py` динамическим реестром.

**Новые файлы:**
- `backend/app/services/tool_registry.py` — register, execute, validate, list_with_schemas, seed_builtin
- `backend/app/schemas/tool_registry.py` — ToolDefinition, ToolExecuteRequest/Response
- `backend/app/api/routes/tool_registry_routes.py` — `/api/agent-os/tools/*`
- `backend/tests/test_agent_os_phase2.py`

**БД:** `data/tool_registry.db`
```sql
tools (name TEXT PK, display_name, display_name_ru, description, category,
       parameters_schema_json, source, enabled, version, created_at, updated_at)
```

**Модификации:**
- `tool_service.py` — каждая if/elif ветка → отдельная функция, `run_tool()` делегирует в registry
- `plugin_system.py` — авторегистрация плагинов как tools (source="plugin")
- `main.py` — подключить роутер

**API:**
- `GET /api/agent-os/tools` — список с JSON Schema
- `GET /api/agent-os/tools/{name}` — детали
- `POST /api/agent-os/tools/{name}/execute` — выполнить
- `POST /api/agent-os/tools` — регистрация custom tool

---

## Phase 3: Event Bus (Codex)

**Цель:** Межагентная коммуникация через события + аудит-трейл.

**Новые файлы:**
- `backend/app/services/event_bus.py` — emit, subscribe, send_message, get_messages
- `backend/app/schemas/event_bus.py` — Event, AgentMessage, Subscription
- `backend/app/api/routes/event_bus_routes.py` — `/api/agent-os/events/*`, `/api/agent-os/messages/*`
- `backend/tests/test_agent_os_phase3.py`

**БД:** `data/event_bus.db`
```sql
events (id INTEGER PK, event_id TEXT UNIQUE, event_type TEXT, payload_json TEXT,
        source_agent_id TEXT, created_at TEXT)
-- idx: event_type, source_agent_id

agent_messages (id INTEGER PK, message_id TEXT UNIQUE, from_agent TEXT,
               to_agent TEXT, content_json TEXT, reply_to TEXT, read INTEGER, created_at TEXT)
-- idx: to_agent+read

subscriptions (id INTEGER PK, subscriber_id TEXT, event_type TEXT,
              handler_name TEXT, created_at TEXT, UNIQUE(subscriber_id, event_type))
```

**Типы событий:**
- `agent.run.started` — при старте run_agent()
- `agent.run.completed` — при завершении run_agent()
- `tool.executed` — **ЗАГЛУШКА до мержа Phase 2**, после мержа подключить в tool_registry.py
- `workflow.step.completed` — заглушка до Phase 4

**Модификации:**
- `agents_service.py` — emit `agent.run.started/completed` в начале/конце `run_agent()`
- `main.py` — подключить роутер

**⚠️ Что НЕ делать (ждёт Phase 2):**
- Не трогать `tool_service.py`
- Не трогать `plugin_system.py`
- `tool.executed` — оставить как stub-подписку с комментарием `# TODO: wire after Phase 2 merge`

**API:**
- `POST /api/agent-os/events` — emit
- `GET /api/agent-os/events` — лог (с фильтрами)
- `POST /api/agent-os/messages` — отправить сообщение агенту
- `GET /api/agent-os/agents/{agent_id}/messages` — входящие
- `PATCH /api/agent-os/messages/{message_id}/read` — пометить прочитанным

---

## Phase 4: Workflow Engine

**Зависимости:** Phase 1 + 2 + 3 должны быть в main.
**Исполнитель:** кто свободен первым.
**Детали:** см. план в `C:\Users\Root\.claude\plans\parallel-drifting-lampson.md`

---

## Phase 5: Monitoring + Sandboxing

**Зависимости:** Phase 3 должна быть в main.
**Исполнитель:** кто свободен первым.
**Детали:** см. план в `C:\Users\Root\.claude\plans\parallel-drifting-lampson.md`

---

## Лог изменений

| Дата | Кто | Что |
|------|-----|-----|
| 2026-03-30 | Claude Code | Phase 1 завершена, ветка запушена |
| 2026-03-30 | Claude Code | Создан этот workplan, распределены Phase 2-3 |
