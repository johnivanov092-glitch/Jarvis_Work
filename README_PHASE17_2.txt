JARVIS PHASE 17.2 PATCH

Что внутри:
- backend/app/main.py
- backend/app/api/routes/jarvis_execute.py
- frontend/src/App.jsx
- frontend/src/api/ide.js
- frontend/src/components/JarvisChatShell.jsx
- frontend/src/components/MemoryPanel.jsx
- frontend/src/components/CodeWorkspace.jsx
- frontend/src/styles.css

Что меняет:
- добавляет Router Mode через POST /api/jarvis/execute
- разводит Chat / Code / Research / Orchestrator / Text-to-Image по режимам
- добавляет отдельный слой памяти:
  - /api/jarvis/memory/save
  - /api/jarvis/memory/list
  - /api/jarvis/memory/delete
- добавляет левую вкладку Память
- добавляет встроенный Code tab внутри общего chat-first shell
- не ломает Tauri, меняет только backend API и frontend shell

Как ставить:
1. Скопируй файлы поверх проекта с заменой.
2. Перезапусти backend.
3. Перезапусти frontend / tauri.

Команды:
cd backend
uvicorn app.main:app --reload

npm run tauri dev
