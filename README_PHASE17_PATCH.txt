Jarvis Phase 17 — Chat-first patch bundle

Install:
1. Extract this archive into the project root with overwrite enabled.
2. Restart FastAPI backend.
3. Restart Tauri / frontend.

Replaced / added files:
- backend/app/api/routes/project_brain.py
- frontend/src/api/ide.js
- frontend/src/components/JarvisChatShell.jsx
- frontend/src/App.jsx
- frontend/src/styles.css

What this patch changes:
- switches UI from IDE-first to chat-first Jarvis shell
- adds direct file attachments in chat
- adds project-file attachments in chat
- adds Ollama model selection
- adds auto routing: chat / plan / research / code / analyze / image prompt routing
- adds web search context via DuckDuckGo HTML + page fetch
- keeps patch preview / apply / rollback / verify for code suggestions
- exposes legacy agent catalog based on old Streamlit-era agents transfer
