JARVIS PHASE 17.3 PATCH

Что внутри:
- frontend/src/api/ide.js
- frontend/src/components/FileExplorer.jsx
- frontend/src/components/CodeEditor.jsx
- frontend/src/components/DiffViewer.jsx
- frontend/src/components/TerminalPanel.jsx
- frontend/src/components/CodeWorkspace.jsx
- frontend/src/styles.css

Что добавляет:
- настоящий Code Workspace внутри общей chat-first оболочки
- File Explorer на основе /snapshot
- открытие файлов на основе /file
- редактор кода
- Patch Preview через /agent/ollama/run
- локальный rollback
- панель терминала/событий
- Diff preview current vs proposed

Как ставить:
1. Скопируй файлы поверх проекта с заменой.
2. Перезапусти frontend / tauri.
3. Backend должен уже содержать /snapshot, /file и /agent/ollama/run.

Важно:
- этот патч не применяет изменения в файл на диске автоматически
- Apply to Editor применяет preview только локально в редакторе
- следующий патч может добавить реальный apply/rollback на backend
