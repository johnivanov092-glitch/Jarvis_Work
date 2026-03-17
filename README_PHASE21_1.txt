JARVIS PHASE 21.1 STABILIZATION PACK

Что внутри:
- backend/app/main.py
- frontend/src/api/ide.js
- frontend/src/components/Phase21StatusStrip.jsx
- README_PHASE21_1.txt

Что делает:
- подключает все накопленные phase routers в одном main.py
- даёт единый стабилизированный api.js
- добавляет небольшой status strip для Phase20/21 состояния
- закрывает интеграционный разрыв между 20.3 / 20.4 / 21

Что проверить после замены:
1. backend стартует без import error
2. /health отвечает
3. Phase20 queue строится
4. Phase20 execution state строится
5. Phase21 controller run сохраняется в history

Важно:
- это stabilization pack, не новый большой функциональный слой
- дальше уже нужен bugfix / cleanup / UX polish pass под твой реальный репозиторий
