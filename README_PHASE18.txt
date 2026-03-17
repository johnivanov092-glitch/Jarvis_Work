JARVIS PHASE 18 PATCH

Что внутри:
- backend/app/api/routes/jarvis_supervisor.py
- frontend/src/api/ide.js
- frontend/src/components/SupervisorPanel.jsx
- frontend/src/components/CodeWorkspace.jsx
- frontend/src/styles.css
- README_PHASE18.txt

Что добавляет:
- Supervisor execution pipeline:
  POST /api/jarvis/supervisor/run
- Supervisor history:
  GET /api/jarvis/supervisor/history/list
  GET /api/jarvis/supervisor/history/get
- новую панель Supervisor
- history для supervisor runs в SQLite

Что делает:
- строит pipeline planner -> coder -> reviewer -> tester
- сохраняет supervisor runs
- даёт отдельную supervisor-оболочку поверх task runner

Важно:
- backend нужно перезапустить
- supervisor пока строит и сохраняет pipeline безопасно, без автоматического внесения изменений в файлы
