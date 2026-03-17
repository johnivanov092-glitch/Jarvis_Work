PHASE 14 FULL PACK

Files included:
- backend/app/routers/project_brain_router.py
- frontend/src/api/ide.js
- frontend/src/components/FileExplorerPanel.jsx
- frontend/src/components/TerminalPanel.jsx
- frontend/src/components/IdeWorkspaceShell.jsx
- frontend/src/App.jsx
- frontend/src/styles.css

Put them into your project with the same paths.

IMPORTANT:
1. Register backend router in your backend main file if not already registered.
   Example:
   from app.routers.project_brain_router import router as project_brain_router
   app.include_router(project_brain_router)

2. Restart backend after replacing files.

3. Then run:
   cd D:/AIWork/jarvis_work
   npm.cmd run tauri dev
