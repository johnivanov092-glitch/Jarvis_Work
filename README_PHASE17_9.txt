JARVIS PHASE 17.9 PATCH

Что внутри:
- backend/app/api/routes/jarvis_task_runner.py
- frontend/src/api/ide.js
- frontend/src/components/TaskHistoryPanel.jsx
- frontend/src/components/TaskRunnerPanel.jsx
- frontend/src/components/CodeWorkspace.jsx
- frontend/src/styles.css

Что добавляет:
- task execution history в SQLite:
  - GET /api/jarvis/task/history/list
  - GET /api/jarvis/task/history/get
- supervisor pipeline в Task Runner:
  planner -> coder -> reviewer -> tester
- панель Task History
- загрузку и просмотр истории прошлых task runs

Важно:
- backend нужно перезапустить
- task runner всё ещё строит pipeline безопасно, без автоприменения патчей
- это основа для следующего шага: реальный supervisor execution
