JARVIS PHASE 19 PATCH

Что внутри:
- backend/app/main.py
- backend/app/api/routes/jarvis_phase19.py
- frontend/src/api/ide.js
- frontend/src/components/Phase19Panel.jsx
- README_PHASE19.txt

Что добавляет:
- Multi-file Dev Loop:
  POST /api/jarvis/phase19/run
- Phase 19 history:
  GET /api/jarvis/phase19/history/list
  GET /api/jarvis/phase19/history/get
- project reasoning
- multi-file plan
- file operations summary
- verify summary

Что делает:
- анализирует несколько выбранных файлов
- строит multi-file reasoning по задаче
- готовит план modify/create
- готовит verify targets и file operations

Важно:
- backend нужно перезапустить
- это безопасный reasoning/pipeline слой
- auto apply по нескольким файлам здесь ещё не выполняется автоматически
