JARVIS PHASE 20.1 PATCH

Что внутри:
- frontend/src/components/CodeWorkspace.jsx
- README_PHASE20_1.txt

Что добавляет:
- встраивает Phase20Panel прямо в CodeWorkspace
- связывает Phase20 со staged файлами
- добавляет:
  - Stage Execution Files
  - Apply Execution
  - Verify Execution
- Phase20 становится верхней orchestration-панелью справа

Что делает:
- использует planner items из Phase20 для автодобавления файлов в stage
- связывает Phase20 execution с batch apply / batch verify
- завершает первую рабочую цепочку:
  Phase20 -> Stage -> Apply -> Verify

Важно:
- backend уже должен содержать endpoints Phase20
- фронт нужно перезапустить после замены
