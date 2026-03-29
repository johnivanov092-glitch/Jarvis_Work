import sqlite3
import json
from pathlib import Path

DB_PATH = Path("data/elira_state.db")

# Р”РµС„РѕР»С‚РЅР°СЏ РѕСЂРєРµСЃС‚СЂР°С†РёСЏ вЂ” РєР°РєР°СЏ РјРѕРґРµР»СЊ РЅР° РєР°РєРѕР№ С‚РёРї Р·Р°РґР°С‡Рё
DEFAULT_ROUTE_MAP = {
    "code":     ["qwen2.5-coder:7b", "qwen3:8b", "gemma3:4b"],
    "project":  ["qwen2.5-coder:7b", "qwen3:8b", "gemma3:4b"],
    "research": ["qwen3:8b", "mistral-nemo:latest", "gemma3:4b"],
    "chat":     ["gemma3:4b", "qwen3:8b"],
}

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _ensure_route_map_column():
    """Р”РѕР±Р°РІР»СЏРµС‚ РєРѕР»РѕРЅРєСѓ route_model_map РµСЃР»Рё РµС‘ РЅРµС‚."""
    conn = _connect()
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(settings)").fetchall()]
        if "route_model_map" not in cols:
            conn.execute("ALTER TABLE settings ADD COLUMN route_model_map TEXT DEFAULT '{}'")
            conn.execute("UPDATE settings SET route_model_map = ? WHERE id = 1", (json.dumps(DEFAULT_ROUTE_MAP),))
            conn.commit()
    finally:
        conn.close()

def get_settings():
    _ensure_route_map_column()
    conn = _connect()
    row = conn.execute('SELECT ollama_context, default_model, agent_profile, route_model_map FROM settings WHERE id = 1').fetchone()
    conn.close()
    if not row:
        return {"ollama_context": 8192, "default_model": "gemma3:4b", "agent_profile": "РЈРЅРёРІРµСЂСЃР°Р»СЊРЅС‹Р№", "route_model_map": DEFAULT_ROUTE_MAP}
    result = dict(row)
    # РџР°СЂСЃРёРј JSON РјР°РїРїРёРЅРіР°
    try:
        result["route_model_map"] = json.loads(result.get("route_model_map") or "{}")
    except (json.JSONDecodeError, TypeError):
        result["route_model_map"] = DEFAULT_ROUTE_MAP
    # Р”РѕРїРѕР»РЅСЏРµРј РЅРµРґРѕСЃС‚Р°СЋС‰РёРµ СЂРѕСѓС‚С‹ РґРµС„РѕР»С‚Р°РјРё
    for route, models in DEFAULT_ROUTE_MAP.items():
        if route not in result["route_model_map"]:
            result["route_model_map"][route] = models
    return result

def save_settings(ollama_context, default_model, agent_profile, route_model_map=None):
    _ensure_route_map_column()
    rmap_json = json.dumps(route_model_map if route_model_map else DEFAULT_ROUTE_MAP)
    conn = _connect()
    conn.execute(
        'UPDATE settings SET ollama_context = ?, default_model = ?, agent_profile = ?, route_model_map = ? WHERE id = 1',
        (int(ollama_context), default_model, agent_profile, rmap_json)
    )
    conn.commit()
    row = conn.execute('SELECT ollama_context, default_model, agent_profile, route_model_map FROM settings WHERE id = 1').fetchone()
    conn.close()
    result = dict(row)
    try:
        result["route_model_map"] = json.loads(result.get("route_model_map") or "{}")
    except (json.JSONDecodeError, TypeError):
        result["route_model_map"] = DEFAULT_ROUTE_MAP
    return result

def get_route_model_map() -> dict:
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ С‚РµРєСѓС‰РёР№ РјР°РїРїРёРЅРі СЂРѕСѓС‚РѕРІ в†’ РјРѕРґРµР»РµР№."""
    settings = get_settings()
    return settings.get("route_model_map", DEFAULT_ROUTE_MAP)


