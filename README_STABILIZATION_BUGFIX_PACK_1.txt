JARVIS STABILIZATION BUGFIX PACK 1

Что внутри:
- backend/app/api/routes/jarvis_stabilization.py
- backend/app/main.py
- frontend/src/api/ide.js
- frontend/src/components/StabilizationPreflightPanel.jsx
- README_STABILIZATION_BUGFIX_PACK_1.txt

Что делает:
- добавляет preflight endpoint перед execution
- проверяет queue / checkpoints / controller / staged files
- даёт единый main.py со всеми phase routers
- даёт единый api.js после накопленных фаз
- добавляет отдельную панель preflight

Это уже не новая фаза, а первый нормальный bugfix/stabilization шаг.
