JARVIS PHASE 20.3 PATCH

Что внутри:
- backend/app/api/routes/jarvis_phase20_queue.py
- frontend/src/components/Phase20Panel.jsx
- frontend/src/components/CodeWorkspace.jsx
- frontend/src/api/ide.js
- README_PHASE20_3.txt

Что добавляет:
- multi-file preview queue для Phase20
- кнопку Build Preview Queue
- кнопку Preview Next
- состояние очереди preview в UI

Что делает:
- строит очередь preview targets
- позволяет по очереди прогонять execution preview по нескольким файлам
- сохраняет результат preview в stagedContents
- готовит переход к следующему шагу:
  20.4 -> execution state / checkpoints / rollback strategy

Важно:
- backend нужно подключить роут preview-queue в main.py
- до первого автономного v1 обычно осталось 2–3 крупных фазы:
  20.4, 21 и финальная стабилизация
