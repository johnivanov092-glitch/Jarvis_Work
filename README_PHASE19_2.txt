JARVIS PHASE 19.2 PATCH

Что внутри:
- frontend/src/components/Phase19Panel.jsx
- frontend/src/components/CodeWorkspace.jsx
- README_PHASE19_2.txt

Что добавляет:
- связывает Phase19 напрямую с batch apply
- связывает Phase19 напрямую с batch verify
- добавляет кнопки:
  - Apply Planned Staged
  - Verify Planned Staged

Что делает:
- использует staged файлы как рабочий набор для multi-file исполнения
- после reasoning можно сразу перейти к batch apply / batch verify
- завершает первую рабочую связку:
  Phase19 -> Apply -> Verify

Важно:
- backend уже должен содержать patch batch endpoints и Phase19 endpoints
- фронт нужно перезапустить после замены
