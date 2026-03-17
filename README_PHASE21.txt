JARVIS PHASE 21 PATCH

Что внутри:
- backend/app/api/routes/jarvis_phase21.py
- frontend/src/components/Phase21Panel.jsx
- frontend/src/components/CodeWorkspace.jsx
- frontend/src/api/ide.js
- README_PHASE21.txt

Что добавляет:
- autonomous execution controller:
  POST /api/jarvis/phase21/run
- history:
  GET /api/jarvis/phase21/history/list
  GET /api/jarvis/phase21/history/get
- новую верхнюю панель Phase21
- контроллер для queue + execution state

Что делает:
- объединяет preview queue и execution state
- строит controller steps:
  load-queue -> preview -> checkpoint -> apply -> verify -> rollback fallback
- связывает controller с batch apply / batch verify
- делает архитектурный переход к финальной стабилизации системы

Важно:
- backend нужно подключить router Phase21 в main.py
- после этого остаётся в основном cleanup / polish / bugfix pass
