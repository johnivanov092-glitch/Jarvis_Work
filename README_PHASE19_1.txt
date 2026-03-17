JARVIS PHASE 19.1 PATCH

Что внутри:
- frontend/src/api/ide.js
- frontend/src/components/CodeWorkspace.jsx
- README_PHASE19_1.txt

Что добавляет:
- встраивает Phase19Panel прямо в CodeWorkspace
- связывает Phase19 со staged файлами
- подключает историю Phase19
- делает основу для следующего шага:
  Phase19 -> Batch Apply -> Batch Verify

Что делает:
- передаёт staged файлы в multi-file reasoning
- позволяет открывать историю запусков Phase19
- выводит Phase19 как верхнюю orchestration панель справа

Важно:
- backend должен уже содержать Phase19 endpoints
- frontend перезапустить после замены
