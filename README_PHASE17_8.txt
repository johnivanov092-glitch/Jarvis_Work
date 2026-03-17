JARVIS PHASE 17.8 PATCH

Что внутри:
- backend/app/main.py
- backend/app/api/routes/jarvis_task_runner.py
- frontend/src/api/ide.js
- frontend/src/components/TaskRunnerPanel.jsx
- frontend/src/components/CodeWorkspace.jsx
- frontend/src/styles.css

Что добавляет:
- Task Runner:
  POST /api/jarvis/task/run
- новую панель Task Runner справа в Code Workspace
- workflow:
  goal -> plan -> preview targets -> next steps
- безопасную основу для task pipeline:
  Plan -> Stage -> Apply -> Verify

Важно:
- backend нужно перезапустить
- task runner пока не применяет патчи автоматически, он строит pipeline и шаги выполнения
- это правильная база для следующей фазы с реальным auto-run по шагам
