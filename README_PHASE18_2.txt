
JARVIS PHASE 18.2

Добавляет:
- partial auto apply pipeline

Новый endpoint:

POST /api/jarvis/supervisor/auto-apply

Что делает:
- применяет preview контент к файлу
- создаёт .bak backup
- возвращает статус

UI:
SupervisorAutoApplyPanel

Теперь pipeline:

Supervisor Execute
→ Preview
→ Auto Apply
→ Verify

Важно:
backup создаётся автоматически
