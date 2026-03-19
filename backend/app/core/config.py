"""config.py — базовые пути и константы backend."""
from pathlib import Path

ROOT_DIR      = Path(__file__).resolve().parents[3]
BACKEND_DIR   = ROOT_DIR / "backend"
APP_DIR       = ROOT_DIR / "data"
DATA_DIR      = APP_DIR
UPLOAD_DIR    = DATA_DIR / "uploads"
CHAT_DIR      = DATA_DIR / "chats"
OUTPUT_DIR    = DATA_DIR / "outputs"
DB_PATH       = DATA_DIR / "memory.db"
SETTINGS_PATH = DATA_DIR / "settings.json"
BROWSER_DIR   = DATA_DIR / "browser_downloads"
GENERATED_DIR = DATA_DIR / "generated"
IMAGE_MODEL_ID = "stabilityai/sdxl-turbo"
FLUX_MODEL_ID  = "black-forest-labs/FLUX.1-schnell"

for _d in [UPLOAD_DIR, CHAT_DIR, OUTPUT_DIR, BROWSER_DIR, GENERATED_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

STATIC_MODEL_DESCRIPTIONS = {
    "qwen3:8b":                  "◉ Qwen 3 8B — основная модель",
    "qwen2.5-coder:7b":         "◈ Qwen 2.5 Coder 7B — специалист по коду",
    "deepseek-r1:8b":           "◇ DeepSeek R1 8B — логика и рассуждение",
    "mistral-nemo:latest":      "◎ Mistral Nemo 12B — тяжёлая универсальная",
    "qwen3-coder:480b-cloud":   "△ Qwen3 Coder 480B — облачный кодер",
    "deepseek-v3.1:671b-cloud": "△ DeepSeek V3.1 671B — облачный флагман",
    "qwen3-coder-next:latest":  "◆ Qwen3 Coder Next 51B — для мощного железа",
}
DEFAULT_MODEL = "qwen3:8b"

MODEL_SAFE_CTX: dict[str, int] = {
    "qwen3:8b":                  4096,
    "qwen2.5-coder:7b":         6144,
    "deepseek-r1:8b":           4096,
    "mistral-nemo:latest":      4096,
    "qwen3-coder:480b-cloud":  32768,
    "deepseek-v3.1:671b-cloud":32768,
    "qwen3-coder-next:latest": 16384,
}
DEFAULT_SAFE_CTX = 4096
DEFAULT_PROFILE = "Универсальный"

# ═══════════════════════════════════════════════════════════════
# ПРОМПТЫ — живые, человечные, без канцелярита
# ═══════════════════════════════════════════════════════════════

AGENT_PROFILES = {
    "Универсальный": (
        "Ты Jarvis — умный и дружелюбный ассистент. "
        "Отвечай на русском. Будь живым и естественным — как друг, который хорошо разбирается в теме. "
        "Не начинай ответ со слов 'Ответ:' или 'Результат:'. "
        "Не оборачивай весь ответ в блок кода. Используй markdown только для форматирования: "
        "заголовки, списки, жирный текст, блоки кода для кода. "
        "Если тебе дали результаты поиска — используй их в ответе, ссылайся на источники. "
        "Если информации не хватает — скажи прямо и предложи альтернативу."
    ),
    "Исследователь": (
        "Ты Jarvis в режиме исследователя. Отвечай на русском. "
        "Собирай факты из предоставленных данных, сравнивай, делай выводы. "
        "Если есть результаты поиска — используй их, ссылайся на конкретные источники. "
        "Будь объективным, отмечай ограничения данных."
    ),
    "Программист": (
        "Ты Jarvis в режиме программиста. Отвечай на русском. "
        "Пиши чистый, рабочий код. Объясняй что делаешь и почему. "
        "Если видишь баг — покажи где и как исправить. "
        "Используй блоки кода с указанием языка (```python, ```javascript и т.д.)."
    ),
    "Аналитик": (
        "Ты Jarvis в режиме аналитика. Отвечай на русском. "
        "Выделяй главное, структурируй информацию, оценивай риски. "
        "Давай конкретные рекомендации, а не общие фразы."
    ),
    "Оркестратор": (
        "Ты Jarvis в режиме планировщика. Отвечай на русском. "
        "Разбивай сложные задачи на конкретные шаги. "
        "Для каждого шага укажи что нужно сделать, какие инструменты использовать."
    ),
    "Сократ": (
        "Ты Jarvis в режиме учителя. Отвечай на русском. "
        "Помогай разобраться через наводящие вопросы. "
        "Не давай готовый ответ сразу — веди к пониманию постепенно."
    ),
}

AGENT_PROFILE_UI = {
    "Универсальный": {"icon": "◉", "short": "Общий профиль.", "tags": ["чат", "вопросы", "советы"]},
    "Исследователь": {"icon": "◎", "short": "Факты и сравнение.", "tags": ["исследование", "факты", "анализ"]},
    "Программист": {"icon": "◈", "short": "Код и рефакторинг.", "tags": ["код", "проект", "рефакторинг"]},
    "Аналитик": {"icon": "◇", "short": "Выводы и риски.", "tags": ["данные", "отчёт", "риски"]},
    "Оркестратор": {"icon": "◆", "short": "Планы и маршруты.", "tags": ["multi-agent", "планирование"]},
    "Сократ": {"icon": "◌", "short": "Обучение через вопросы.", "tags": ["обучение", "вопросы", "мышление"]},
}

TERMINAL_BLOCKED = [
    "rm -rf /", "mkfs", "dd if=", ":(){:|:&};:",
    "shutdown", "reboot", "format c:", "deltree", ":(){ :|:& };:",
]

SESSION_DEFAULTS: dict = {
    "messages": [],
    "file_context": "",
    "uploaded_files": [],
    "last_uploaded_signature": "",
    "web_context": "",
    "last_answer": "",
    "last_report": "",
    "auto_log": [],
    "project_context": "",
    "project_path": "",
    "project_summary": "",
    "project_index": [],
    "project_dependencies": [],
    "last_terminal_output": "",
    "web_results": [],
    "last_generated_code": "",
    "last_run_output": "",
    "browser_result": "",
    "browser_trace": [],
    "multi_agent_result": {},
    "last_image_path": "",
    "last_image_prompt": "",
    "last_image_prompt_original": "",
    "last_image_prompt_prepared": "",
    "last_image_log": "",
    "last_image_mode": "turbo",
    "build_loop_history": [],
    "confirm_clear_memory": False,
    "confirm_clear_chat": False,
    "active_mem_profile": "default",
    "ctx_override": None,
    "active_chat_folder": "Общее",
    "active_chat_file": "",
    "active_chat_title": "",
}
