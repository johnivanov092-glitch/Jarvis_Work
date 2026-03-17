JARVIS PHASE 17 — CUSTOM CHAT UI (RU)

Что внутри:
- frontend/src/App.jsx
- frontend/src/api/ide.js
- frontend/src/components/JarvisChatShell.jsx
- frontend/src/styles.css

Что изменено:
- возвращён chat-first интерфейс
- кнопка "Новый чат" наверху слева
- левое меню полностью на русском: Поиск / Чаты / Проекты / Настройки
- верхняя панель по центру: Jarvis + LLM + профиль агента + Chat / Code / Orchestrator / Text-to-Image
- уменьшена область ввода примерно на 25%
- список "Все чаты" оформлен красивыми карточками одинакового размера
- раздел Чаты = память чатов
- раздел Поиск = поиск по чатам и проектам по ключевым словам
- добавлены действия: сохранить в памяти / закрепить в памяти

Как ставить:
1. Скопируй файлы поверх проекта с заменой.
2. Перезапусти frontend / tauri.
3. Если backend уже поддерживает /api/jarvis/chats, /api/jarvis/messages, /api/jarvis/search, /api/jarvis/settings, UI заработает сразу.

Важно:
- Я не менял твой GitHub автоматически.
- Это готовый локальный пакет на замену файлов.
