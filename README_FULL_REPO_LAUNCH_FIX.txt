JARVIS FULL REPO LAUNCH FIX

Заменяет:
- frontend/src/App.jsx
- frontend/src/api/ide.js
- frontend/src/components/JarvisChatShell.jsx
- frontend/src/components/IdeWorkspaceShell.jsx
- frontend/src/components/FileExplorerPanel.jsx
- frontend/src/components/TerminalPanel.jsx
- frontend/src/styles.css
- backend/app/main.py

Что делает:
- фиксит пустой App.jsx
- даёт единый api.js с chat + code + phase API
- чинит чатовый shell и новый чат
- убирает лишнюю J
- убирает строку "Режим: chat • qwen3:8b"
- добавляет выбор контекста
- делает верхний бар и code layout адаптивными
- монтирует chat/models/memory/library роуты на backend

Это минимальный launch-fix под текущий main.
