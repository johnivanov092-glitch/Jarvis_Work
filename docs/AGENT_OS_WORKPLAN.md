# Agent OS - Рабочий план координации

> Этот файл - единый источник правды для всех агентов проекта.
> Читай его перед началом работы и обновляй после каждого завершенного этапа.

---

## Статус фаз

| Фаза | Описание | Исполнитель | Ветка | Статус | Зависимости |
|------|----------|-------------|-------|--------|-------------|
| 1 | Agent Registry + Persistent State | Claude Code | `feat/agent-os-phase1-registry` | **DONE** | — |
| 2 | Tool Registry с JSON Schema | Claude Code | `feat/agent-os-phase2-tools` | **DONE** | Phase 1 |
| 3 | Event Bus + межагентные сообщения | Codex | `feat/agent-os-phase3-eventbus` | **DONE** | Phase 1 + 2 |
| 4 | Workflow Engine | Codex | `feat/agent-os-phase4-workflows` | **DONE** | Phase 1 + 2 + 3 |
| 5 | Monitoring + Sandboxing | Codex | `feat/agent-os-phase5-monitoring` | **DONE** | Phase 3 + 4 |

---

## Правила работы

1. Каждый агент работает только в своей ветке.
2. Зависимые фазы веткуются от свежего `main` после мержа предыдущих фаз.
3. После взятия фазы ставь `IN PROGRESS`, после завершения — `DONE`.
4. Phase 1 служит шаблоном реализации: `schema -> service -> routes -> main.py -> tests`.
5. Каждый новый сервис создает свою `.db` через `sqlite_data_file()` из `app/core/data_files.py`.
6. Тесты фазы живут в `backend/tests/test_agent_os_phaseN.py`.
7. Пушить фазовые ветки нужно сразу после осмысленных коммитов.
8. Детальный локальный журнал этапов и работ обязательно ведется в [ACTUAL_WORK.md](/D:/AIWork/Elira_AI/docs/ACTUAL_WORK.md).
9. Агенты координируются между собой сами: все статусы, зависимости, заглушки, handoff-заметки и договоренности фиксируются в этом файле и в `ACTUAL_WORK.md`, без перекладывания роли посредника на пользователя.

---

## Phase 1: Agent Registry (DONE)

**Цель:** дать агентам постоянную идентичность, состояние между вызовами и историю запусков.

**Создано:**
- `backend/app/schemas/agent_registry.py`
- `backend/app/services/agent_registry.py`
- `backend/app/api/routes/agent_registry_routes.py`
- `backend/tests/test_agent_os_phase1.py`

**Изменено:**
- `backend/app/main.py` — подключен роутер и seed builtin agents
- `backend/app/services/agents_service.py` — добавлен `agent_id` в `run_agent()`

**БД:** `data/agent_registry.db`

**API:** `/api/agent-os/agents/*`

---

## Phase 2: Tool Registry (Claude Code)

**Цель:** заменить `if/elif` в `tool_service.py` динамическим реестром инструментов.

**Новые файлы:**
- `backend/app/services/tool_registry.py`
- `backend/app/schemas/tool_registry.py`
- `backend/app/api/routes/tool_registry_routes.py`
- `backend/tests/test_agent_os_phase2.py`

**БД:** `data/tool_registry.db`

```sql
tools (
  name TEXT PRIMARY KEY,
  display_name TEXT,
  display_name_ru TEXT,
  description TEXT,
  category TEXT,
  parameters_schema_json TEXT,
  source TEXT,
  enabled INTEGER,
  version INTEGER,
  created_at TEXT,
  updated_at TEXT
)
```

**Модификации:**
- `tool_service.py` — ветки переводятся в отдельные функции, `run_tool()` делегирует в registry
- `plugin_system.py` — плагины регистрируются как `source="plugin"`
- `main.py` — подключение нового роутера

**API:**
- `GET /api/agent-os/tools`
- `GET /api/agent-os/tools/{name}`
- `POST /api/agent-os/tools/{name}/execute`
- `POST /api/agent-os/tools`

---

## Phase 3: Event Bus (Codex)

**Цель:** дать агентам общую событийную шину, audit trail и прямые сообщения.

**Новые файлы:**
- `backend/app/services/event_bus.py`
- `backend/app/schemas/event_bus.py`
- `backend/app/api/routes/event_bus_routes.py`
- `backend/tests/test_agent_os_phase3.py`

**БД:** `data/event_bus.db`

```sql
events (
  id INTEGER PRIMARY KEY,
  event_id TEXT UNIQUE,
  event_type TEXT,
  payload_json TEXT,
  source_agent_id TEXT,
  created_at TEXT
)

agent_messages (
  id INTEGER PRIMARY KEY,
  message_id TEXT UNIQUE,
  from_agent TEXT,
  to_agent TEXT,
  content_json TEXT,
  reply_to TEXT,
  read INTEGER,
  created_at TEXT
)

subscriptions (
  id INTEGER PRIMARY KEY,
  subscriber_id TEXT,
  event_type TEXT,
  handler_name TEXT,
  created_at TEXT,
  UNIQUE(subscriber_id, event_type)
)
```

