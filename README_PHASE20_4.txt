JARVIS PHASE 20.4 PATCH

Что внутри:
- backend/app/api/routes/jarvis_phase20_state.py
- frontend/src/components/Phase20Panel.jsx
- frontend/src/components/CodeWorkspace.jsx
- frontend/src/api/ide.js
- README_PHASE20_4.txt

Что добавляет:
- execution state для Phase20
- checkpoints перед apply/verify
- rollback strategy блок
- кнопку Build Execution State

Что делает:
- фиксирует queue/checkpoints/rollback advice
- подготавливает контролируемый execution flow
- делает основу для следующего шага:
  21 -> autonomous execution controller

Важно:
- backend нужно подключить роут execution-state в main.py
- после этого обычно остаётся 1 большая фаза + стабилизация:
  21 и финальный cleanup/polish
