JARVIS PHASE 18.1 PATCH

Что внутри:
- backend/app/api/routes/jarvis_supervisor.py
- frontend/src/api/ide.js
- frontend/src/components/SupervisorPanel.jsx
- frontend/src/components/CodeWorkspace.jsx
- frontend/src/styles.css
- README_PHASE18_1.txt

Что добавляет:
- реальный supervisor execute flow:
  POST /api/jarvis/supervisor/execute
- supervisor теперь может:
  - собрать plan
  - подготовить preview для текущего файла
  - выдать verify-ready шаги
- в UI добавлена кнопка:
  Execute Flow

Что делает:
- связывает supervisor с текущим file workflow
- пробрасывает proposed content в preview внутри Code Workspace
- подготавливает переход к следующему шагу:
  Execute -> Preview -> Apply -> Verify

Важно:
- backend нужно перезапустить
- execute flow пока не делает автоматический apply в файл на диске
- apply и verify остаются явным подтверждением через существующий Patch Engine
