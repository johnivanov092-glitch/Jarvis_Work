"""
plugin_system.py — система плагинов Jarvis.

Плагины = .py файлы в data/plugins/
Каждый плагин должен иметь функцию: def run(args: dict) -> dict

Пример плагина (data/plugins/hello.py):
    def run(args):
        name = args.get("name", "мир")
        return {"ok": True, "message": f"Привет, {name}!"}

API:
  GET  /api/plugins/list    — список плагинов
  POST /api/plugins/run     — запуск плагина
  POST /api/plugins/reload  — перезагрузка
"""
from __future__ import annotations
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PLUGINS_DIR = Path("data/plugins")
PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

_plugins: dict[str, dict] = {}


def load_plugins() -> dict:
    """Загружает все плагины из data/plugins/."""
    global _plugins
    _plugins = {}
    loaded = []
    errors = []

    for py_file in sorted(PLUGINS_DIR.glob("*.py")):
        name = py_file.stem
        if name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"jarvis_plugin_{name}", py_file)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            if not hasattr(mod, "run") or not callable(mod.run):
                errors.append({"name": name, "error": "Нет функции run(args)"})
                continue

            _plugins[name] = {
                "module": mod,
                "path": str(py_file),
                "description": getattr(mod, "DESCRIPTION", ""),
                "author": getattr(mod, "AUTHOR", ""),
                "version": getattr(mod, "VERSION", "1.0"),
            }
            loaded.append(name)
        except Exception as e:
            errors.append({"name": name, "error": str(e)})

    return {"ok": True, "loaded": loaded, "errors": errors, "count": len(loaded)}


def list_plugins() -> dict:
    """Список загруженных плагинов."""
    items = []
    for name, info in _plugins.items():
        items.append({
            "name": name,
            "description": info["description"],
            "author": info["author"],
            "version": info["version"],
            "path": info["path"],
        })
    return {"ok": True, "plugins": items, "count": len(items)}


def run_plugin(name: str, args: dict = None) -> dict:
    """Запускает плагин по имени."""
    if name not in _plugins:
        return {"ok": False, "error": f"Плагин не найден: {name}. Доступные: {list(_plugins.keys())}"}

    try:
        result = _plugins[name]["module"].run(args or {})
        if not isinstance(result, dict):
            result = {"ok": True, "result": result}
        return result
    except Exception as e:
        return {"ok": False, "error": f"Ошибка плагина {name}: {e}"}


def reload_plugins() -> dict:
    """Перезагружает все плагины."""
    # Удаляем старые модули из sys.modules
    for name in list(sys.modules.keys()):
        if name.startswith("jarvis_plugin_"):
            del sys.modules[name]
    return load_plugins()


# Автозагрузка при импорте
load_plugins()


# Создаём пример плагина если папка пустая
_EXAMPLE = PLUGINS_DIR / "example_hello.py"
if not _EXAMPLE.exists() and not list(PLUGINS_DIR.glob("*.py")):
    _EXAMPLE.write_text('''"""Пример плагина Jarvis."""
DESCRIPTION = "Приветствие — пример плагина"
AUTHOR = "Jarvis"
VERSION = "1.0"

def run(args: dict) -> dict:
    name = args.get("name", "мир")
    return {"ok": True, "message": f"Привет, {name}!"}
''', encoding="utf-8")
    load_plugins()