**Типы событий:**
- `agent.run.started`
- `agent.run.completed`
- `tool.executed` — каноническое tool-событие из реального пути Tool Registry
- `workflow.step.completed` — штатное workflow step-событие для workflow runtime

**Модификации:**
- `agents_service.py` — emit `agent.run.started` и `agent.run.completed`
- `main.py` — подключение роутера Event Bus

**Состояние после Phase 2 merge:**
- `tool_service.py` делегирует execution в Tool Registry
- `workflow_engine.py` использует registry-native tool execution semantics
- `tool.executed` эмитится из канонического Tool Registry execution path

**API:**
- `POST /api/agent-os/events`
- `GET /api/agent-os/events`
- `POST /api/agent-os/messages`
- `GET /api/agent-os/agents/{agent_id}/messages`
- `PATCH /api/agent-os/messages/{message_id}/read`
- `POST /api/agent-os/subscriptions`
- `GET /api/agent-os/subscriptions`
- `DELETE /api/agent-os/subscriptions`

---

## Phase 4: Workflow Engine

**Зависимости:** в `main` должны быть Phase 1 + 2 + 3.  
**Детали:** см. `C:\Users\Root\.claude\plans\parallel-drifting-lampson.md`

---

## Phase 5: Monitoring + Sandboxing

**Зависимости:** в `main` должна быть Phase 1 + 2 + 3 + 4.  
**Детали:** см. `C:\Users\Root\.claude\plans\parallel-drifting-lampson.md`

---

## Wave 6: Consolidation First (DONE)

**Цель:** after the Phase 2 merge on `main`, close the remaining post-merge seams and make Agent OS behave like one integrated runtime instead of five loosely green slices.

**Track 6A - Tool/Event Convergence**
- `tool.executed` must come from the real Tool Registry execution path.
- Workflow tool steps must use registry-native execution semantics instead of a Phase 4 adapter seam.
- Soft-sandbox allowlists must derive from enabled Tool Registry tools, not from static local names.

**Track 6B - Runtime Hygiene + Integration Hardening**
- Runtime SQLite/state files must stop polluting `git status` during normal development.
- `multi_agent_chain.py` must remain a thin workflow-backed shim with no dead legacy body above the override.
- One integration suite must cover `agent run -> tool execution -> event emission -> workflow run -> monitoring metrics`.

**Merge gate for this wave**
- Finish convergence first, then finish runtime cleanup and the full integration pass.

**Wave 6 outcome**
- Tool Registry is the single source of truth for tool metadata, execution, canonical `tool.executed`, and tool-aware sandbox allowlists.
- Workflow tool steps now use registry-native execution semantics instead of a post-Phase-2 adapter seam.
- Runtime SQLite/state files are excluded from normal git tracking; code/docs/fixtures remain tracked, while live state stays local.
- Consolidation is verified by a dedicated integration chain covering `agent run -> tool execution -> event emission -> workflow run -> monitoring metrics`.

---

## Лог изменений

| Дата | Кто | Что |
|------|-----|-----|
| 2026-03-30 | Claude Code | Phase 1 завершена, ветка `feat/agent-os-phase1-registry` подготовлена |
| 2026-03-30 | Claude Code | Создан общий workplan и распределены Phase 2-3 |
| 2026-03-30 | Codex | Взята Phase 3, создана ветка `feat/agent-os-phase3-eventbus`, реализация Event Bus начата |
| 2026-03-30 | Codex | Phase 3 завершена: Event Bus, subscriptions, agent messages, emit в `run_agent`/`run_agent_stream`, тесты и smoke-check зелёные |
| 2026-03-30 | Codex | Зафиксировано правило самокоординации: два агента синхронизируют статусы и handoff через `AGENT_OS_WORKPLAN.md` и `ACTUAL_WORK.md` без ручной передачи через пользователя |
| 2026-03-30 | Codex | Взята Phase 4, создана ветка `feat/agent-os-phase4-workflows`, Workflow Engine стартует параллельно незавершённой Phase 2 через локальный tool adapter |
| 2026-03-30 | Codex | Взята Phase 5, создана ветка `feat/agent-os-phase5-monitoring`, backend checkpoint готов: monitoring DB, soft sandbox hooks, workflow metrics, новые `/api/agent-os/health|dashboard|limits*`, tests + smoke зелёные; следующий шаг — read-only UI секция |
| 2026-03-30 | Codex | Phase 5 завершена: read-only `Agent OS` секция добавлена в dashboard, UI подтягивает health/dashboard/limits, `npm --prefix frontend run build` зелёный, фаза помечена как DONE |
| 2026-03-31 | Codex | Wave 6 consolidation выполнена: Tool Registry стал каноническим источником `tool.executed` и execution semantics, workflow tool steps переведены на registry-native execution, `multi_agent_chain.py` очищен до thin workflow shim |
| 2026-03-31 | Codex | Зафиксирована runtime hygiene policy: live SQLite/state исключены из обычного git tracking, добавлены integration tests и расширен smoke-check для Agent OS post-merge цепочки |
