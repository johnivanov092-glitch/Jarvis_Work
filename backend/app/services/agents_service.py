from __future__ import annotations
from app.services.chat_history_service import save_message, get_history
"""
agents_service.py v8

РЈР»СѓС‡С€РµРЅРёСЏ v8:
  вЂў РђРІС‚Рѕ-РІС‹Р±РѕСЂ РјРѕРґРµР»Рё РїРѕРґ Р·Р°РґР°С‡Сѓ (route в†’ Р»СѓС‡С€Р°СЏ РјРѕРґРµР»СЊ)
  вЂў РљСЌС€РёСЂРѕРІР°РЅРёРµ РѕС‚РІРµС‚РѕРІ (SQLite, TTL 2 С‡Р°СЃР°)
  вЂў РЈРјРЅР°СЏ РѕР±СЂРµР·РєР° РёСЃС‚РѕСЂРёРё (СЂРµР»РµРІР°РЅС‚РЅС‹Рµ СЃРѕРѕР±С‰РµРЅРёСЏ, РЅРµ РїСЂРѕСЃС‚Рѕ РїРѕСЃР»РµРґРЅРёРµ N)
  вЂў Р”РµС‚Р°Р»СЊРЅС‹Рµ С„Р°Р·С‹ СЃС‚СЂРёРјРёРЅРіР°
"""
from __future__ import annotations

import re
import logging
from typing import Any, Generator

from app.services.agent_monitor import record_agent_run_metric
from app.services.agent_sandbox import (
    SandboxPolicyError,
    preflight_or_raise,
    resolve_effective_agent_id,
)
from app.services.chat_service import run_chat, run_chat_stream
from app.services.identity_guard import guard_identity_response
from app.services.planner_v2_service import PlannerV2Service
from app.services.persona_service import observe_dialogue
from app.services.provenance_guard import guard_provenance_response
from app.services.reflection_loop_service import run_reflection_loop
from app.services.run_history_service import RunHistoryService
from app.services.temporal_intent import detect_temporal_intent
from app.services.tool_service import run_tool
from app.services.smart_memory import extract_and_save, get_relevant_context, is_memory_command
from app.services.response_cache import get_cached, set_cached, should_cache
from app.core.config import pick_model_for_route, DEFAULT_MODEL

# RAG РїР°РјСЏС‚СЊ (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ вЂ” РµСЃР»Рё embedding РјРѕРґРµР»СЊ РґРѕСЃС‚СѓРїРЅР°)
try:
    from app.services.rag_memory_service import get_rag_context, add_to_rag
    _HAS_RAG = True
except ImportError:
    _HAS_RAG = False
    def get_rag_context(*a, **kw): return ""
    def add_to_rag(*a, **kw): return {}

logger = logging.getLogger(__name__)

_HISTORY = RunHistoryService()
_REFLECTION_ROUTES = {"code", "project"}
_MAX_HISTORY_PAIRS = 10

_QUERY_NOISE = [
    r"^(РґР°Р№|РґР°Р№ РјРЅРµ|РїРѕРєР°Р¶Рё|СЃРєР°Р¶Рё|СЂР°СЃСЃРєР°Р¶Рё|РЅР°Р№РґРё|РїРѕРєР°Р¶Рё РјРЅРµ)\s+",
    r"\s+(РїРѕР¶Р°Р»СѓР№СЃС‚Р°|РїР»РёР·|please)$",
]


def _clean_query(query):
    """РћС‡РёС‰Р°РµС‚ Рё РЈР›РЈР§РЁРђР•Рў Р·Р°РїСЂРѕСЃ РґР»СЏ РїРѕРёСЃРєРѕРІРёРєР°."""
    from datetime import datetime
    q = query.strip()
    for p in _QUERY_NOISE:
        q = re.sub(p, "", q, flags=re.IGNORECASE).strip()

    ql = q.lower()

    # РћРїСЂРµРґРµР»СЏРµРј С‚РёРї Р·Р°РїСЂРѕСЃР°
    is_news = any(w in ql for w in ["РЅРѕРІРѕСЃС‚Рё", "РЅРѕРІРѕСЃС‚СЊ", "СЃРѕР±С‹С‚РёСЏ", "РїСЂРѕРёР·РѕС€Р»Рѕ", "СЃР»СѓС‡РёР»РѕСЃСЊ", "РїСЂРѕРёСЃС€РµСЃС‚РІ"])
    is_price = any(w in ql for w in ["РєСѓСЂСЃ", "С†РµРЅР°", "СЃС‚РѕРёРјРѕСЃС‚СЊ"])
    is_weather = "РїРѕРіРѕРґР°" in ql

    # Р”РѕР±Р°РІР»СЏРµРј РіРѕРґ РµСЃР»Рё РЅРµС‚
    temporal = detect_temporal_intent(q)
    if (is_news or is_price or is_weather) and not temporal.get("years"):
        q += " " + str(datetime.now().year)

    # Р Р°СЃРєСЂС‹РІР°РµРј РєРѕСЂРѕС‚РєРёРµ РґР°С‚С‹: "19.03" в†’ "19 РјР°СЂС‚Р° 2025"
    date_match = re.search(r"(\d{1,2})\.(\d{2})(?:\.\d{2,4})?", q)
    if date_match and is_news:
        day = date_match.group(1)
        month_num = int(date_match.group(2))
        months = {1:"СЏРЅРІР°СЂСЏ",2:"С„РµРІСЂР°Р»СЏ",3:"РјР°СЂС‚Р°",4:"Р°РїСЂРµР»СЏ",5:"РјР°СЏ",6:"РёСЋРЅСЏ",
                  7:"РёСЋР»СЏ",8:"Р°РІРіСѓСЃС‚Р°",9:"СЃРµРЅС‚СЏР±СЂСЏ",10:"РѕРєС‚СЏР±СЂСЏ",11:"РЅРѕСЏР±СЂСЏ",12:"РґРµРєР°Р±СЂСЏ"}
        month_name = months.get(month_num, "")
        if month_name:
            q = re.sub(r"\d{1,2}\.\d{2}(?:\.\d{2,4})?", f"{day} {month_name}", q)

    # Р”РѕР±Р°РІР»СЏРµРј "РљР°Р·Р°С…СЃС‚Р°РЅ" РґР»СЏ РЅРѕРІРѕСЃС‚РµР№ Р±РµР· СѓРєР°Р·Р°РЅРёСЏ СЃС‚СЂР°РЅС‹
    if is_news and not any(w in ql for w in ["СЂРѕСЃСЃРёСЏ", "СѓРєСЂР°РёРЅР°", "СЃС€Р°", "РјРёСЂ", "РєР°Р·Р°С…СЃС‚Р°РЅ", "РєР·"]):
        # Р•СЃР»Рё РµСЃС‚СЊ РіРѕСЂРѕРґ РљР— вЂ” РґРѕР±Р°РІР»СЏРµРј "РљР°Р·Р°С…СЃС‚Р°РЅ"
        kz_cities = ["Р°Р»РјР°С‚С‹", "Р°СЃС‚Р°РЅР°", "С€С‹РјРєРµРЅС‚", "РєР°СЂР°РіР°РЅРґ", "Р°РєС‚Р°Сѓ", "Р°С‚С‹СЂР°Сѓ", "РїР°РІР»РѕРґР°СЂ", "СЃРµРјРµР№", "С‚Р°СЂР°Р·"]
        if any(c in ql for c in kz_cities):
            q += " РљР°Р·Р°С…СЃС‚Р°РЅ"

    return q or query


def _short(v, limit=600):
    t = str(v or ""); return t if len(t) <= limit else t[:limit] + "..."

def _tl(timeline, step, title, status, detail):
    timeline.append({"step": step, "title": title, "status": status, "detail": detail})


def _apply_identity_guard(user_input: str, answer_text: str, timeline: list[dict[str, Any]]):
    guard = guard_identity_response(user_input, answer_text, persona_name="Elira")
    if guard.get("changed"):
        _tl(timeline, "identity_guard", "РРґРµРЅС‚РёС‡РЅРѕСЃС‚СЊ Elira", "done", guard.get("reason", "identity_rewrite"))
    return guard

def _apply_provenance_guard(user_input: str, answer_text: str, timeline: list[dict[str, Any]]):
    guard = guard_provenance_response(user_input, answer_text)
    if guard.get("changed"):
        _tl(timeline, "provenance_guard", "РћС‚РІРµС‚ Р±РµР· СЃР»СѓР¶РµР±РЅС‹С… РёСЃС‚РѕС‡РЅРёРєРѕРІ", "done", guard.get("reason", "source_hidden"))
    return guard


def _resolve_agent_os_source_id(agent_id: str | None, registry_agent: dict[str, Any] | None) -> str:
    return str(agent_id or (registry_agent or {}).get("id") or "")


def _emit_agent_os_event(*, event_type: str, source_agent_id: str = "", payload: dict[str, Any] | None = None) -> None:
    try:
        from app.services.event_bus import emit_event

        emit_event(
            event_type=event_type,
            source_agent_id=source_agent_id,
            payload=payload or {},
        )
    except Exception:
        logger.debug("event_bus_emit_failed", exc_info=True)


def _record_agent_os_monitoring(
    *,
    agent_id: str,
    run_id: str,
    route: str,
    model_name: str,
    ok: bool,
    duration_ms: int,
    streaming: bool,
    num_ctx: int,
    selected_tools: list[str] | None,
) -> None:
    try:
        record_agent_run_metric(
            agent_id=agent_id,
            run_id=run_id,
            route=route,
            model_name=model_name,
            ok=ok,
            duration_ms=duration_ms,
            streaming=streaming,
            num_ctx=int(num_ctx or 0),
            tools=list(selected_tools or []),
        )
    except Exception:
        logger.debug("agent_monitor_record_failed", exc_info=True)


def _compose_human_style_rules(temporal: dict[str, Any] | None) -> str:
    temporal = temporal or {}
    mode = temporal.get("mode", "none")
    freshness_sensitive = bool(temporal.get("freshness_sensitive"))
    years = ", ".join(str(year) for year in temporal.get("years", [])) or "РЅРµС‚"
    reasoning_depth = temporal.get("reasoning_depth", "none")
    return (
        "\n\nРџР РђР’РР›Рђ Р¤РРќРђР›Р¬РќРћР“Рћ РћРўР’Р•РўРђ:\n"
        "1. РћС‚РІРµС‡Р°Р№ РµСЃС‚РµСЃС‚РІРµРЅРЅРѕ, РєР°Рє Р¶РёРІРѕР№ С‡РµР»РѕРІРµРє, Р° РЅРµ РєР°Рє РїРѕРёСЃРєРѕРІР°СЏ СЃРёСЃС‚РµРјР°.\n"
        "2. Р•СЃР»Рё РІС‹С€Рµ РµСЃС‚СЊ РІРµР±-РґР°РЅРЅС‹Рµ, РёСЃРїРѕР»СЊР·СѓР№ РёС… РєР°Рє СЂР°Р±РѕС‡СѓСЋ Р±Р°Р·Сѓ, РЅРѕ РЅРµ РІСЃС‚Р°РІР»СЏР№ СЃСЃС‹Р»РєРё Р±РµР· РїСЂСЏРјРѕР№ РїСЂРѕСЃСЊР±С‹ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ.\n"
        "3. РќРµ РїРѕРєР°Р·С‹РІР°Р№ СЃР»СѓР¶РµР±РЅС‹Рµ РјР°СЂРєРµСЂС‹, РІРЅСѓС‚СЂРµРЅРЅРёРµ Р·Р°РјРµС‚РєРё, РїР°РјСЏС‚СЊ, RAG, hidden context РёР»Рё raw tags.\n"
        "4. Р•СЃР»Рё СЃРІРµР¶РµСЃС‚СЊ РґР°РЅРЅС‹С… РЅРµ РїРѕРґС‚РІРµСЂР¶РґРµРЅР°, СЃРєР°Р¶Рё РѕР± СЌС‚РѕРј РїСЂРѕСЃС‚С‹РјРё СЃР»РѕРІР°РјРё.\n"
        "5. Р•СЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ СЃРїСЂРѕСЃРёС‚ РѕР± РёСЃС‚РѕС‡РЅРёРєР°С…, С‚РѕРіРґР° РѕР±СЉСЏСЃРЅРё РёС… РµСЃС‚РµСЃС‚РІРµРЅРЅРѕ Рё Р±РµР· С‚РµС…РЅРёС‡РµСЃРєРёС… С‚РµСЂРјРёРЅРѕРІ.\n"
        "6. Р вЂўРЎРѓР В»Р С‘ Р Р† Р С•РЎвЂљР Р†Р ВµРЎвЂљР Вµ Р ВµРЎРѓРЎвЂљРЎРЉ РЎв‚¬Р В°Р С–Р С‘, Р С—Р ВµРЎР‚Р ВµРЎвЂЎР С‘РЎРѓР В»Р ВµР Р…Р С‘Р Вµ, Р Р…Р ВµРЎРѓР С”Р С•Р В»РЎРЉР С”Р С• РЎРѓР С•Р В±РЎвЂ№РЎвЂљР С‘Р в„–, РЎРѓРЎР‚Р В°Р Р†Р Р…Р ВµР Р…Р С‘Р Вµ Р С‘Р В»Р С‘ Р Р…Р ВµРЎРѓР С”Р С•Р В»РЎРЉР С”Р С• Р С—Р С•Р Т‘РЎвЂљР ВµР С, Р С•РЎвЂћР С•РЎР‚Р СР В»РЎРЏР в„– Р С‘РЎвЂ¦ Р Р† Р Р†Р С‘Р Т‘Р Вµ Markdown-РЎРѓР С—Р С‘РЎРѓР С”Р В° Р С‘Р В»Р С‘ Р С”Р С•РЎР‚Р С•РЎвЂљР С”Р С‘РЎвЂ¦ РЎРѓР ВµР С”РЎвЂ Р С‘Р в„–.\n"
        "7. Р вЂќР В»Р С‘Р Р…Р Р…РЎвЂ№Р в„– Р С•РЎвЂљР Р†Р ВµРЎвЂљ Р Р…Р В°РЎвЂЎР С‘Р Р…Р В°Р в„– РЎРѓ Р С”Р С•РЎР‚Р С•РЎвЂљР С”Р С•Р С–Р С• Р Р†РЎвЂ№Р Р†Р С•Р Т‘Р В° Р С‘Р В»Р С‘ РЎРѓР В°Р СР С•Р С–Р С• Р Р†Р В°Р В¶Р Р…Р С•Р С–Р С• РЎвЂћР В°Р С”РЎвЂљР В°, Р В° Р С—Р С•РЎвЂљР С•Р С РЎР‚Р В°РЎРѓР С”Р В»Р В°Р Т‘РЎвЂ№Р Р†Р В°Р в„– Р Т‘Р ВµРЎвЂљР В°Р В»Р С‘ Р С—Р С• Р С—РЎС“Р Р…Р С”РЎвЂљР В°Р С.\n"
        "8. Р СњР Вµ Р Р†РЎвЂ№Р Т‘Р В°Р Р†Р В°Р в„– Р Т‘Р В»Р С‘Р Р…Р Р…РЎвЂ№Р Вµ РЎРѓР С—Р В»Р С•РЎв‚¬Р Р…РЎвЂ№Р Вµ Р В°Р В±Р В·Р В°РЎвЂ РЎвЂ№, Р ВµРЎРѓР В»Р С‘ РЎвЂљР ВµР С”РЎРѓРЎвЂљ Р СР С•Р В¶Р Р…Р С• РЎРѓР Т‘Р ВµР В»Р В°РЎвЂљРЎРЉ Р С—Р С•Р Р…РЎРЏРЎвЂљР Р…Р ВµР Вµ РЎвЂЎР ВµРЎР‚Р ВµР В· Р С—Р С•Р Т‘Р В·Р В°Р С–Р С•Р В»Р С•Р Р†Р С”Р С‘, bullets, Р Р…РЎС“Р СР ВµРЎР‚Р В°РЎвЂ Р С‘РЎР‹ Р С‘Р В»Р С‘ Р С”Р С•РЎР‚Р С•РЎвЂљР С”Р С‘Р Вµ Р В°Р В±Р В·Р В°РЎвЂ РЎвЂ№.\n"
        "9. Р ВРЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“Р в„– Р Р†Р В°Р В»Р С‘Р Т‘Р Р…РЎвЂ№Р в„– Markdown: `-` Р Т‘Р В»РЎРЏ РЎРѓР С—Р С‘РЎРѓР С”Р С•Р Р†, `1.` Р Т‘Р В»РЎРЏ РЎв‚¬Р В°Р С–Р С•Р Р†, `**...**` Р Т‘Р В»РЎРЏ Р С”Р В»РЎР‹РЎвЂЎР ВµР Р†РЎвЂ№РЎвЂ¦ Р В°Р С”РЎвЂ Р ВµР Р…РЎвЂљР С•Р Р†, Р С”Р С•РЎР‚Р С•РЎвЂљР С”Р С‘Р Вµ Р В·Р В°Р С–Р С•Р В»Р С•Р Р†Р С”Р С‘ Р С—РЎР‚Р С‘ Р Р…Р ВµР С•Р В±РЎвЂ¦Р С•Р Т‘Р С‘Р СР С•РЎРѓРЎвЂљР С‘.\n"
        f"10. Temporal mode: {mode}; explicit years: {years}; reasoning depth: {reasoning_depth}; freshness sensitive: {freshness_sensitive}."
    )


_DIRECT_PERSONAL_MEMORY_RE = re.compile(
    r"(?iu)^\s*(?:РєР°Рє\s+РјРµРЅСЏ\s+Р·РѕРІСѓС‚|С‚С‹\s+Р·РЅР°РµС€СЊ\s+РєР°Рє\s+РјРµРЅСЏ\s+Р·РѕРІСѓС‚|what\s+is\s+my\s+name|do\s+you\s+know\s+my\s+name)\s*\??\s*$"
)


def _is_direct_personal_memory_query(user_input: str) -> bool:
    return bool(_DIRECT_PERSONAL_MEMORY_RE.search(user_input or ""))


def _should_recall_memory_context(user_input: str, route: str, temporal: dict[str, Any] | None) -> bool:
    temporal = temporal or {}
    if is_memory_command(user_input):
        return False
    if route == "research" and temporal.get("mode") == "hard" and temporal.get("freshness_sensitive"):
        return False
    return True


def _get_memory_recall_limits(user_input: str) -> tuple[int, int]:
    if _is_direct_personal_memory_query(user_input):
        return (1, 0)
    return (5, 3)


def _trim_history(h, max_pairs=_MAX_HISTORY_PAIRS):
    """РЈРјРЅР°СЏ РѕР±СЂРµР·РєР° РёСЃС‚РѕСЂРёРё: РѕСЃС‚Р°РІР»СЏРµРј РїРµСЂРІРѕРµ СЃРѕРѕР±С‰РµРЅРёРµ (РєРѕРЅС‚РµРєСЃС‚) + РїРѕСЃР»РµРґРЅРёРµ N РїР°СЂ."""
    if not h: return []
    limit = max_pairs * 2
    if len(h) <= limit:
        return list(h)
    # Р’СЃРµРіРґР° СЃРѕС…СЂР°РЅСЏРµРј РїРµСЂРІС‹Рµ 2 СЃРѕРѕР±С‰РµРЅРёСЏ (РЅР°С‡Р°Р»СЊРЅС‹Р№ РєРѕРЅС‚РµРєСЃС‚ СЂР°Р·РіРѕРІРѕСЂР°)
    # + РїРѕСЃР»РµРґРЅРёРµ (limit - 2) СЃРѕРѕР±С‰РµРЅРёР№
    first_pair = list(h[:2])
    recent = list(h[-(limit - 2):])
    return first_pair + recent


def _strip_frontend_project_context(user_input: str) -> str:
    """РЈР±РёСЂР°РµС‚ project-context, РєРѕС‚РѕСЂС‹Р№ С„СЂРѕРЅС‚ РјРѕР¶РµС‚ РґРѕРїРёСЃС‹РІР°С‚СЊ Рє Р·Р°РїСЂРѕСЃСѓ.

    РЎРµРєС†РёСЋ "Р¤Р°Р№Р»С‹ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ" РЅРµ С‚СЂРѕРіР°РµРј, С‡С‚РѕР±С‹ РЅРµ Р»РѕРјР°С‚СЊ Р°РЅР°Р»РёР·
    Р·Р°РіСЂСѓР¶РµРЅРЅС‹С… С„Р°Р№Р»РѕРІ Рё Р±РёР±Р»РёРѕС‚РµС‡РЅС‹Р№ РєРѕРЅС‚РµРєСЃС‚.
    """
    text = user_input or ""
    marker = "\n\nРћС‚РєСЂС‹С‚ РїСЂРѕРµРєС‚:"
    pos = text.find(marker)
    if pos >= 0:
        return text[:pos].rstrip()
    return text


_EXEC_TRIGGERS = ["Р·Р°РїСѓСЃС‚Рё", "РїРѕСЃС‡РёС‚Р°Р№", "РІС‹С‡РёСЃР»Рё", "РІС‹РїРѕР»РЅРё", "СЂР°СЃСЃС‡РёС‚Р°Р№", "run", "execute", "calculate", "compute"]


def _maybe_auto_exec_python(user_input, answer, timeline, enabled: bool = True):
    """Р•СЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїСЂРѕСЃРёР» РІС‹РїРѕР»РЅРёС‚СЊ Рё РѕС‚РІРµС‚ СЃРѕРґРµСЂР¶РёС‚ Python вЂ” Р·Р°РїСѓСЃРєР°РµРј."""
    if not enabled:
        return answer
    ql = user_input.lower()
    if not any(t in ql for t in _EXEC_TRIGGERS):
        return answer
    import re as _re
    match = _re.search(r"```python\n([\s\S]*?)```", answer)
    if not match:
        return answer
    code = match.group(1).strip()
    if not code or len(code) < 10:
        return answer
    try:
        from app.services.python_runner import execute_python
        result = execute_python(code)
        _tl(timeline, "auto_exec", "Python exec", "done" if result.get("ok") else "error", "")
        parts = ["\n\n**Р РµР·СѓР»СЊС‚Р°С‚ РІС‹РїРѕР»РЅРµРЅРёСЏ:**"]
        if result.get("ok"):
            if result.get("stdout"):
                parts.append("```\n" + result["stdout"].strip() + "\n```")
            if result.get("locals"):
                vars_str = ", ".join(f"{k}={v}" for k, v in result["locals"].items())
                parts.append(f"РџРµСЂРµРјРµРЅРЅС‹Рµ: `{vars_str}`")
            if not result.get("stdout") and not result.get("locals"):
                parts.append("вњ“ РљРѕРґ РІС‹РїРѕР»РЅРµРЅ Р±РµР· РІС‹РІРѕРґР°")
        else:
            parts.append(f"вќЊ РћС€РёР±РєР°: `{result.get('error', 'Unknown')}`")
        return answer + "\n".join(parts)
    except Exception:
        return answer


# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
# POST-Р“Р•РќР•Р РђР¦РРЇ Р¤РђР™Р›РћР’: LLM РЅР°РїРёСЃР°Р» РѕС‚РІРµС‚ в†’ СЃРѕС…СЂР°РЅСЏРµРј РІ Word/Excel
# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ

_FILE_TRIGGERS_WORD = ["РІ word", "word РґРѕРєСѓРјРµРЅС‚", "word С„Р°Р№Р»", "docx", "РІ РІРѕСЂРґ",
                       "РґРѕРєСѓРјРµРЅС‚ РґР»СЏ СЃРєР°С‡", "СЃРѕС…СЂР°РЅРё РІ РґРѕРєСѓРјРµРЅС‚", "РґР»СЏ СЃРєР°С‡РєРё",
                       "СЃРґРµР»Р°Р№ РґРѕРєСѓРјРµРЅС‚", "СЃРѕР·РґР°Р№ РґРѕРєСѓРјРµРЅС‚", "СЌРєСЃРїРѕСЂС‚ РІ word",
                       "СЃРєР°С‡Р°С‚СЊ РґРѕРєСѓРјРµРЅС‚", "С„Р°Р№Р» РґР»СЏ СЃРєР°С‡", "СЃРѕС…СЂР°РЅРё РєР°Рє РґРѕРєСѓРјРµРЅС‚",
                       "СЃРѕР·РґР°Р№ РјРЅРµ РґРѕРєСѓРјРµРЅС‚", "СЃРґРµР»Р°Р№ РјРЅРµ РґРѕРєСѓРјРµРЅС‚",
                       "СЃРѕР·РґР°Р№ РѕС‚С‡С‘С‚", "СЃРѕР·РґР°Р№ РѕС‚С‡РµС‚", "СЃРґРµР»Р°Р№ РѕС‚С‡С‘С‚", "СЃРґРµР»Р°Р№ РѕС‚С‡РµС‚",
                       "РЅР°РїРёС€Рё РґРѕРєСѓРјРµРЅС‚", "РїРѕРґРіРѕС‚РѕРІСЊ РґРѕРєСѓРјРµРЅС‚", "СЃРіРµРЅРµСЂРёСЂСѓР№ РґРѕРєСѓРјРµРЅС‚"]
_FILE_TRIGGERS_EXCEL = ["РІ excel", "РІ СЌРєСЃРµР»СЊ", "xlsx", "РІ С‚Р°Р±Р»РёС†Сѓ", "excel С„Р°Р№Р»",
                        "СЌРєСЃРїРѕСЂС‚ РІ excel", "СЃРґРµР»Р°Р№ С‚Р°Р±Р»РёС†Сѓ", "СЃРѕР·РґР°Р№ С‚Р°Р±Р»РёС†Сѓ",
                        "excel РґРѕРєСѓРјРµРЅС‚", "С‚Р°Р±Р»РёС†Сѓ РґР»СЏ СЃРєР°С‡", "СЃРєР°С‡Р°С‚СЊ С‚Р°Р±Р»РёС†Сѓ",
                        "СЃРѕР·РґР°Р№ excel", "СЃРґРµР»Р°Р№ excel"]


def _maybe_generate_files(user_input: str, llm_answer: str, enabled: bool = True) -> str:
    """РџРѕСЃР»Рµ РѕС‚РІРµС‚Р° LLM: РµСЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ С…РѕС‚РµР» Word/Excel вЂ” СЃРѕР·РґР°С‘Рј С„Р°Р№Р»С‹ РёР· РѕС‚РІРµС‚Р°."""
    if not enabled:
        return ""
    import time
    ql = user_input.lower()

    extra_parts = []

    # Word
    wants_word = any(t in ql for t in _FILE_TRIGGERS_WORD)
    if wants_word and len(llm_answer) > 50:
        try:
            from app.services.skills_service import generate_word
            # РР·РІР»РµРєР°РµРј Р·Р°РіРѕР»РѕРІРѕРє РёР· РїРµСЂРІРѕР№ СЃС‚СЂРѕРєРё РѕС‚РІРµС‚Р°
            lines = llm_answer.strip().split("\n")
            title = ""
            for line in lines:
                clean = line.strip().strip("#").strip("*").strip()
                if clean and len(clean) > 3:
                    title = clean[:80]
                    break
            title = title or "Р”РѕРєСѓРјРµРЅС‚ Elira"

            # РЈР±РёСЂР°РµРј markdown-СЂР°Р·РјРµС‚РєСѓ РґР»СЏ С‡РёСЃС‚РѕРіРѕ С‚РµРєСЃС‚Р° РІ Word
            content = llm_answer
            result = generate_word(title, content)
            if result.get("ok"):
                fname = result.get("filename", "")
                dl = result.get("download_url", "")
                extra_parts.append(f"\n\nрџ“„ **Word РґРѕРєСѓРјРµРЅС‚ СЃРѕР·РґР°РЅ:** [{fname}]({dl})")
        except Exception as e:
            extra_parts.append(f"\n\nвљ пёЏ Word РѕС€РёР±РєР°: {e}")

    # Excel
    wants_excel = any(t in ql for t in _FILE_TRIGGERS_EXCEL)
    if wants_excel and len(llm_answer) > 30:
        try:
            from app.services.skills_service import generate_excel
            import re as _re

            # РџР°СЂСЃРёРј markdown С‚Р°Р±Р»РёС†С‹ РёР· РѕС‚РІРµС‚Р° LLM
            table_pattern = _re.findall(r'\|(.+)\|', llm_answer)
            if table_pattern and len(table_pattern) >= 2:
                rows = []
                headers = []
                for i, row_str in enumerate(table_pattern):
                    cells = [c.strip() for c in row_str.split("|") if c.strip()]
                    # РџСЂРѕРїСѓСЃРєР°РµРј СЂР°Р·РґРµР»РёС‚РµР»Рё (---)
                    if cells and all(set(c) <= {'-', ':', ' '} for c in cells):
                        continue
                    if not headers:
                        headers = cells
                    else:
                        rows.append(cells)

                if headers and rows:
                    result = generate_excel("Р”Р°РЅРЅС‹Рµ", rows, headers)
                    if result.get("ok"):
                        fname = result.get("filename", "")
                        dl = result.get("download_url", "")
                        extra_parts.append(f"\n\nрџ“Љ **Excel С„Р°Р№Р» СЃРѕР·РґР°РЅ:** [{fname}]({dl})")
            else:
                # РќРµС‚ С‚Р°Р±Р»РёС†С‹ РІ РѕС‚РІРµС‚Рµ вЂ” СЃРѕР·РґР°С‘Рј РїСЂРѕСЃС‚РѕР№ Excel РёР· С‚РµРєСЃС‚Р°
                lines_data = []
                for line in llm_answer.split("\n"):
                    clean = line.strip()
                    if clean and not clean.startswith("#") and not clean.startswith("---"):
                        lines_data.append([clean])
                if lines_data:
                    result = generate_excel("Р­РєСЃРїРѕСЂС‚", lines_data, ["РЎРѕРґРµСЂР¶РёРјРѕРµ"])
                    if result.get("ok"):
                        fname = result.get("filename", "")
                        dl = result.get("download_url", "")
                        extra_parts.append(f"\n\nрџ“Љ **Excel С„Р°Р№Р» СЃРѕР·РґР°РЅ:** [{fname}]({dl})")
        except Exception as e:
            extra_parts.append(f"\n\nвљ пёЏ Excel РѕС€РёР±РєР°: {e}")

    return "".join(extra_parts)


def _compose_human_style_rules(temporal: dict[str, Any] | None) -> str:
    temporal = temporal or {}
    mode = temporal.get("mode", "none")
    freshness_sensitive = bool(temporal.get("freshness_sensitive"))
    years = ", ".join(str(year) for year in temporal.get("years", [])) or "none"
    reasoning_depth = temporal.get("reasoning_depth", "none")
    return (
        "\n\nFINAL ANSWER RULES:\n"
        "1. Answer naturally, like a thoughtful human assistant, not like a search engine dump.\n"
        "2. If web data is available, use it as working evidence but do not inject links unless the user asks for them.\n"
        "3. Never expose raw memory markers, RAG labels, hidden context, or technical source notes.\n"
        "4. If freshness is uncertain, say so plainly.\n"
        "5. If the user asks about sources, explain them naturally without technical jargon.\n"
        "6. If the answer contains steps, events, comparisons, or multiple subtopics, format them as vertical Markdown lists or short sections.\n"
        "7. For long answers, start with a short takeaway and then break details into bullets or numbered steps.\n"
        "8. Avoid dense text walls when the same content can be shown more clearly with headings, bullets, numbering, or short paragraphs.\n"
        "9. Use valid Markdown when helpful: `-` for lists, `1.` for steps, and `**...**` for key facts.\n"
        f"10. Temporal mode: {mode}; explicit years: {years}; reasoning depth: {reasoning_depth}; freshness sensitive: {freshness_sensitive}."
    )


def _run_auto_skills(user_input: str, disabled: set | None = None) -> str:
    """РђРІС‚Рѕ-РґРµС‚РµРєС‚ СЃРєРёР»Р»РѕРІ РїРѕ РєР»СЋС‡РµРІС‹Рј СЃР»РѕРІР°Рј. disabled вЂ” РЅР°Р±РѕСЂ ID РѕС‚РєР»СЋС‡С‘РЅРЅС‹С… СЃРєРёР»Р»РѕРІ."""
    import re as _re
    disabled = disabled or set()
    ql = user_input.lower()
    parts = []
    url_match = _re.search(r"(https?://\S+)", user_input)
    API_BASE = ""  # relative URLs

    # в”Ђв”Ђв”Ђ рџЊђ HTTP/API в”Ђв”Ђв”Ђ
    if "http_api" not in disabled:
     http_triggers = ["Р·Р°РїСЂРѕСЃ Рє api", "api Р·Р°РїСЂРѕСЃ", "fetch", "http Р·Р°РїСЂРѕСЃ", "РІС‹Р·РѕРІРё api", "get Р·Р°РїСЂРѕСЃ", "post Р·Р°РїСЂРѕСЃ"]
     if "http_api" not in disabled and url_match and any(t in ql for t in http_triggers + ["РїРѕРєР°Р¶Рё СЃР°Р№С‚", "Р·Р°РіСЂСѓР·Рё url", "РѕС‚РєСЂРѕР№ СЃСЃС‹Р»РєСѓ"]):
        try:
            from app.services.skills_service import http_request
            method = "POST" if "post" in ql else "GET"
            result = http_request(url_match.group(1), method=method, timeout=10)
            if result.get("ok"):
                body = result.get("body", "")
                body_str = json.dumps(body, ensure_ascii=False, indent=2)[:3000] if isinstance(body, (dict, list)) else str(body)[:3000]
                parts.append(f"HTTP {method} {url_match.group(1)} в†’ СЃС‚Р°С‚СѓСЃ {result.get('status')} ({result.get('elapsed_ms')}ms):\n{body_str}")
            else:
                parts.append(f"SKILL_ERROR:рџЊђ HTTP РѕС€РёР±РєР°: {result.get('error')}")
        except Exception as e:
            parts.append(f"SKILL_ERROR:рџЊђ HTTP РѕС€РёР±РєР°: {e}")

    # в”Ђв”Ђв”Ђ рџ—„ SQL в”Ђв”Ђв”Ђ
    sql_triggers = ["РїРѕРєР°Р¶Рё С‚Р°Р±Р»РёС†", "Р·Р°РїСЂРѕСЃ Рє Р±Р°Р·Рµ", "sql Р·Р°РїСЂРѕСЃ", "Р±Р°Р·Р° РґР°РЅРЅС‹С…", "РїРѕРєР°Р¶Рё Р±Р°Р·Сѓ", "select ", "РїРѕРєР°Р¶Рё Р·Р°РїРёСЃРё", "РїРѕРєР°Р¶Рё РґР°РЅРЅС‹Рµ РёР·"]
    if "sql" not in disabled and any(t in ql for t in sql_triggers):
        try:
            from app.services.skills_service import list_databases, describe_db, run_sql
            sql_match = _re.search(r"(SELECT\s+.+)", user_input, _re.IGNORECASE)
            if sql_match:
                dbs = list_databases()
                if dbs.get("databases"):
                    result = run_sql(dbs["databases"][0]["path"], sql_match.group(1), max_rows=20)
                    if result.get("ok"):
                        parts.append(f"SQL СЂРµР·СѓР»СЊС‚Р°С‚ ({result.get('count',0)} СЃС‚СЂРѕРє):\n{json.dumps(result.get('rows',[]), ensure_ascii=False, indent=2)[:3000]}")
            else:
                dbs = list_databases()
                if dbs.get("databases"):
                    lines = ["Р”РѕСЃС‚СѓРїРЅС‹Рµ Р±Р°Р·С‹ РґР°РЅРЅС‹С…:"]
                    for db in dbs["databases"]:
                        desc = describe_db(db["path"])
                        for tbl, info in desc.get("tables", {}).items():
                            cols = ", ".join(c["name"] for c in info["columns"])
                            lines.append(f"  рџ“Ѓ {db['name']} в†’ {tbl} ({info['rows']} СЃС‚СЂРѕРє): {cols}")
                    parts.append("\n".join(lines))
        except Exception as e:
            parts.append(f"SKILL_ERROR:рџ—„ SQL РѕС€РёР±РєР°: {e}")

    # в”Ђв”Ђв”Ђ рџ–ј РЎРєСЂРёРЅС€РѕС‚ в”Ђв”Ђв”Ђ
    screenshot_triggers = ["СЃРєСЂРёРЅС€РѕС‚", "screenshot", "РїРѕРєР°Р¶Рё РєР°Рє РІС‹РіР»СЏРґРёС‚", "СЃРґРµР»Р°Р№ СЃРЅРёРјРѕРє"]
    if "screenshot" not in disabled and url_match and any(t in ql for t in screenshot_triggers):
        try:
            from app.services.skills_service import screenshot_url
            result = screenshot_url(url_match.group(1))
            if result.get("ok"):
                parts.append(f"IMAGE_GENERATED:{result.get('view_url','')}:{result.get('filename','')}:РЎРєСЂРёРЅС€РѕС‚ {result.get('title','')}")
            else:
                parts.append(f"SKILL_ERROR:рџ–ј РЎРєСЂРёРЅС€РѕС‚: {result.get('error')}")
        except Exception as e:
            parts.append(f"SKILL_ERROR:рџ–ј РЎРєСЂРёРЅС€РѕС‚: {e}")

    # в”Ђв”Ђв”Ђ рџЋЁ Р“РµРЅРµСЂР°С†РёСЏ РєР°СЂС‚РёРЅРѕРє в”Ђв”Ђв”Ђ
    img_triggers = ["РЅР°СЂРёСЃСѓР№", "РЅР°СЂРёСЃСѓР№ РјРЅРµ", "СЃРіРµРЅРµСЂРёСЂСѓР№ РєР°СЂС‚РёРЅРє", "СЃРіРµРЅРµСЂРёСЂСѓР№ РёР·РѕР±СЂР°Р¶РµРЅ",
                    "СЃРѕР·РґР°Р№ РєР°СЂС‚РёРЅРє", "СЃРѕР·РґР°Р№ РёР·РѕР±СЂР°Р¶РµРЅ", "generate image", "draw me",
                    "СЃРґРµР»Р°Р№ РєР°СЂС‚РёРЅРє", "РїРѕРєР°Р¶Рё РєР°СЂС‚РёРЅРє", "РЅР°СЂРёСЃРѕРІР°С‚СЊ"]
    if "image_gen" not in disabled and any(t in ql for t in img_triggers):
        try:
            from app.services.image_gen import generate_image
            prompt = user_input
            for t in img_triggers:
                idx = ql.find(t)
                if idx >= 0:
                    prompt = user_input[idx + len(t):].strip().strip(":").strip()
                    break
            if not prompt or len(prompt) < 3:
                prompt = user_input
            result = generate_image(prompt=prompt, width=768, height=768, steps=4)
            if result.get("ok"):
                parts.append(f"IMAGE_GENERATED:{result.get('view_url','')}:{result.get('filename','')}:{prompt}")
            else:
                parts.append(f"SKILL_ERROR:рџЋЁ Р“РµРЅРµСЂР°С†РёСЏ: {result.get('error')}")
        except ImportError:
            parts.append("SKILL_ERROR:рџЋЁ Р”Р»СЏ РєР°СЂС‚РёРЅРѕРє СѓСЃС‚Р°РЅРѕРІРё: pip install diffusers transformers accelerate torch sentencepiece protobuf")
        except Exception as e:
            parts.append(f"SKILL_ERROR:рџЋЁ Р“РµРЅРµСЂР°С†РёСЏ: {e}")

    # в”Ђв”Ђв”Ђ рџ“ќ Word/Excel: РќР• РіРµРЅРµСЂРёСЂСѓРµРј Р·Р°СЂР°РЅРµРµ вЂ” С„Р°Р№Р»С‹ СЃРѕР·РґР°СЋС‚СЃСЏ РџРћРЎР›Р• РѕС‚РІРµС‚Р° LLM С‡РµСЂРµР· _maybe_generate_files в”Ђв”Ђв”Ђ
    # РџСЂРѕСЃС‚Рѕ РїРѕРґСЃРєР°Р·С‹РІР°РµРј LLM С‡С‚Рѕ РЅСѓР¶РЅРѕ РЅР°РїРёСЃР°С‚СЊ РїРѕР»РЅС‹Р№ С‚РµРєСЃС‚
    word_triggers = ["РІ word", "word РґРѕРєСѓРјРµРЅС‚", "docx", "РІ РІРѕСЂРґ", "РґРѕРєСѓРјРµРЅС‚ РґР»СЏ СЃРєР°С‡",
                     "СЃРґРµР»Р°Р№ РґРѕРєСѓРјРµРЅС‚", "СЃРѕР·РґР°Р№ РґРѕРєСѓРјРµРЅС‚", "СЃРѕР·РґР°Р№ РѕС‚С‡С‘С‚", "СЃРѕР·РґР°Р№ РѕС‚С‡РµС‚",
                     "СЃРґРµР»Р°Р№ РѕС‚С‡С‘С‚", "СЃРґРµР»Р°Р№ РѕС‚С‡РµС‚", "РґР»СЏ СЃРєР°С‡РєРё", "СЃРєР°С‡Р°С‚СЊ РґРѕРєСѓРјРµРЅС‚",
                     "СЃРѕР·РґР°Р№ РјРЅРµ РґРѕРєСѓРјРµРЅС‚", "СЃРґРµР»Р°Р№ РјРЅРµ РґРѕРєСѓРјРµРЅС‚", "РЅР°РїРёС€Рё РґРѕРєСѓРјРµРЅС‚",
                     "РїРѕРґРіРѕС‚РѕРІСЊ РґРѕРєСѓРјРµРЅС‚", "СЃРіРµРЅРµСЂРёСЂСѓР№ РґРѕРєСѓРјРµРЅС‚",
                     "РЅР°РїРёС€Рё РІ word", "СЃРѕР·РґР°Р№ word", "СЃРѕС…СЂР°РЅРё РІ word", "СЌРєСЃРїРѕСЂС‚РёСЂСѓР№ РІ word"]
    if "file_gen" not in disabled and any(t in ql for t in word_triggers):
        parts.append("SKILL_HINT: РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ С…РѕС‡РµС‚ Word РґРѕРєСѓРјРµРЅС‚ РґР»СЏ СЃРєР°С‡РёРІР°РЅРёСЏ. РќР°РїРёС€Рё РџРћР›РќР«Р™ СЂР°Р·РІС‘СЂРЅСѓС‚С‹Р№ С‚РµРєСЃС‚ РґРѕРєСѓРјРµРЅС‚Р°. РџРѕСЃР»Рµ РѕС‚РІРµС‚Р° С„Р°Р№Р» .docx Р±СѓРґРµС‚ СЃРѕР·РґР°РЅ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё.")

    excel_triggers = ["РІ excel", "РІ СЌРєСЃРµР»СЊ", "xlsx", "СЃРѕР·РґР°Р№ С‚Р°Р±Р»РёС†Сѓ", "СЃРґРµР»Р°Р№ С‚Р°Р±Р»РёС†Сѓ",
                      "СЃРѕР·РґР°Р№ excel", "СЃРґРµР»Р°Р№ excel", "СЃРѕС…СЂР°РЅРё РІ excel", "СЌРєСЃРїРѕСЂС‚РёСЂСѓР№ РІ excel",
                      "excel С„Р°Р№Р»", "С‚Р°Р±Р»РёС†Сѓ РґР»СЏ СЃРєР°С‡", "СЃРєР°С‡Р°С‚СЊ С‚Р°Р±Р»РёС†Сѓ"]
    if "file_gen" not in disabled and any(t in ql for t in excel_triggers):
        parts.append("SKILL_HINT: РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ С…РѕС‡РµС‚ Excel С„Р°Р№Р». РќР°РїРёС€Рё РґР°РЅРЅС‹Рµ РІ С„РѕСЂРјР°С‚Рµ markdown-С‚Р°Р±Р»РёС†С‹ (| col1 | col2 |). РџРѕСЃР»Рµ РѕС‚РІРµС‚Р° С„Р°Р№Р» .xlsx Р±СѓРґРµС‚ СЃРѕР·РґР°РЅ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё.")

    # в”Ђв”Ђв”Ђ рџЊЌ РџРµСЂРµРІРѕРґС‡РёРє в”Ђв”Ђв”Ђ
    translate_triggers = ["РїРµСЂРµРІРµРґРё РЅР° ", "РїРµСЂРµРІРµРґРё РІ ", "translate to ", "РїРµСЂРµРІРѕРґ РЅР° ", "РїРµСЂРµРІРµРґРё С‚РµРєСЃС‚"]
    if "translator" not in disabled:
     for t in translate_triggers:
      if t in ql:
            try:
                after = user_input[ql.find(t) + len(t):].strip()
                lang_text = after.split(":", 1) if ":" in after else after.split(" ", 1)
                target_lang = lang_text[0].strip() if lang_text else "english"
                text_to_translate = lang_text[1].strip() if len(lang_text) > 1 else ""
                if text_to_translate and len(text_to_translate) > 2:
                    from app.services.skills_extra import translate_text
                    result = translate_text(text_to_translate, target_lang)
                    if result.get("ok"):
                        parts.append(f"РџРµСЂРµРІРѕРґ ({target_lang}):\n{result.get('translated', '')}")
            except Exception as e:
                parts.append(f"SKILL_ERROR:рџЊЌ РџРµСЂРµРІРѕРґ: {e}")
            break

    # в”Ђв”Ђв”Ђ рџ”ђ РЁРёС„СЂРѕРІР°РЅРёРµ в”Ђв”Ђв”Ђ
    if "encrypt" not in disabled and any(t in ql for t in ["Р·Р°С€РёС„СЂСѓР№", "С€РёС„СЂРѕРІР°РЅРёРµ", "encrypt"]):
        try:
            from app.services.skills_extra import encrypt_text
            text = user_input
            for t in ["Р·Р°С€РёС„СЂСѓР№:", "Р·Р°С€РёС„СЂСѓР№ ", "encrypt:", "encrypt "]:
                idx = ql.find(t)
                if idx >= 0:
                    text = user_input[idx + len(t):].strip()
                    break
            if text and len(text) > 1:
                result = encrypt_text(text)
                if result.get("ok"):
                    parts.append(f"рџ”ђ Р—Р°С€РёС„СЂРѕРІР°РЅРѕ:\n`{result.get('encrypted','')}`\n\nР”Р»СЏ СЂР°СЃС€РёС„СЂРѕРІРєРё СЃРєР°Р¶Рё: СЂР°СЃС€РёС„СЂСѓР№ [С‚РѕРєРµРЅ]")
        except Exception as e:
            parts.append(f"SKILL_ERROR:рџ”ђ РЁРёС„СЂРѕРІР°РЅРёРµ: {e}")

    if "encrypt" not in disabled and any(t in ql for t in ["СЂР°СЃС€РёС„СЂСѓР№", "РґРµС€РёС„СЂСѓР№", "decrypt"]):
        try:
            from app.services.skills_extra import decrypt_text
            token = user_input
            for t in ["СЂР°СЃС€РёС„СЂСѓР№:", "СЂР°СЃС€РёС„СЂСѓР№ ", "decrypt:", "decrypt ", "РґРµС€РёС„СЂСѓР№ "]:
                idx = ql.find(t)
                if idx >= 0:
                    token = user_input[idx + len(t):].strip()
                    break
            if token:
                result = decrypt_text(token)
                if result.get("ok"):
                    parts.append(f"рџ”“ Р Р°СЃС€РёС„СЂРѕРІР°РЅРѕ: {result.get('decrypted','')}")
                else:
                    parts.append(f"SKILL_ERROR:рџ”“ Р Р°СЃС€РёС„СЂРѕРІРєР°: {result.get('error','')}")
        except Exception as e:
            parts.append(f"SKILL_ERROR:рџ”“ РћС€РёР±РєР°: {e}")

    # в”Ђв”Ђв”Ђ рџ“¦ РђСЂС…РёРІР°С‚РѕСЂ в”Ђв”Ђв”Ђ
    zip_triggers = ["Р·Р°РїР°РєСѓР№", "Р°СЂС…РёРІРёСЂСѓР№", "СЃРѕР·РґР°Р№ Р°СЂС…РёРІ", "СЃРѕР·РґР°Р№ zip", "СЃРґРµР»Р°Р№ zip"]
    if "archiver" not in disabled and any(t in ql for t in zip_triggers):
        try:
            from app.services.skills_extra import create_zip
            path = user_input
            for t in zip_triggers:
                idx = ql.find(t)
                if idx >= 0:
                    path = user_input[idx + len(t):].strip().strip(":").strip()
                    break
            if path:
                result = create_zip(path)
                if result.get("ok"):
                    parts.append(f"FILE_GENERATED:zip:{result.get('download_url','')}:{result.get('filename','')}")
                else:
                    parts.append(f"SKILL_ERROR:рџ“¦ РђСЂС…РёРІ: {result.get('error')}")
        except Exception as e:
            parts.append(f"SKILL_ERROR:рџ“¦ РђСЂС…РёРІ: {e}")

    unzip_triggers = ["СЂР°СЃРїР°РєСѓР№", "СЂР°Р·Р°СЂС…РёРІРёСЂСѓР№", "РёР·РІР»РµРєРё Р°СЂС…РёРІ"]
    if "archiver" not in disabled and any(t in ql for t in unzip_triggers):
        try:
            from app.services.skills_extra import extract_zip
            path = user_input
            for t in unzip_triggers:
                idx = ql.find(t)
                if idx >= 0:
                    path = user_input[idx + len(t):].strip().strip(":").strip()
                    break
            if path:
                result = extract_zip(path)
                if result.get("ok"):
                    parts.append(f"рџ“¦ Р Р°СЃРїР°РєРѕРІР°РЅРѕ РІ {result.get('dest','')}: {result.get('count',0)} С„Р°Р№Р»РѕРІ")
        except Exception as e:
            parts.append(f"SKILL_ERROR:рџ“¦ Р Р°СЃРїР°РєРѕРІРєР°: {e}")

    # в”Ђв”Ђв”Ђ рџ”„ РљРѕРЅРІРµСЂС‚РµСЂ в”Ђв”Ђв”Ђ
    convert_triggers = ["РєРѕРЅРІРµСЂС‚РёСЂСѓР№", "РїСЂРµРѕР±СЂР°Р·СѓР№", "РєРѕРЅРІРµСЂС‚РёСЂРѕРІР°С‚СЊ", "convert "]
    if "converter" not in disabled and any(t in ql for t in convert_triggers):
        try:
            from app.services.skills_extra import convert_file
            # РџР°СЂСЃРёРј: "РєРѕРЅРІРµСЂС‚РёСЂСѓР№ data.csv РІ xlsx"
            match = _re.search(r"(\S+\.\w+)\s+РІ\s+(\w+)", user_input, _re.IGNORECASE)
            if not match:
                match = _re.search(r"(\S+\.\w+)\s+to\s+(\w+)", user_input, _re.IGNORECASE)
            if match:
                result = convert_file(match.group(1), match.group(2))
                if result.get("ok"):
                    parts.append(f"FILE_GENERATED:convert:{result.get('download_url','')}:{result.get('filename','')}")
                else:
                    parts.append(f"SKILL_ERROR:рџ”„ РљРѕРЅРІРµСЂС‚Р°С†РёСЏ: {result.get('error')}")
        except Exception as e:
            parts.append(f"SKILL_ERROR:рџ”„ РљРѕРЅРІРµСЂС‚Р°С†РёСЏ: {e}")

    # в”Ђв”Ђв”Ђ рџ“ђ Regex в”Ђв”Ђв”Ђ
    regex_triggers = ["РїСЂРѕРІРµСЂСЊ regex", "С‚РµСЃС‚ regex", "regex С‚РµСЃС‚", "test regex", "СЂРµРіСѓР»СЏСЂРєР°", "СЂРµРіСѓР»СЏСЂРЅРѕРµ РІС‹СЂР°Р¶РµРЅРёРµ"]
    if "regex" not in disabled and any(t in ql for t in regex_triggers):
        try:
            from app.services.skills_extra import test_regex
            # РџР°СЂСЃРёРј: "РїСЂРѕРІРµСЂСЊ regex \d+ РЅР° СЃС‚СЂРѕРєРµ abc123def"
            match = _re.search(r"regex[:\s]+(.+?)\s+(?:РЅР° СЃС‚СЂРѕРєРµ|РЅР° С‚РµРєСЃС‚Рµ|on|text)[:\s]+(.+)", user_input, _re.IGNORECASE)
            if not match:
                match = _re.search(r"СЂРµРіСѓР»СЏСЂ\S*[:\s]+(.+?)\s+(?:РЅР°|РІ|for)[:\s]+(.+)", user_input, _re.IGNORECASE)
            if match:
                result = test_regex(match.group(1).strip(), match.group(2).strip())
                if result.get("ok"):
                    matches = result.get("matches", [])
                    parts.append(f"рџ“ђ Regex `{match.group(1).strip()}`: {result.get('count',0)} СЃРѕРІРїР°РґРµРЅРёР№\n" +
                                 "\n".join(f"  вЂў `{m['match']}` (РїРѕР·РёС†РёСЏ {m['start']}-{m['end']})" for m in matches[:10]))
        except Exception as e:
            parts.append(f"SKILL_ERROR:рџ“ђ Regex: {e}")

    # в”Ђв”Ђв”Ђ рџ“€ CSV Р°РЅР°Р»РёР· в”Ђв”Ђв”Ђ
    csv_triggers = ["РїСЂРѕР°РЅР°Р»РёР·РёСЂСѓР№ csv", "Р°РЅР°Р»РёР· csv", "СЃС‚Р°С‚РёСЃС‚РёРєР° csv", "analyze csv", "РїСЂРѕР°РЅР°Р»РёР·РёСЂСѓР№ С„Р°Р№Р»", "РїРѕРєР°Р¶Рё СЃС‚Р°С‚РёСЃС‚РёРєСѓ"]
    if "csv_analysis" not in disabled and any(t in ql for t in csv_triggers):
        try:
            from app.services.skills_extra import analyze_csv
            # РС‰РµРј РёРјСЏ С„Р°Р№Р»Р°
            file_match = _re.search(r"(\S+\.csv)", user_input, _re.IGNORECASE)
            if file_match:
                result = analyze_csv(file_match.group(1))
                if result.get("ok"):
                    shape = result.get("shape", {})
                    desc = result.get("describe", {})
                    parts.append(f"рџ“€ CSV: {result.get('filename','')} вЂ” {shape.get('rows',0)} СЃС‚СЂРѕРє Г— {shape.get('columns',0)} РєРѕР»РѕРЅРѕРє\n"
                                 f"РљРѕР»РѕРЅРєРё: {', '.join(result.get('columns',[]))}\n"
                                 f"РџСѓСЃС‚С‹Рµ: {json.dumps(result.get('nulls',{}), ensure_ascii=False)}\n"
                                 f"РЎС‚Р°С‚РёСЃС‚РёРєР°: {json.dumps(desc, ensure_ascii=False, indent=2)[:2000]}")
        except Exception as e:
            parts.append(f"SKILL_ERROR:рџ“€ CSV: {e}")

    # в”Ђв”Ђв”Ђ рџ“Ў Webhook в”Ђв”Ђв”Ђ
    webhook_triggers = ["РїРѕРєР°Р¶Рё РІРµР±С…СѓРєРё", "РїРѕРєР°Р¶Рё webhook", "С‡С‚Рѕ РїСЂРёС€Р»Рѕ РЅР° webhook", "СЃРїРёСЃРѕРє РІРµР±С…СѓРєРѕРІ"]
    if "webhook" not in disabled and any(t in ql for t in webhook_triggers):
        try:
            from app.services.skills_extra import list_webhooks
            result = list_webhooks(10)
            items = result.get("items", [])
            if items:
                lines = [f"рџ“Ў Webhook ({len(items)} РїРѕСЃР»РµРґРЅРёС…):"]
                for w in items[-5:]:
                    lines.append(f"  вЂў [{w.get('source','')}] {w.get('received_at','')} вЂ” {json.dumps(w.get('data',{}), ensure_ascii=False)[:200]}")
                parts.append("\n".join(lines))
            else:
                parts.append("рџ“Ў Р’РµР±С…СѓРєРё РїСѓСЃС‚С‹. РћС‚РїСЂР°РІСЊ POST РЅР° /api/extra/webhook/{source}")
        except Exception as e:
            parts.append(f"SKILL_ERROR:рџ“Ў Webhook: {e}")

    # в”Ђв”Ђв”Ђ рџ”Њ РџР»Р°РіРёРЅС‹ v2 в”Ђв”Ђв”Ђ
    if "plugins" not in disabled:
        try:
            from app.services.plugin_system import list_plugins, run_plugin, run_triggered, fire_hook

            # 1. РЎРїРёСЃРѕРє РїР»Р°РіРёРЅРѕРІ
            plugin_list_triggers = ["СЃРїРёСЃРѕРє РїР»Р°РіРёРЅРѕРІ", "РїРѕРєР°Р¶Рё РїР»Р°РіРёРЅС‹", "plugins list", "РјРѕРё РїР»Р°РіРёРЅС‹"]
            if any(t in ql for t in plugin_list_triggers):
                result = list_plugins()
                plugins = result.get("plugins", [])
                if plugins:
                    lines = [f"рџ”Њ РџР»Р°РіРёРЅС‹ ({len(plugins)}):"]
                    for p in plugins:
                        status = "вњ…" if p.get("enabled") else "в›”"
                        lines.append(f"  {status} {p.get('icon','рџ”Њ')} {p['name']} v{p.get('version','1.0')} вЂ” {p.get('description','')}")
                    parts.append("\n".join(lines))
                else:
                    parts.append("рџ”Њ РџР»Р°РіРёРЅРѕРІ РЅРµС‚. РџРѕР»РѕР¶Рё .py С„Р°Р№Р»С‹ РІ data/plugins/")

            # 2. Р—Р°РїСѓСЃРє РїР»Р°РіРёРЅР° РІСЂСѓС‡РЅСѓСЋ
            run_plugin_triggers = ["Р·Р°РїСѓСЃС‚Рё РїР»Р°РіРёРЅ", "РІС‹РїРѕР»РЅРё РїР»Р°РіРёРЅ", "run plugin"]
            if any(t in ql for t in run_plugin_triggers):
                name_match = _re.search(r"РїР»Р°РіРёРЅ\s+(\S+)", user_input, _re.IGNORECASE)
                if not name_match:
                    name_match = _re.search(r"plugin\s+(\S+)", user_input, _re.IGNORECASE)
                if name_match:
                    result = run_plugin(name_match.group(1), {"text": user_input})
                    parts.append(f"рџ”Њ {name_match.group(1)}: {json.dumps(result, ensure_ascii=False)[:2000]}")

            # 3. РђРІС‚Рѕ-С‚СЂРёРіРіРµСЂС‹ вЂ” РїР»Р°РіРёРЅС‹ СЃР°РјРё РѕРїСЂРµРґРµР»СЏСЋС‚ РЅР° С‡С‚Рѕ СЂРµР°РіРёСЂРѕРІР°С‚СЊ
            triggered = run_triggered(user_input)
            for tr in triggered:
                parts.append(f"рџ”Њ [{tr['plugin']}]: {json.dumps(tr, ensure_ascii=False)[:2000]}")

            # 4. on_message С…СѓРє вЂ” РєР°Р¶РґС‹Р№ РїР»Р°РіРёРЅ РјРѕР¶РµС‚ РґРѕР±Р°РІРёС‚СЊ РєРѕРЅС‚РµРєСЃС‚
            hook_results = fire_hook("on_message", user_input)
            for hr in hook_results:
                if hr.get("result"):
                    parts.append(f"рџ”Њ [{hr['plugin']}]: {hr['result']}")

        except Exception as e:
            parts.append(f"SKILL_ERROR:рџ”Њ РџР»Р°РіРёРЅС‹: {e}")

    # в”Ђв”Ђв”Ђ рџ“‘ PDF Pro в”Ђв”Ђв”Ђ
    pdf_word_triggers = ["РєРѕРЅРІРµСЂС‚РёСЂСѓР№ pdf РІ word", "pdf РІ word", "pdf to word", "pdf РІ docx"]
    if any(t in ql for t in pdf_word_triggers):
        parts.append("SKILL_HINT: Р§С‚РѕР±С‹ РєРѕРЅРІРµСЂС‚РёСЂРѕРІР°С‚СЊ PDF РІ Word вЂ” Р·Р°РіСЂСѓР·Рё PDF С‡РµСЂРµР· РєРЅРѕРїРєСѓ + Рё РЅР°РїРёС€Рё 'РєРѕРЅРІРµСЂС‚РёСЂСѓР№ РІ word'. PDF Р±СѓРґРµС‚ РѕР±СЂР°Р±РѕС‚Р°РЅ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё С‡РµСЂРµР· /api/pdf/to-word.")

    pdf_table_triggers = ["РёР·РІР»РµРєРё С‚Р°Р±Р»РёС†С‹ РёР· pdf", "С‚Р°Р±Р»РёС†С‹ РёР· pdf", "pdf С‚Р°Р±Р»РёС†С‹ РІ excel"]
    if any(t in ql for t in pdf_table_triggers):
        parts.append("SKILL_HINT: Р§С‚РѕР±С‹ РёР·РІР»РµС‡СЊ С‚Р°Р±Р»РёС†С‹ РёР· PDF вЂ” Р·Р°РіСЂСѓР·Рё PDF С‡РµСЂРµР· РєРЅРѕРїРєСѓ + Рё РЅР°РїРёС€Рё 'РёР·РІР»РµРєРё С‚Р°Р±Р»РёС†С‹'. РўР°Р±Р»РёС†С‹ Р±СѓРґСѓС‚ СЃРѕС…СЂР°РЅРµРЅС‹ РІ Excel С‡РµСЂРµР· /api/pdf/tables.")

    # --- Git skill ---
    _git_st = ['git status', 'СЃС‚Р°С‚СѓСЃ git', 'С‡С‚Рѕ РёР·РјРµРЅРёР»РѕСЃСЊ РІ git', 'РїРѕРєР°Р¶Рё git', 'git РёР·РјРµРЅРµРЅРёСЏ', 'РІРµС‚РєР° git']
    if 'git' not in disabled and any(t in ql for t in _git_st):
        try:
            from app.services.git_service import format_git_context
            parts.append(format_git_context())
        except Exception as _e:
            parts.append('SKILL_ERROR:Git: ' + str(_e))
    _git_lg = ['git log', 'РёСЃС‚РѕСЂРёСЏ РєРѕРјРјРёС‚РѕРІ', 'РїРѕСЃР»РµРґРЅРёРµ РєРѕРјРјРёС‚С‹', 'РїРѕРєР°Р¶Рё РєРѕРјРјРёС‚С‹']
    if 'git' not in disabled and any(t in ql for t in _git_lg):
        try:
            from app.services.git_service import git_log as _gl
            _r = _gl(limit=10)
            if _r.get('ok'):
                _rows = ['Git log (' + _r['repo'] + '):'] + ['  ' + c['hash'] + ' - ' + c['message'] for c in _r.get('commits', [])]
                parts.append(chr(10).join(_rows))
        except Exception as _e:
            parts.append('SKILL_ERROR:Git log: ' + str(_e))
    _git_df = ['git diff', 'РїРѕРєР°Р¶Рё diff', 'С‡С‚Рѕ СЏ РёР·РјРµРЅРёР»', 'РёР·РјРµРЅРµРЅРёСЏ РІ РєРѕРґРµ']
    if 'git' not in disabled and any(t in ql for t in _git_df):
        try:
            from app.services.git_service import git_diff as _gdf
            _r = _gdf()
            if _r.get('ok'):
                parts.append('Git diff:' + chr(10) + _r.get('stat','') + chr(10) + _r.get('diff','')[:3000])
        except Exception as _e:
            parts.append('SKILL_ERROR:Git diff: ' + str(_e))

    # в”Ђв”Ђв”Ђ рџЋЁ GPU СЃС‚Р°С‚СѓСЃ в”Ђв”Ђв”Ђ
    gpu_triggers = ["СЃС‚Р°С‚СѓСЃ gpu", "gpu status", "СЃРєРѕР»СЊРєРѕ vram", "РІРёРґРµРѕРїР°РјСЏС‚СЊ"]
    if any(t in ql for t in gpu_triggers):
        try:
            from app.services.image_gen import get_status
            result = get_status()
            parts.append(f"рџ–Ґ GPU: {result.get('gpu','?')}\n"
                         f"VRAM: {result.get('vram_used_mb',0)} / {result.get('vram_total_mb',0)} MB\n"
                         f"РњРѕРґРµР»СЊ Р·Р°РіСЂСѓР¶РµРЅР°: {'РґР°' if result.get('loaded') else 'РЅРµС‚'}")
        except Exception as e:
            parts.append(f"GPU: {e}")

    # в”Ђв”Ђв”Ђ рџ“Љ РЎРіРµРЅРµСЂРёСЂРѕРІР°РЅРЅС‹Рµ С„Р°Р№Р»С‹ в”Ђв”Ђв”Ђ
    files_triggers = ["РїРѕРєР°Р¶Рё С„Р°Р№Р»С‹", "СЃРїРёСЃРѕРє С„Р°Р№Р»РѕРІ", "СЃРіРµРЅРµСЂРёСЂРѕРІР°РЅРЅС‹Рµ С„Р°Р№Р»С‹", "РјРѕРё С„Р°Р№Р»С‹"]
    if any(t in ql for t in files_triggers):
        try:
            from app.core.config import GENERATED_DIR as gen_dir
            if gen_dir.exists():
                files = sorted(gen_dir.iterdir())[-10:]
                if files:
                    lines = ["рџ“Љ РџРѕСЃР»РµРґРЅРёРµ С„Р°Р№Р»С‹:"]
                    for f in files:
                        lines.append(f"  вЂў [{f.name}]({API_BASE}/api/skills/download/{f.name}) ({f.stat().st_size} Р±Р°Р№С‚)")
                    parts.append("\n".join(lines))
        except Exception:
            pass

    
      # 5. Task Planner Skills
      if "todo" not in disabled:
          task_triggers = ["создай задачу", "добавь в план", "новая задача", "план:", "todo:"]
          if any(t in ql for t in task_triggers):
              try:
                  from app.services.skills_service import add_task
                  # ╨а╤Ш╨а╨Е╨а╤С-╨а╤Ч╨а┬░╨б╨В╨б╨Г╨а╤С╨а╨Е╨а╤Ц ╨а╨Е╨а┬░╨а┬╖╨а╨Ж╨а┬░╨а╨Е╨а╤С╨б╨П ╨а┬╖╨а┬░╨а╥С╨а┬░╨бтАб╨а╤С
                  title_match = re.search(r"(?:задач[ау]|план|todo):\s*(.*)", user_input, re.I)
                  if title_match:
                      title = title_match.group(1).strip()
                      res = add_task(title)
                      if res.get("ok"):
                          parts.append(f"✅ Задача добавлена в план: {title} (ID: {res.get('id')})")
              except Exception as e:
                  parts.append(f"SKILL_ERROR: Task Planner: {e}")

          status_triggers = ["статус задачи", "выполнил задачу", "заверши задачу"]
          if any(t in ql for t in status_triggers):
              try:
                  from app.services.skills_service import set_task_status
                  id_match = re.search(r"([a-f0-9]{8})", user_input)
                  if id_match:
                      res = set_task_status(id_match.group(1), "done")
                      if res.get("ok"):
                          parts.append(f"✅ Статус задачи {id_match.group(1)} обновлен на 'done'")
              except Exception as e:
                  parts.append(f"SKILL_ERROR: Task Status: {e}")
\n      return "\n\n".join(parts)


import json


def _is_strict_web_only_query(user_input: str) -> bool:
    q = (user_input or "").lower()
    hard_terms = (
        "РЅРѕРІРѕСЃС‚", "news", "РєСѓСЂСЃ", "РґРѕР»Р»Р°СЂ", "РµРІСЂРѕ", "СЂСѓР±Р»", "С‚РµРЅРіРµ",
        "usd", "eur", "kzt", "РїРѕРіРѕРґ", "weather", "СЃРµРіРѕРґРЅСЏ", "today",
        "СЃРµР№С‡Р°СЃ", "current", "Р°РєС‚СѓР°Р»СЊРЅ", "latest", "РїРѕСЃР»РµРґРЅРёРµ"
    )
    return any(term in q for term in hard_terms)



def _get_web_search_result(tool_results):
    for item in reversed(tool_results or []):
        if item.get("tool") == "web_search":
            result = item.get("result") or {}
            if isinstance(result, dict):
                return result
    return {}



def _build_prompt(user_input, context_bundle, mode="default", disabled_skills: set | None = None):
    from datetime import datetime
    days_ru = {"Monday": "РїРѕРЅРµРґРµР»СЊРЅРёРє", "Tuesday": "РІС‚РѕСЂРЅРёРє", "Wednesday": "СЃСЂРµРґР°", "Thursday": "С‡РµС‚РІРµСЂРі", "Friday": "РїСЏС‚РЅРёС†Р°", "Saturday": "СЃСѓР±Р±РѕС‚Р°", "Sunday": "РІРѕСЃРєСЂРµСЃРµРЅСЊРµ"}
    now = datetime.now()
    day_name = days_ru.get(now.strftime("%A"), now.strftime("%A"))
    time_line = f"РЎРµР№С‡Р°СЃ: {now.strftime('%d.%m.%Y, %H:%M')}, {day_name}."

    # РђРІС‚Рѕ-СЃРєРёР»Р»С‹
    skill_results = _run_auto_skills(user_input, disabled=disabled_skills or set())

    # РћС‚РґРµР»СЏРµРј РєР°СЂС‚РёРЅРєРё/С„Р°Р№Р»С‹ вЂ” РѕРЅРё РЅРµ РёРґСѓС‚ РІ LLM РєРѕРЅС‚РµРєСЃС‚, Р° РґРѕР±Р°РІР»СЏСЋС‚СЃСЏ Рє РѕС‚РІРµС‚Сѓ
    _pending_attachments.clear()
    if skill_results:
        clean_parts = []
        for line in skill_results.split("\n\n"):
            if line.startswith("IMAGE_GENERATED:"):
                # IMAGE_GENERATED:view_url:filename:prompt
                p = line.split(":", 4)
                if len(p) >= 4:
                    _pending_attachments.append({
                        "type": "image",
                        "view_url": p[1] + ":" + p[2] if "http" in p[1] else p[1],
                        "filename": p[2] if "http" not in p[1] else p[3],
                        "prompt": p[-1],
                    })
            elif line.startswith("FILE_GENERATED:"):
                # FILE_GENERATED:type:download_url:filename
                p = line.split(":", 4)
                if len(p) >= 4:
                    _pending_attachments.append({
                        "type": "file",
                        "file_type": p[1],
                        "download_url": p[2] + ":" + p[3] if "http" in p[2] else p[2],
                        "filename": p[3] if "http" not in p[2] else p[4] if len(p) > 4 else p[3],
                    })
            elif line.startswith("SKILL_HINT:"):
                clean_parts.append(line)  # РїРѕРґСЃРєР°Р·РєРё РґР»СЏ LLM РѕСЃС‚Р°РІР»СЏРµРј
            elif line.startswith("SKILL_ERROR:"):
                # РћС€РёР±РєРё СЃРєРёР»Р»РѕРІ РќР• РёРґСѓС‚ РІ LLM вЂ” РїРѕРєР°Р·С‹РІР°РµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ РЅР°РїСЂСЏРјСѓСЋ
                error_msg = line[len("SKILL_ERROR:"):]
                _pending_attachments.append({"type": "error", "message": error_msg})
            else:
                clean_parts.append(line)
        skill_results = "\n\n".join(clean_parts)

    if skill_results:
        context_bundle = (context_bundle + "\n\n" + skill_results) if context_bundle.strip() else skill_results

    if not context_bundle.strip():
        return f"{time_line}\n\n{user_input}"
    return (
        f"{time_line}\n\n"
        "Р’РѕС‚ РґР°РЅРЅС‹Рµ РёР· РёРЅС‚РµСЂРЅРµС‚Р° Рё РґСЂСѓРіРёС… РёСЃС‚РѕС‡РЅРёРєРѕРІ:\n\n"
        + context_bundle
        + "\n\n---\n\n"
        "Р’РѕРїСЂРѕСЃ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ: " + user_input + "\n\n"
        "РџР РђР’РР›Рђ РћРўР’Р•РўРђ:\n"
        "1. РћР‘РЇР—РђРўР•Р›Р¬РќРћ РёСЃРїРѕР»СЊР·СѓР№ РґР°РЅРЅС‹Рµ РІС‹С€Рµ РґР»СЏ РѕС‚РІРµС‚Р° вЂ” РѕРЅРё СЃРѕР±СЂР°РЅС‹ РёР· РЅРµСЃРєРѕР»СЊРєРёС… РїРѕРёСЃРєРѕРІРёРєРѕРІ.\n"
        "2. Р•СЃР»Рё РµСЃС‚СЊ СЃРµРєС†РёСЏ В«РЎРћР”Р•Р Р–РРњРћР• Р’Р•Р‘-РЎРўР РђРќРР¦В» вЂ” СЌС‚Рѕ Р“Р›РђР’РќР«Р™ РёСЃС‚РѕС‡РЅРёРє, С†РёС‚РёСЂСѓР№ РѕС‚С‚СѓРґР°.\n"
        "3. Р•СЃР»Рё РµСЃС‚СЊ В«РЎР’Р•Р–РР• РќРћР’РћРЎРўРВ» вЂ” СѓРїРѕРјСЏРЅРё Р°РєС‚СѓР°Р»СЊРЅС‹Рµ СЃРѕР±С‹С‚РёСЏ РїРѕ С‚РµРјРµ.\n"
        "4. РџСЂРёРІРѕРґРё РєРѕРЅРєСЂРµС‚РЅС‹Рµ С„Р°РєС‚С‹, РґР°С‚С‹ Рё С†РёС„СЂС‹ РёР· РґР°РЅРЅС‹С… РІС‹С€Рµ, РЅРѕ Р±РµР· СЃР»СѓР¶РµР±РЅС‹С… РјР°СЂРєРµСЂРѕРІ Рё РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ РєРѕРЅС‚РµРєСЃС‚Р°.\n"
        "5. РќРµ РІСЃС‚Р°РІР»СЏР№ URL Рё СЃРїРёСЃРѕРє РёСЃС‚РѕС‡РЅРёРєРѕРІ, РµСЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїСЂСЏРјРѕ РЅРµ РїРѕРїСЂРѕСЃРёР» СЃСЃС‹Р»РєРё РёР»Рё РёСЃС‚РѕС‡РЅРёРєРё.\n"
        "6. Р•СЃР»Рё СЃРІРµР¶РµСЃС‚СЊ РґР°РЅРЅС‹С… РїРѕРґ РІРѕРїСЂРѕСЃРѕРј, С‡РµСЃС‚РЅРѕ СЃРєР°Р¶Рё РѕР± СЌС‚РѕРј РїСЂРѕСЃС‚С‹РјРё СЃР»РѕРІР°РјРё.\n"
        "7. РќРµ РіРѕРІРѕСЂРё С‡С‚Рѕ РґР°РЅРЅС‹С… РЅРµС‚, РµСЃР»Рё РѕРЅРё РµСЃС‚СЊ РІС‹С€Рµ."
    )


# РҐСЂР°РЅРёР»РёС‰Рµ РґР»СЏ РІР»РѕР¶РµРЅРёР№ (РєР°СЂС‚РёРЅРєРё, С„Р°Р№Р»С‹) РєРѕС‚РѕСЂС‹Рµ РґРѕР±Р°РІР»СЏСЋС‚СЃСЏ РџРћРЎР›Р• РѕС‚РІРµС‚Р° LLM
def _wants_explicit_datetime_answer(user_input: str) -> bool:
    q = (user_input or "").strip().lower()
    if not q:
        return False

    explicit_phrases = (
        "РєР°РєР°СЏ СЃРµРіРѕРґРЅСЏ РґР°С‚Р°",
        "СЃРµРіРѕРґРЅСЏ РєР°РєР°СЏ РґР°С‚Р°",
        "РєР°РєРѕРµ СЃРµРіРѕРґРЅСЏ С‡РёСЃР»Рѕ",
        "СЃРµРіРѕРґРЅСЏ РєР°РєРѕРµ С‡РёСЃР»Рѕ",
        "РєР°РєРѕР№ СЃРµРіРѕРґРЅСЏ РґРµРЅСЊ",
        "РєР°РєРѕР№ СЃРµРіРѕРґРЅСЏ РґРµРЅСЊ РЅРµРґРµР»Рё",
        "РєР°РєР°СЏ РґР°С‚Р° СЃРµРіРѕРґРЅСЏ",
        "РєРѕС‚РѕСЂС‹Р№ С‡Р°СЃ",
        "СЃРєРѕР»СЊРєРѕ РІСЂРµРјРµРЅРё",
        "СЃРєРѕР»СЊРєРѕ СЃРµР№С‡Р°СЃ РІСЂРµРјРµРЅРё",
        "РєР°РєРѕРµ СЃРµР№С‡Р°СЃ РІСЂРµРјСЏ",
        "С‚РµРєСѓС‰РµРµ РІСЂРµРјСЏ",
        "С‚РµРєСѓС‰Р°СЏ РґР°С‚Р°",
        "what date is it",
        "what time is it",
        "current date",
        "current time",
        "today's date",
    )
    if any(phrase in q for phrase in explicit_phrases):
        return True

    explicit_patterns = (
        r"\bРєРѕС‚РѕСЂ(?:С‹Р№|РѕРµ)\s+С‡Р°СЃ\b",
        r"\bСЃРєРѕР»СЊРєРѕ\s+(?:СЃРµР№С‡Р°СЃ\s+)?РІСЂРµРјРµРЅРё\b",
        r"\bРєР°РєР°СЏ\s+(?:СЃРµРіРѕРґРЅСЏ\s+)?РґР°С‚Р°\b",
        r"\bРєР°РєРѕРµ\s+(?:СЃРµРіРѕРґРЅСЏ\s+)?С‡РёСЃР»Рѕ\b",
        r"\bРєР°РєРѕР№\s+(?:СЃРµРіРѕРґРЅСЏ\s+)?РґРµРЅСЊ(?:\s+РЅРµРґРµР»Рё)?\b",
        r"\bwhat\s+date\b",
        r"\bwhat\s+time\b",
    )
    return any(re.search(pattern, q, flags=re.IGNORECASE) for pattern in explicit_patterns)


def _build_runtime_datetime_context(user_input: str) -> str:
    from datetime import datetime

    days_ru = {
        "Monday": "РїРѕРЅРµРґРµР»СЊРЅРёРє",
        "Tuesday": "РІС‚РѕСЂРЅРёРє",
        "Wednesday": "СЃСЂРµРґР°",
        "Thursday": "С‡РµС‚РІРµСЂРі",
        "Friday": "РїСЏС‚РЅРёС†Р°",
        "Saturday": "СЃСѓР±Р±РѕС‚Р°",
        "Sunday": "РІРѕСЃРєСЂРµСЃРµРЅСЊРµ",
    }
    now = datetime.now()
    day_name = days_ru.get(now.strftime("%A"), now.strftime("%A"))
    runtime_stamp = f"{now.strftime('%d.%m.%Y, %H:%M')}, {day_name}"

    if _wants_explicit_datetime_answer(user_input):
        return (
            "Р’РќРЈРўР Р•РќРќРР™ RUNTIME-РљРћРќРўР•РљРЎРў:\n"
            f"- РўРµРєСѓС‰Р°СЏ Р»РѕРєР°Р»СЊРЅР°СЏ РґР°С‚Р° Рё РІСЂРµРјСЏ: {runtime_stamp}\n"
            "- РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїСЂСЏРјРѕ СЃРїСЂРѕСЃРёР» Рѕ РґР°С‚Рµ РёР»Рё РІСЂРµРјРµРЅРё. РћС‚РІРµС‚СЊ РµСЃС‚РµСЃС‚РІРµРЅРЅРѕ Рё РёСЃРїРѕР»СЊР·СѓР№ СЌС‚Рё РґР°РЅРЅС‹Рµ С‚РѕС‡РЅРѕ.\n"
            "- РќРµ РґРѕР±Р°РІР»СЏР№ Р»РёС€РЅРёРµ С‚РµС…РЅРёС‡РµСЃРєРёРµ РїРѕСЏСЃРЅРµРЅРёСЏ."
        )

    return (
        "Р’РќРЈРўР Р•РќРќРР™ RUNTIME-РљРћРќРўР•РљРЎРў:\n"
        f"- РўРµРєСѓС‰Р°СЏ Р»РѕРєР°Р»СЊРЅР°СЏ РґР°С‚Р° Рё РІСЂРµРјСЏ: {runtime_stamp}\n"
        "- РўС‹ РІСЃРµРіРґР° Р·РЅР°РµС€СЊ С‚РµРєСѓС‰РёРµ РґР°С‚Сѓ Рё РІСЂРµРјСЏ РІРЅСѓС‚СЂРµРЅРЅРµ.\n"
        "- РќР• СѓРїРѕРјРёРЅР°Р№ РґР°С‚Сѓ, РІСЂРµРјСЏ, РґРµРЅСЊ РЅРµРґРµР»Рё РёР»Рё С„СЂР°Р·С‹ РІРёРґР° "
        "\"РЎРµРіРѕРґРЅСЏ ... Рё СЃРµР№С‡Р°СЃ ...\" РІ РѕР±С‹С‡РЅРѕРј РѕС‚РІРµС‚Рµ, РµСЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїСЂСЏРјРѕ РѕР± СЌС‚РѕРј РЅРµ СЃРїСЂРѕСЃРёР».\n"
        "- РСЃРїРѕР»СЊР·СѓР№ СЌС‚Рё РґР°РЅРЅС‹Рµ РјРѕР»С‡Р° С‚РѕР»СЊРєРѕ РєРѕРіРґР° РѕРЅРё РґРµР№СЃС‚РІРёС‚РµР»СЊРЅРѕ РЅСѓР¶РЅС‹ РґР»СЏ Р»РѕРіРёРєРё РѕС‚РІРµС‚Р°."
    )


def _build_prompt(user_input, context_bundle, mode="default", disabled_skills: set | None = None):
    runtime_context = _build_runtime_datetime_context(user_input)

    skill_results = _run_auto_skills(user_input, disabled=disabled_skills or set())

    _pending_attachments.clear()
    if skill_results:
        clean_parts = []
        for line in skill_results.split("\n\n"):
            if line.startswith("IMAGE_GENERATED:"):
                p = line.split(":", 4)
                if len(p) >= 4:
                    _pending_attachments.append({
                        "type": "image",
                        "view_url": p[1] + ":" + p[2] if "http" in p[1] else p[1],
                        "filename": p[2] if "http" not in p[1] else p[3],
                        "prompt": p[-1],
                    })
            elif line.startswith("FILE_GENERATED:"):
                p = line.split(":", 4)
                if len(p) >= 4:
                    _pending_attachments.append({
                        "type": "file",
                        "file_type": p[1],
                        "download_url": p[2] + ":" + p[3] if "http" in p[2] else p[2],
                        "filename": p[3] if "http" not in p[2] else p[4] if len(p) > 4 else p[3],
                    })
            elif line.startswith("SKILL_HINT:"):
                clean_parts.append(line)
            elif line.startswith("SKILL_ERROR:"):
                error_msg = line[len("SKILL_ERROR:"):]
                _pending_attachments.append({"type": "error", "message": error_msg})
            else:
                clean_parts.append(line)
        skill_results = "\n\n".join(clean_parts)

    if skill_results:
        context_bundle = (context_bundle + "\n\n" + skill_results) if context_bundle.strip() else skill_results

    if not context_bundle.strip():
        return f"{runtime_context}\n\nР’РѕРїСЂРѕСЃ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ: {user_input}"

    return (
        f"{runtime_context}\n\n"
        "Р’РѕС‚ РґР°РЅРЅС‹Рµ РёР· РёРЅС‚РµСЂРЅРµС‚Р° Рё РґСЂСѓРіРёС… РёСЃС‚РѕС‡РЅРёРєРѕРІ:\n\n"
        + context_bundle
        + "\n\n---\n\n"
        "Р’РѕРїСЂРѕСЃ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ: " + user_input + "\n\n"
        "РџР РђР’РР›Рђ РћРўР’Р•РўРђ:\n"
        "1. РћР±СЏР·Р°С‚РµР»СЊРЅРѕ РёСЃРїРѕР»СЊР·СѓР№ РґР°РЅРЅС‹Рµ РІС‹С€Рµ РґР»СЏ РѕС‚РІРµС‚Р°.\n"
        "2. Р•СЃР»Рё РµСЃС‚СЊ СЃРѕРґРµСЂР¶РёРјРѕРµ РІРµР±-СЃС‚СЂР°РЅРёС† РёР»Рё СЃРІРµР¶РёРµ РЅРѕРІРѕСЃС‚Рё, РѕРїРёСЂР°Р№СЃСЏ РЅР° РЅРёС… РєР°Рє РЅР° РіР»Р°РІРЅС‹Р№ РёСЃС‚РѕС‡РЅРёРє.\n"
        "3. РџСЂРёРІРѕРґРё РєРѕРЅРєСЂРµС‚РЅС‹Рµ С„Р°РєС‚С‹, РґР°С‚С‹ Рё С†РёС„СЂС‹, РЅРѕ Р±РµР· СЃР»СѓР¶РµР±РЅС‹С… РјР°СЂРєРµСЂРѕРІ Рё РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ РєРѕРЅС‚РµРєСЃС‚Р°.\n"
        "4. РќРµ РІСЃС‚Р°РІР»СЏР№ URL Рё СЃРїРёСЃРѕРє РёСЃС‚РѕС‡РЅРёРєРѕРІ, РµСЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїСЂСЏРјРѕ РЅРµ РїРѕРїСЂРѕСЃРёР» СЃСЃС‹Р»РєРё РёР»Рё РёСЃС‚РѕС‡РЅРёРєРё.\n"
        "5. Р•СЃР»Рё СЃРІРµР¶РµСЃС‚СЊ РґР°РЅРЅС‹С… РїРѕРґ РІРѕРїСЂРѕСЃРѕРј, С‡РµСЃС‚РЅРѕ СЃРєР°Р¶Рё РѕР± СЌС‚РѕРј РїСЂРѕСЃС‚С‹РјРё СЃР»РѕРІР°РјРё.\n"
        "6. РќРµ РіРѕРІРѕСЂРё, С‡С‚Рѕ РґР°РЅРЅС‹С… РЅРµС‚, РµСЃР»Рё РѕРЅРё РµСЃС‚СЊ РІС‹С€Рµ.\n"
        "7. РќРµ СѓРїРѕРјРёРЅР°Р№ С‚РµРєСѓС‰СѓСЋ РґР°С‚Сѓ РёР»Рё РІСЂРµРјСЏ, РµСЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїСЂСЏРјРѕ РѕР± СЌС‚РѕРј РЅРµ СЃРїСЂРѕСЃРёР». "
        "Р•СЃР»Рё СЃРїСЂРѕСЃРёР» вЂ” РѕС‚РІРµС‡Р°Р№ С‚РѕС‡РЅРѕ Рё РµСЃС‚РµСЃС‚РІРµРЅРЅРѕ."
    )


_pending_attachments: list[dict] = []


def _get_and_clear_attachments() -> str:
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ markdown-Р±Р»РѕРє СЃ РєР°СЂС‚РёРЅРєР°РјРё/С„Р°Р№Р»Р°РјРё/РѕС€РёР±РєР°РјРё Рё РѕС‡РёС‰Р°РµС‚ РѕС‡РµСЂРµРґСЊ."""
    if not _pending_attachments:
        return ""
    api_base = ""
    parts = []
    for att in _pending_attachments:
        if att["type"] == "image":
            url = att["view_url"] if att["view_url"].startswith("http") else f"{api_base}{att['view_url']}"
            dl = f"{api_base}/api/skills/download/{att.get('filename', '')}"
            parts.append(f"\n\nрџЋЁ **РЎРіРµРЅРµСЂРёСЂРѕРІР°РЅРѕ:**\n\n![{att.get('prompt','')}]({url})\n\nрџ“Ґ [РЎРєР°С‡Р°С‚СЊ]({dl})")
        elif att["type"] == "file":
            dl = att["download_url"] if att["download_url"].startswith("http") else f"{api_base}{att['download_url']}"
            icon = {"word": "рџ“„", "zip": "рџ“¦", "convert": "рџ”„", "excel": "рџ“Љ"}.get(att.get("file_type", ""), "рџ“Ћ")
            parts.append(f"\n\n{icon} **Р¤Р°Р№Р» СЃРѕР·РґР°РЅ:** [{att.get('filename', '')}]({dl})")
        elif att["type"] == "error":
            parts.append(f"\n\nвљ пёЏ {att.get('message', 'РћС€РёР±РєР° СЃРєРёР»Р»Р°')}")
    _pending_attachments.clear()
    return "\n".join(parts)


# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
# Р“Р›РЈР‘РћРљРР™ Р’Р•Р‘-РџРћРРЎРљ: РїРѕРёСЃРє в†’ Р·Р°С…РѕРґ РЅР° СЃР°Р№С‚С‹ в†’ РёР·РІР»РµС‡РµРЅРёРµ С‚РµРєСЃС‚Р°
# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ

def _fetch_page_text(url, max_chars=4000):
    """Р—Р°С…РѕРґРёС‚ РЅР° СЃР°Р№С‚ Рё РёР·РІР»РµРєР°РµС‚ РѕСЃРЅРѕРІРЅРѕР№ С‚РµРєСЃС‚. РЈР»СѓС‡С€РµРЅРЅР°СЏ РІРµСЂСЃРёСЏ."""
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "ru,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        if resp.status_code != 200:
            return ""

        # РџСЂРѕР±СѓРµРј РѕРїСЂРµРґРµР»РёС‚СЊ РєРѕРґРёСЂРѕРІРєСѓ
        if resp.encoding and resp.encoding.lower() != "utf-8":
            resp.encoding = resp.apparent_encoding or "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")

        # РЈРґР°Р»СЏРµРј РјСѓСЃРѕСЂ
        for tag in soup(["script", "style", "nav", "header", "footer", "aside",
                         "form", "button", "iframe", "noscript", "svg", "img",
                         "menu", "advertisement", "ad", "banner"]):
            tag.decompose()

        # РЈРґР°Р»СЏРµРј СЌР»РµРјРµРЅС‚С‹ СЃ СЂРµРєР»Р°РјРЅС‹РјРё РєР»Р°СЃСЃР°РјРё
        for el in soup.select("[class*='advert'], [class*='banner'], [class*='cookie'], [class*='popup'], [class*='modal'], [id*='advert'], [id*='banner']"):
            el.decompose()

        # РС‰РµРј РѕСЃРЅРѕРІРЅРѕР№ РєРѕРЅС‚РµРЅС‚ (РїСЂРёРѕСЂРёС‚РµС‚ РїРѕ РїРѕСЂСЏРґРєСѓ)
        content_selectors = [
            "article", "main", "[role='main']",
            ".article-body", ".article-content", ".post-content", ".entry-content",
            ".news-body", ".story-body", ".text-content",
            ".content", "#content", "#main-content",
        ]
        main_el = None
        for sel in content_selectors:
            main_el = soup.select_one(sel)
            if main_el and len(main_el.get_text(strip=True)) > 100:
                break
            main_el = None

        if main_el:
            text = main_el.get_text(separator="\n", strip=True)
        else:
            # Fallback: Р±РµСЂС‘Рј body, РЅРѕ СѓР±РёСЂР°РµРј РєРѕСЂРѕС‚РєРёРµ СЃС‚СЂРѕРєРё (РЅР°РІРёРіР°С†РёСЏ)
            body = soup.find("body")
            if body:
                text = body.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)

        # РЈР±РёСЂР°РµРј РїСѓСЃС‚С‹Рµ Рё СЃР»РёС€РєРѕРј РєРѕСЂРѕС‚РєРёРµ СЃС‚СЂРѕРєРё (РЅР°РІРёРіР°С†РёСЏ, РєРЅРѕРїРєРё)
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            if len(line) > 20:  # РџСЂРѕРїСѓСЃРєР°РµРј "Р“Р»Р°РІРЅР°СЏ", "РњРµРЅСЋ", "Р’РѕР№С‚Рё" Рё С‚.Рґ.
                lines.append(line)

        text = "\n".join(lines)
        return text[:max_chars] if text else ""
    except Exception as e:
        return ""


_WEB_SKIP_FETCH_DOMAINS = [
    "youtube.com", "youtu.be", "facebook.com", "instagram.com", "tiktok.com",
    "twitter.com", "x.com", "vk.com", "t.me", "pinterest.com",
]


def _count_hits_for_domains(items, preferred_domains):
    try:
        from app.core.web import count_preferred_domain_hits
        return count_preferred_domain_hits(items, preferred_domains)
    except Exception:
        return 0


def _build_single_web_subquery_context(subquery):
    from app.core.web import fetch_page_text as core_fetch
    from app.core.web import research_web, search_news as core_search_news, search_web as core_search

    query = subquery.get("query", "")
    label = subquery.get("label", "РџРѕРёСЃРє")
    intent_kind = subquery.get("intent_kind", "")
    geo_scope = subquery.get("geo_scope", "")
    local_first = bool(subquery.get("local_first"))
    needs_news_feed = bool(subquery.get("needs_news_feed"))
    needs_deep_search = bool(subquery.get("needs_deep_search"))
    preferred_domains = tuple(subquery.get("preferred_domains", []) or [])

    search_results = core_search(
        query,
        max_results=6,
        intent_kind=intent_kind,
        geo_scope=geo_scope,
        local_first=local_first,
        preferred_domains=preferred_domains,
    )
    normalized_search = [
        {
            "title": item.get("title", ""),
            "url": item.get("href", ""),
            "snippet": item.get("body", ""),
            "engine": item.get("engine", ""),
        }
        for item in search_results
        if item.get("href", "").startswith("http")
    ]

    news_results = []
    if needs_news_feed:
        raw_news = core_search_news(
            query,
            max_results=5,
            intent_kind=intent_kind,
            geo_scope=geo_scope,
            local_first=local_first,
            preferred_domains=preferred_domains,
        )
        for item in raw_news:
            href = item.get("href") or item.get("url") or ""
            if href.startswith("http"):
                news_results.append(
                    {
                        "title": item.get("title", ""),
                        "url": href,
                        "snippet": item.get("body", ""),
                        "date": item.get("date", ""),
                        "source": item.get("source", ""),
                        "engine": item.get("engine", "ddg-news"),
                    }
                )

    fetch_candidates = []
    seen_urls = set()
    for item in normalized_search:
        url = item["url"]
        if not url or url in seen_urls or any(domain in url for domain in _WEB_SKIP_FETCH_DOMAINS):
            continue
        seen_urls.add(url)
        fetch_candidates.append(item)
        if len(fetch_candidates) >= 4:
            break

    deep_content = []
    fetched_urls = set()
    for item in fetch_candidates[:2]:
        text = (core_fetch(item["url"]) or "")[:3000]
        if text and len(text) > 100:
            deep_content.append("--- " + item["title"] + " ---\n" + text)
            fetched_urls.add(item["url"])

    local_source_hits = _count_hits_for_domains(
        [{"href": item.get("url", "")} for item in normalized_search + news_results],
        preferred_domains,
    )
    weak_coverage = (
        len(normalized_search) < 3
        or (needs_news_feed and not news_results)
        or (local_first and preferred_domains and local_source_hits == 0)
    )

    deeper_search = False
    deep_context = ""
    if needs_deep_search and weak_coverage:
        deep_engines = ("wikipedia", "tavily", "duckduckgo") if intent_kind == "historical" else ("tavily", "duckduckgo", "wikipedia")
        deep_context = research_web(
            query,
            max_results=6,
            pages_to_read=3,
            engines=deep_engines,
            intent_kind=intent_kind,
            geo_scope=geo_scope,
            local_first=local_first,
            preferred_domains=preferred_domains,
        )
        deeper_search = bool(deep_context)

    parts = [f"=== РџРћР”РўР•РњРђ: {label} ===", f"Р—Р°РїСЂРѕСЃ: {query}"]

    if deep_content:
        parts.append("РЎРћР”Р•Р Р–РРњРћР• Р’Р•Р‘-РЎРўР РђРќРР¦:\n" + "\n\n".join(deep_content))

    if news_results:
        lines = []
        for item in news_results[:5]:
            date_str = f" [{item['date']}]" if item.get("date") else ""
            source_str = f" ({item['source']})" if item.get("source") else ""
            lines.append(f"- {item['title']}{date_str}{source_str}: {item['snippet']}")
        parts.append("РЎР’Р•Р–РР• РќРћР’РћРЎРўР:\n" + "\n".join(lines))

    remaining = [item for item in normalized_search if item["url"] not in fetched_urls][:4]
    if remaining:
        lines = [f"- {item['title']}: {item['snippet']}" for item in remaining]
        parts.append("РћРЎРўРђР›Р¬РќР«Р• Р Р•Р—РЈР›Р¬РўРђРўР«:\n" + "\n".join(lines))

    if deep_context:
        parts.append("РЈР“Р›РЈР‘Р›Р•РќРќР«Р™ РџРћРРЎРљ:\n" + deep_context)

    if not normalized_search and not news_results and not deep_context:
        parts.append("РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ СЃРІРµР¶РёС… РїРѕРґС‚РІРµСЂР¶РґРµРЅРЅС‹С… РґР°РЅРЅС‹С… РїРѕ СЌС‚РѕР№ РїРѕРґС‚РµРјРµ.")

    engines_used = sorted(
        {
            item.get("engine", "")
            for item in normalized_search + news_results
            if item.get("engine")
        }
    )

    return {
        "context": "\n\n".join(part for part in parts if part.strip()),
        "debug": {
            "label": label,
            "query": query,
            "intent_kind": intent_kind,
            "geo_scope": geo_scope,
            "found": len(normalized_search),
            "news_hits": len(news_results),
            "fetched_pages": len(deep_content),
            "engines": engines_used,
            "local_source_hits": local_source_hits,
            "deeper_search_used": deeper_search,
            "coverage": "strong" if (len(normalized_search) >= 3 or news_results or deep_content) else "weak",
        },
    }


def _do_web_search(query, timeline, tool_results):
    """
    Multi-engine РїРѕРёСЃРє: DDG + Bing + Google + Yandex + DDG News.
    РџР°СЂР°Р»Р»РµР»СЊРЅС‹Р№ fetch top-3 СЃС‚СЂР°РЅРёС† С‡РµСЂРµР· BeautifulSoup.
    РСЃРїРѕР»СЊР·СѓРµС‚ core/web.py РґР»СЏ РјСѓР»СЊС‚Рё-РїРѕРёСЃРєР°.
    """
    search_query = _clean_query(query)

    # в•ђв•ђв•ђ РЁР°Рі 1: Multi-engine РїРѕРёСЃРє в•ђв•ђв•ђ
    search_results = []
    engines_used = []
    try:
        from app.core.web import fetch_page_text as core_fetch
        from app.core.web import search_news as core_search_news
        from app.core.web import search_web as multi_search
        raw = multi_search(search_query, max_results=12)
        for r in raw:
            href = r.get("href", "")
            if href and href.startswith("http"):
                search_results.append({
                    "title": r.get("title", ""),
                    "url": href,
                    "snippet": r.get("body", ""),
                    "engine": r.get("engine", ""),
                })
        engines_used = sorted({r.get("engine", "") for r in raw if r.get("engine")})
    except Exception as e:
        logger.warning(f"Web search failed: {e}")

    # Fallback: С‚РѕР»СЊРєРѕ DDG РµСЃР»Рё РјСѓР»СЊС‚Рё-РїРѕРёСЃРє СѓРїР°Р»
    if not search_results:
        try:
            DDGS = None
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                raw = list(ddgs.text(search_query, max_results=8))
            for r in raw:
                url = r.get("href") or r.get("url") or ""
                if url:
                    search_results.append({"title": r.get("title", ""), "url": url, "snippet": r.get("body", ""), "engine": "duckduckgo"})
            engines_used = ["duckduckgo"]
        except Exception as e:
            logger.warning(f"DDG fallback also failed: {e}")

    # в•ђв•ђв•ђ РЁР°Рі 1.5: DDG News (СЃРІРµР¶РёРµ РЅРѕРІРѕСЃС‚Рё) в•ђв•ђв•ђ
    news_results = []
    try:
        news_raw = core_search_news(search_query, max_results=5)
        for n in news_raw:
            url = n.get("href") or n.get("url") or ""
            if url and url.startswith("http"):
                news_results.append({
                    "title": n.get("title", ""),
                    "url": url,
                    "snippet": n.get("body", ""),
                    "date": n.get("date", ""),
                    "source": n.get("source", ""),
                })
        if news_results and "ddg-news" not in engines_used:
            engines_used.append("ddg-news")
    except Exception:
        pass  # РќРѕРІРѕСЃС‚Рё вЂ” Р±РѕРЅСѓСЃ, РЅРµ РєСЂРёС‚РёС‡РЅРѕ

    if not search_results and not news_results:
        _tl(timeline, "tool_web", "Р’РµР±-РїРѕРёСЃРє", "error", "РќРµС‚ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ")
        tool_results.append({"tool": "web_search", "result": {"count": 0}})
        return "[РџРѕРёСЃРє РЅРµ РґР°Р» СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ]"

    # в•ђв•ђв•ђ РЁР°Рі 2: Deep fetch top-3 СЃС‚СЂР°РЅРёС† (РїР°СЂР°Р»Р»РµР»СЊРЅРѕ) в•ђв•ђв•ђ
    deep_content = []
    fetched_urls = set()
    skip_domains = ["youtube.com", "youtu.be", "facebook.com", "instagram.com",
                    "tiktok.com", "twitter.com", "x.com", "vk.com", "t.me",
                    "pinterest.com"]

    # Р”РµРґСѓРїР»РёРєР°С†РёСЏ URL, С„РёР»СЊС‚СЂ СЃРѕС†СЃРµС‚РµР№
    all_urls_seen = set()
    fetch_candidates = []
    for item in search_results[:7]:
        url = item["url"]
        if url not in all_urls_seen and not any(d in url for d in skip_domains):
            all_urls_seen.add(url)
            fetch_candidates.append(item)

    # РџР°СЂР°Р»Р»РµР»СЊРЅС‹Р№ fetch С‡РµСЂРµР· ThreadPoolExecutor
    from concurrent.futures import ThreadPoolExecutor, as_completed
    targets = fetch_candidates[:5]  # РџСЂРѕР±СѓРµРј 5, Р±РµСЂС‘Рј Р»СѓС‡С€РёРµ 3
    if targets:
        page_results = {}  # url в†’ text
        with ThreadPoolExecutor(max_workers=min(len(targets), 4)) as executor:
            future_map = {executor.submit(core_fetch, t["url"]): t for t in targets}
            for future in as_completed(future_map):
                item = future_map[future]
                try:
                    text = (future.result() or "")[:3000]
                    if text and len(text) > 100 and not text.lower().startswith("СЂС›СЃв‚¬СЂС‘СЂВ±СЂС”СЂВ°"):
                        page_results[item["url"]] = (item, text)
                except Exception:
                    pass

        # Р‘РµСЂС‘Рј РїРµСЂРІС‹Рµ 3 СѓСЃРїРµС€РЅС‹С… (РїРѕ РїРѕСЂСЏРґРєСѓ РѕСЂРёРіРёРЅР°Р»СЊРЅС‹С… СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ)
        for t in targets:
            if t["url"] in page_results and len(deep_content) < 3:
                item, text = page_results[t["url"]]
                deep_content.append(
                    "--- " + item["title"] + " ---\n"
                    + text
                )
                fetched_urls.add(item["url"])

    fetched_count = len(deep_content)

    # в•ђв•ђв•ђ РЁР°Рі 3: Р¤РѕСЂРјРёСЂСѓРµРј РєРѕРЅС‚РµРєСЃС‚ в•ђв•ђв•ђ
    engines_str = ", ".join(engines_used) if engines_used else "search"
    tool_results.append({"tool": "web_search", "result": {
        "query": search_query,
        "found": len(search_results),
        "news": len(news_results),
        "fetched_pages": fetched_count,
        "engines": engines_used,
    }})
    _tl(timeline, "tool_web", "Р’РµР±-РїРѕРёСЃРє", "done",
        f"{len(search_results)} РЅР°Р№РґРµРЅРѕ ({engines_str}), {fetched_count} СЃС‚СЂР°РЅРёС† Р·Р°РіСЂСѓР¶РµРЅРѕ, {len(news_results)} РЅРѕРІРѕСЃС‚РµР№")

    parts = []

    # Р“Р»СѓР±РѕРєРёР№ РєРѕРЅС‚РµРЅС‚ (СЃРѕ СЃС‚СЂР°РЅРёС†)
    if deep_content:
        parts.append("в•ђв•ђ РЎРћР”Р•Р Р–РРњРћР• Р’Р•Р‘-РЎРўР РђРќРР¦ (РРЎРџРћР›Р¬Р—РЈР™ Р­РўР Р”РђРќРќР«Р•!) в•ђв•ђ\n\n" + "\n\n".join(deep_content))

    # РЎРІРµР¶РёРµ РЅРѕРІРѕСЃС‚Рё
    if news_results:
        news_lines = []
        for n in news_results[:5]:
            date_str = f" [{n['date']}]" if n.get("date") else ""
            source_str = f" ({n['source']})" if n.get("source") else ""
            news_lines.append(f"- {n['title']}{date_str}{source_str}: {n['snippet']}")
        parts.append("в•ђв•ђ РЎР’Р•Р–РР• РќРћР’РћРЎРўР в•ђв•ђ\n" + "\n".join(news_lines))

    # РЎРЅРёРїРїРµС‚С‹ РѕСЃС‚Р°Р»СЊРЅС‹С… СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ (РёСЃРєР»СЋС‡Р°РµРј СѓР¶Рµ Р·Р°РіСЂСѓР¶РµРЅРЅС‹Рµ)
    remaining = [s for s in search_results if s["url"] not in fetched_urls][:5]
    if remaining:
        snippet_lines = [f"- {s['title']}: {s['snippet']}" for s in remaining]
        parts.append("в•ђв•ђ Р”Р РЈР“РР• Р Р•Р—РЈР›Р¬РўРђРўР« в•ђв•ђ\n" + "\n".join(snippet_lines))

    
      # 5. Task Planner Skills
      if "todo" not in disabled:
          task_triggers = ["создай задачу", "добавь в план", "новая задача", "план:", "todo:"]
          if any(t in ql for t in task_triggers):
              try:
                  from app.services.skills_service import add_task
                  # ╨а╤Ш╨а╨Е╨а╤С-╨а╤Ч╨а┬░╨б╨В╨б╨Г╨а╤С╨а╨Е╨а╤Ц ╨а╨Е╨а┬░╨а┬╖╨а╨Ж╨а┬░╨а╨Е╨а╤С╨б╨П ╨а┬╖╨а┬░╨а╥С╨а┬░╨бтАб╨а╤С
                  title_match = re.search(r"(?:задач[ау]|план|todo):\s*(.*)", user_input, re.I)
                  if title_match:
                      title = title_match.group(1).strip()
                      res = add_task(title)
                      if res.get("ok"):
                          parts.append(f"✅ Задача добавлена в план: {title} (ID: {res.get('id')})")
              except Exception as e:
                  parts.append(f"SKILL_ERROR: Task Planner: {e}")

          status_triggers = ["статус задачи", "выполнил задачу", "заверши задачу"]
          if any(t in ql for t in status_triggers):
              try:
                  from app.services.skills_service import set_task_status
                  id_match = re.search(r"([a-f0-9]{8})", user_input)
                  if id_match:
                      res = set_task_status(id_match.group(1), "done")
                      if res.get("ok"):
                          parts.append(f"✅ Статус задачи {id_match.group(1)} обновлен на 'done'")
              except Exception as e:
                  parts.append(f"SKILL_ERROR: Task Status: {e}")
\n      return "\n\n".join(parts)


# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
# РљРћРќРўР•РљРЎРў
# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ

def _do_temporal_web_search(query, timeline, tool_results, temporal=None):
    temporal = temporal or {}
    context = _do_web_search(query, timeline, tool_results)
    web_result = _get_web_search_result(tool_results)
    found = int(web_result.get("found", 0) or 0)
    fetched_pages = int(web_result.get("fetched_pages", 0) or 0)
    news_count = int(web_result.get("news", 0) or 0)
    engines_used = set(web_result.get("engines", []) or [])
    current_evidence_engines = {"tavily", "duckduckgo", "ddg-news"}
    has_current_evidence = bool(engines_used & current_evidence_engines) or news_count > 0
    deeper_search = False

    if temporal.get("requires_web") and temporal.get("reasoning_depth") == "deep":
        weak_coverage = found < 4 or fetched_pages < 2 or (temporal.get("freshness_sensitive") and not has_current_evidence)
        if weak_coverage:
            try:
                from app.core.web import research_web
                deep_engines = ("wikipedia", "tavily", "duckduckgo") if temporal.get("stable_historical") else ("tavily", "duckduckgo", "wikipedia")

                deep_context = research_web(
                    _clean_query(query),
                    max_results=8,
                    pages_to_read=4,
                    engines=deep_engines,
                )
                if deep_context:
                    deeper_search = True
                    context = (
                        context + "\n\nР”РѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Р№ СѓРіР»СѓР±Р»РµРЅРЅС‹Р№ РІРµР±-РїРѕРёСЃРє:\n" + deep_context
                        if context
                        else deep_context
                    )
                    _tl(timeline, "tool_web_deep", "РЈРіР»СѓР±Р»РµРЅРЅС‹Р№ РІРµР±-РїРѕРёСЃРє", "done", "Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅР°СЏ РїСЂРѕРІРµСЂРєР° РёСЃС‚РѕС‡РЅРёРєРѕРІ")
            except Exception as exc:
                _tl(timeline, "tool_web_deep", "РЈРіР»СѓР±Р»РµРЅРЅС‹Р№ РІРµР±-РїРѕРёСЃРє", "error", str(exc))

    if temporal.get("freshness_sensitive"):
        freshness_state = "fresh_checked" if has_current_evidence and (news_count > 0 or fetched_pages >= 2 or deeper_search) else "unverified_current"
        freshness_note = (
            "Freshness status: fresh_checked. Use current web findings as the main evidence."
            if freshness_state == "fresh_checked"
            else "Freshness status: unverified_current. If confidence is limited, say that the data may be outdated or not fully verified."
        )
    elif temporal.get("stable_historical"):
        freshness_state = "historical_or_stable"
        freshness_note = "Freshness status: historical_or_stable. Treat this as a mostly stable historical topic."
    else:
        freshness_state = "standard_web"
        freshness_note = "Freshness status: standard_web. Use the web findings naturally without exposing internal formatting."

    if tool_results and tool_results[-1].get("tool") == "web_search":
        result = tool_results[-1].setdefault("result", {})
        if isinstance(result, dict):
            result["freshness_state"] = freshness_state
            result["deeper_search"] = deeper_search
            result["temporal_mode"] = temporal.get("mode", "none")
            result["has_current_evidence"] = has_current_evidence

    if context:
        context += "\n\n" + freshness_note
    return context


def _do_web_search(query, timeline, tool_results, web_plan=None):
    search_query = _clean_query(query)
    plan = web_plan or {
        "is_multi_intent": False,
        "subqueries": [
            {
                "label": "Web search",
                "query": search_query,
                "intent_kind": "general_web",
                "geo_scope": "",
                "freshness_class": "stable",
                "local_first": False,
                "needs_news_feed": False,
                "needs_deep_search": False,
                "preferred_domains": [],
            }
        ],
    }

    raw_subqueries = list(plan.get("subqueries") or [])[:6]
    if not raw_subqueries:
        raw_subqueries = [
            {
                "label": "Web search",
                "query": search_query,
                "intent_kind": "general_web",
                "geo_scope": "",
                "freshness_class": "stable",
                "local_first": False,
                "needs_news_feed": False,
                "needs_deep_search": False,
                "preferred_domains": [],
                "priority": 0,
            }
        ]

    passes = list(plan.get("passes") or [])
    if not passes:
        passes = [
            {
                "name": f"pass_{pass_index + 1}",
                "subqueries": raw_subqueries[offset : offset + 3],
            }
            for pass_index, offset in enumerate(range(0, len(raw_subqueries), 3))
        ]

    sections = []
    debug_rows = []
    pass_summaries = []
    engines_used = set()
    total_found = 0
    total_news = 0
    total_fetched = 0
    total_local_hits = 0
    deeper_search_used = False
    uncovered_subqueries = list(plan.get("uncovered_subqueries") or [])

    for pass_index, pass_spec in enumerate(passes, start=1):
        pass_name = str(pass_spec.get("name") or f"pass_{pass_index}")
        pass_found = 0
        pass_news = 0
        pass_pages = 0
        pass_engines = set()
        pass_queries = []
        pass_uncovered = []

        for subquery in list(pass_spec.get("subqueries") or [])[:3]:
            subquery_result = _build_single_web_subquery_context(subquery)
            context = (subquery_result.get("context") or "").strip()
            debug = dict(subquery_result.get("debug") or {})
            debug["pass_name"] = pass_name
            debug_rows.append(debug)
            pass_queries.append(debug.get("query", ""))

            if context:
                sections.append(context)

            found = int(debug.get("found", 0) or 0)
            news_hits = int(debug.get("news_hits", 0) or 0)
            fetched_pages = int(debug.get("fetched_pages", 0) or 0)
            local_hits = int(debug.get("local_source_hits", 0) or 0)
            coverage = str(debug.get("coverage", "weak") or "weak")

            total_found += found
            total_news += news_hits
            total_fetched += fetched_pages
            total_local_hits += local_hits
            deeper_search_used = deeper_search_used or bool(debug.get("deeper_search_used"))
            engines_used.update(debug.get("engines", []) or [])

            pass_found += found
            pass_news += news_hits
            pass_pages += fetched_pages
            pass_engines.update(debug.get("engines", []) or [])

            if coverage != "strong":
                pass_uncovered.append(debug.get("query", ""))
                uncovered_subqueries.append(debug.get("query", ""))

            if found or news_hits or fetched_pages:
                _tl(
                    timeline,
                    f"tool_web_{pass_name}_{len(pass_queries)}",
                    f"Р’РµР±-РїРѕРёСЃРє {pass_name}",
                    "done",
                    f"{debug.get('query', '')}: found={found}, news={news_hits}, pages={fetched_pages}",
                )
            else:
                _tl(
                    timeline,
                    f"tool_web_{pass_name}_{len(pass_queries)}",
                    f"Р’РµР±-РїРѕРёСЃРє {pass_name}",
                    "error",
                    f"{debug.get('query', '')}: no confirmed results",
                )

        pass_summaries.append(
            {
                "name": pass_name,
                "subqueries": pass_queries,
                "found": pass_found,
                "news_hits": pass_news,
                "fetched_pages": pass_pages,
                "engines": sorted(pass_engines),
                "uncovered_subqueries": [item for item in pass_uncovered if item],
            }
        )
        _tl(
            timeline,
            f"tool_web_{pass_name}",
            f"Р’РµР±-РїСЂРѕС…РѕРґ {pass_index}",
            "done",
            f"{len(pass_queries)} РїРѕРґС‚РµРј, found={pass_found}, news={pass_news}, pages={pass_pages}",
        )

    unique_uncovered = list(dict.fromkeys(item for item in uncovered_subqueries if item))
    result_payload = {
        "query": search_query,
        "count": total_found,
        "found": total_found,
        "news": total_news,
        "fetched_pages": total_fetched,
        "engines": sorted(engines_used),
        "subqueries": [debug.get("query", "") for debug in debug_rows],
        "coverage_by_subquery": {
            debug.get("query", f"subquery_{idx + 1}"): debug.get("coverage", "weak")
            for idx, debug in enumerate(debug_rows)
        },
        "engines_by_subquery": {
            debug.get("query", f"subquery_{idx + 1}"): debug.get("engines", [])
            for idx, debug in enumerate(debug_rows)
        },
        "local_source_hits": total_local_hits,
        "news_hits": total_news,
        "deeper_search_used": deeper_search_used,
        "is_multi_intent": bool(plan.get("is_multi_intent")),
        "passes": pass_summaries,
        "pass_count": len(pass_summaries),
        "total_subqueries": len(raw_subqueries),
        "overflow_applied": bool(plan.get("overflow_applied") or len(raw_subqueries) > 3),
        "uncovered_subqueries": unique_uncovered,
    }
    tool_results.append({"tool": "web_search", "result": result_payload})

    if not sections:
        _tl(timeline, "tool_web", "Р’РµР±-РїРѕРёСЃРє", "error", "РќРµС‚ РїРѕРґС‚РІРµСЂР¶РґРµРЅРЅС‹С… СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ")
        return "[РџРѕРёСЃРє РЅРµ РґР°Р» СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ]"

    _tl(
        timeline,
        "tool_web",
        "Р’РµР±-РїРѕРёСЃРє",
        "done",
        f"{total_found} РЅР°Р№РґРµРЅРѕ, {total_news} РЅРѕРІРѕСЃС‚РµР№, {total_fetched} СЃС‚СЂР°РЅРёС†, {len(raw_subqueries)} РїРѕРґС‚РµРј, {len(pass_summaries)} РїСЂРѕС…РѕРґРѕРІ",
    )
    return "\n\n".join(section for section in sections if section.strip())


def _do_temporal_web_search(query, timeline, tool_results, temporal=None, web_plan=None):
    temporal = temporal or {}
    context = _do_web_search(query, timeline, tool_results, web_plan=web_plan)
    web_result = _get_web_search_result(tool_results)
    found = int(web_result.get("found", 0) or 0)
    fetched_pages = int(web_result.get("fetched_pages", 0) or 0)
    news_count = int(web_result.get("news", 0) or 0)
    subquery_count = int(web_result.get("total_subqueries", len(web_result.get("subqueries", []) or [])) or 0)
    engines_used = set(web_result.get("engines", []) or [])
    current_evidence_engines = {"tavily", "duckduckgo", "ddg-news"}
    has_current_evidence = bool(engines_used & current_evidence_engines) or news_count > 0
    deeper_search = bool(web_result.get("deeper_search_used"))

    if temporal.get("requires_web") and temporal.get("reasoning_depth") == "deep":
        weak_coverage = (
            found < max(4, subquery_count * 2)
            or fetched_pages < max(2, subquery_count)
            or (temporal.get("freshness_sensitive") and not has_current_evidence)
        )
        if weak_coverage:
            try:
                from app.core.web import research_web

                deep_engines = ("wikipedia", "tavily", "duckduckgo") if temporal.get("stable_historical") else ("tavily", "duckduckgo", "wikipedia")

                deep_context = research_web(
                    _clean_query(query),
                    max_results=8,
                    pages_to_read=4,
                    engines=deep_engines,
                    intent_kind="historical" if temporal.get("stable_historical") else "general_web",
                )
                if deep_context:
                    deeper_search = True
                    context = (
                        context + "\n\nР”РѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Р№ СѓРіР»СѓР±Р»РµРЅРЅС‹Р№ РІРµР±-РїРѕРёСЃРє:\n" + deep_context
                        if context
                        else deep_context
                    )
                    _tl(timeline, "tool_web_deep", "РЈРіР»СѓР±Р»РµРЅРЅС‹Р№ РІРµР±-РїРѕРёСЃРє", "done", "Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅР°СЏ РїСЂРѕРІРµСЂРєР° РёСЃС‚РѕС‡РЅРёРєРѕРІ")
            except Exception as exc:
                _tl(timeline, "tool_web_deep", "РЈРіР»СѓР±Р»РµРЅРЅС‹Р№ РІРµР±-РїРѕРёСЃРє", "error", str(exc))

    if temporal.get("freshness_sensitive"):
        freshness_state = "fresh_checked" if has_current_evidence and (news_count > 0 or fetched_pages >= 2 or deeper_search) else "unverified_current"
        freshness_note = (
            "Freshness status: fresh_checked. Use current web findings as the main evidence."
            if freshness_state == "fresh_checked"
            else "Freshness status: unverified_current. If confidence is limited, say that the data may be outdated or not fully verified."
        )
    elif temporal.get("stable_historical"):
        freshness_state = "historical_or_stable"
        freshness_note = "Freshness status: historical_or_stable. Treat this as a mostly stable historical topic."
    else:
        freshness_state = "standard_web"
        freshness_note = "Freshness status: standard_web. Use the web findings naturally without exposing internal formatting."

    if tool_results and tool_results[-1].get("tool") == "web_search":
        result = tool_results[-1].setdefault("result", {})
        if isinstance(result, dict):
            result["freshness_state"] = freshness_state
            result["deeper_search"] = deeper_search
            result["temporal_mode"] = temporal.get("mode", "none")
            result["has_current_evidence"] = has_current_evidence

    if context:
        context += "\n\n" + freshness_note
    return context


def _collect_context(
    *,
    profile_name,
    user_input,
    tools,
    tool_results,
    timeline,
    use_reflection=False,
    temporal=None,
    web_plan=None,
    source_agent_id="",
    run_id="",
):
    parts = []
    for tool_name in tools:
        try:
            if tool_name == "memory_search":
                result = run_tool(
                    "search_memory",
                    {"profile": profile_name, "query": user_input, "limit": 5},
                    source="agent_run",
                    source_agent_id=source_agent_id,
                    run_id=run_id,
                )
                tool_results.append({"tool": "search_memory", "result": result})
                items = result.get("items", [])
                _tl(timeline, "tool_memory", "РџР°РјСЏС‚СЊ", "done", str(result.get("count", 0)))
                if items:
                    parts.append("РР· РїР°РјСЏС‚Рё:\n" + "\n".join("- " + i.get("text", "") for i in items))

            elif tool_name == "library_context":
                _tl(timeline, "tool_library", "Р‘РёР±Р»РёРѕС‚РµРєР°", "skip", "Р¤СЂРѕРЅС‚РµРЅРґ")

            elif tool_name == "web_search":
                web_ctx = _do_temporal_web_search(user_input, timeline, tool_results, temporal=temporal, web_plan=web_plan)
                if web_ctx:
                    parts.append(web_ctx)

            elif tool_name == "project_mode":
                project_ctx = ""
                # РџРѕРїС‹С‚РєР° 1: СЃС‚Р°СЂС‹Р№ project_service
                try:
                    tree = run_tool(
                        "list_project_tree",
                        {"max_depth": 3, "max_items": 200},
                        source="agent_run",
                        source_agent_id=source_agent_id,
                        run_id=run_id,
                    )
                    search = run_tool(
                        "search_project",
                        {"query": user_input, "max_hits": 20},
                        source="agent_run",
                        source_agent_id=source_agent_id,
                        run_id=run_id,
                    )
                    tool_results.append({"tool": "project", "result": {"tree": tree.get("count", 0), "hits": search.get("count", 0)}})
                    snippets = search.get("items") or search.get("results") or []
                    if snippets:
                        rendered = ["- " + (item.get("path","") + ": " + (item.get("snippet","") or item.get("preview","")) if isinstance(item,dict) else str(item)) for item in snippets[:10]]
                        project_ctx = "РР· РїСЂРѕРµРєС‚Р°:\n" + "\n".join(rendered)
                except Exception:
                    pass

                # РџРѕРїС‹С‚РєР° 2: advanced project API (РµСЃР»Рё РѕС‚РєСЂС‹С‚ С‡РµСЂРµР· UI)
                if not project_ctx:
                    try:
                        from app.api.routes.advanced_routes import _project_path
                        if _project_path:
                            from pathlib import Path
                            root = Path(_project_path)
                            if root.exists():
                                file_list = []
                                for f in sorted(root.rglob("*"))[:50]:
                                    if f.is_file() and not any(b in str(f) for b in [".git","node_modules","__pycache__",".venv","dist"]):
                                        file_list.append(str(f.relative_to(root)))
                                project_ctx = f"РћС‚РєСЂС‹С‚ РїСЂРѕРµРєС‚: {root.name}\nР¤Р°Р№Р»С‹ ({len(file_list)}):\n" + "\n".join("- " + f for f in file_list[:30])
                    except Exception:
                        pass

                if project_ctx:
                    parts.append(project_ctx)
                    _tl(timeline, "tool_project", "РџСЂРѕРµРєС‚", "done", "РљРѕРЅС‚РµРєСЃС‚ Р·Р°РіСЂСѓР¶РµРЅ")
                else:
                    _tl(timeline, "tool_project", "РџСЂРѕРµРєС‚", "skip", "РќРµ РѕС‚РєСЂС‹С‚")

            elif tool_name == "python_executor":
                _tl(timeline, "tool_python", "Python", "ready", "Р’С‹РїРѕР»РЅРµРЅРёРµ РїРѕ Р·Р°РїСЂРѕСЃСѓ")

            elif tool_name == "project_patch":
                _tl(timeline, "tool_patch", "РџР°С‚С‡РёРЅРі", "ready", "")

        except Exception as exc:
            _tl(timeline, "tool_" + tool_name, tool_name, "error", str(exc))

    return "\n\n".join(p for p in parts if p.strip())


# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
# run_agent
# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ

def run_agent(*, model_name, profile_name, user_input, session_id=None, agent_id=None, use_memory=True, use_library=True, use_reflection=False, history=None, num_ctx=8192, use_web_search=True, use_python_exec=True, use_image_gen=True, use_file_gen=True, use_http_api=True, use_sql=True, use_screenshot=True, use_encrypt=True, use_archiver=True, use_converter=True, use_regex=True, use_translator=True, use_csv=True, use_webhook=True, use_plugins=True):
    from app.services.chat_history_service import save_message, get_history
    if session_id and not history:
        history = get_history(session_id, limit=20)
    import time as _time
    _agent_start = _time.monotonic()

    # Agent OS: РµСЃР»Рё СѓРєР°Р·Р°РЅ agent_id, Р·Р°РіСЂСѓР¶Р°РµРј РѕРїСЂРµРґРµР»РµРЅРёРµ РёР· СЂРµРµСЃС‚СЂР°
    _registry_agent = None
    if agent_id:
        try:
            from app.services.agent_registry import resolve_agent
            _registry_agent = resolve_agent(agent_id=agent_id)
            if _registry_agent:
                if _registry_agent.get("system_prompt"):
                    profile_name = _registry_agent.get("name_ru") or profile_name
                if _registry_agent.get("model_preference"):
                    model_name = _registry_agent["model_preference"]
        except Exception:
            pass

    _effective_agent_id = resolve_effective_agent_id(
        agent_id=agent_id,
        profile_name=profile_name,
        registry_agent=_registry_agent,
    )
    history = _trim_history(history or [])
    _skill_flags = {"web_search": use_web_search, "python_exec": use_python_exec, "image_gen": use_image_gen, "file_gen": use_file_gen, "http_api": use_http_api, "sql": use_sql, "screenshot": use_screenshot, "encrypt": use_encrypt, "archiver": use_archiver, "converter": use_converter, "regex": use_regex, "translator": use_translator, "csv_analysis": use_csv, "webhook": use_webhook, "plugins": use_plugins}
    _disabled_skills = {k for k, v in _skill_flags.items() if not v}
    timeline, tool_results = [], []
    planner = PlannerV2Service()
    raw_user_input = user_input
    planner_input = _strip_frontend_project_context(user_input)
    run = _HISTORY.start_run(raw_user_input)
    _agent_os_source_id = _effective_agent_id
    _emit_agent_os_event(
        event_type="agent.run.started",
        source_agent_id=_agent_os_source_id,
        payload={
            "run_id": run["run_id"],
            "profile_name": profile_name,
            "requested_model": model_name,
            "session_id": str(session_id or ""),
            "streaming": False,
        },
    )
    try:
        plan = planner.plan(planner_input)
        _HISTORY.add_event(run["run_id"], "planner", plan)
        route = plan.get("route", "chat")
        temporal = plan.get("temporal", {})
        web_plan = plan.get("web_plan", {"is_multi_intent": False, "subqueries": []})
        effective_model = pick_model_for_route(route, model_name)
        selected = [t for t in plan.get("tools", []) if not (t == "memory_search" and not use_memory) and not (t == "library_context" and not use_library) and not (t == "web_search" and not use_web_search)]
        if temporal.get("requires_web") and use_web_search and "web_search" not in selected:
            selected.append("web_search")
        strict_web_only = route == "research" and temporal.get("mode") == "hard" and temporal.get("freshness_sensitive")
        if strict_web_only:
            selected = [t for t in selected if t != "memory_search"]
        if is_memory_command(planner_input):
            selected = [t for t in selected if t != "memory_search"]

        # РЈРјРЅР°СЏ РїР°РјСЏС‚СЊ: РёР·РІР»РµРєР°РµРј С„Р°РєС‚С‹ РёР· СЃРѕРѕР±С‰РµРЅРёСЏ
        try:
            saved = extract_and_save(planner_input)
            if saved:
                _tl(timeline, "memory_save", "РџР°РјСЏС‚СЊ", "done", "РЎРѕС…СЂР°РЅРµРЅРѕ: " + str(len(saved)))
        except Exception:
            pass

        preflight_or_raise(
            agent_id=_effective_agent_id,
            num_ctx=num_ctx,
            selected_tools=selected,
            run_id=run["run_id"],
            route=route,
            streaming=False,
        )

        ctx = _collect_context(
            profile_name=profile_name,
            user_input=planner_input,
            tools=selected,
            tool_results=tool_results,
            timeline=timeline,
            use_reflection=use_reflection,
            temporal=temporal,
            web_plan=web_plan,
            source_agent_id=_effective_agent_id,
            run_id=run["run_id"],
        )

        # РЈРјРЅР°СЏ РїР°РјСЏС‚СЊ + RAG: РґРѕР±Р°РІР»СЏРµРј СЂРµР»РµРІР°РЅС‚РЅС‹Рµ РІРѕСЃРїРѕРјРёРЅР°РЅРёСЏ С‚РѕР»СЊРєРѕ РєРѕРіРґР° СЌС‚Рѕ СЂРµР°Р»СЊРЅРѕ РЅСѓР¶РЅРѕ
        if _should_recall_memory_context(planner_input, route, temporal):
            try:
                mem_limit, rag_limit = _get_memory_recall_limits(planner_input)
                mem_ctx = get_relevant_context(planner_input, max_items=mem_limit)
                if _HAS_RAG and rag_limit > 0:
                    rag_ctx = get_rag_context(planner_input, max_items=rag_limit)
                    if rag_ctx:
                        mem_ctx = (mem_ctx + "\n\n" + rag_ctx) if mem_ctx else rag_ctx
                if mem_ctx:
                    ctx = mem_ctx + "\n\n" + ctx if ctx else mem_ctx
                    _tl(timeline, "memory_recall", "РџР°РјСЏС‚СЊ", "done", "РќР°Р№РґРµРЅС‹ СЂРµР»РµРІР°РЅС‚РЅС‹Рµ Р·Р°РјРµС‚РєРё")
            except Exception:
                pass

        prompt = _build_prompt(raw_user_input, ctx, disabled_skills=_disabled_skills) + _compose_human_style_rules(temporal)
        task_context = f"РњР°СЂС€СЂСѓС‚: {route}. РРЅСЃС‚СЂСѓРјРµРЅС‚С‹: {', '.join(selected) if selected else 'РЅРµС‚ РґРѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹С… РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ'}."
        draft = run_chat(model_name=effective_model, profile_name=profile_name, user_input=prompt, history=history, num_ctx=num_ctx, task_context=task_context)
        if not draft.get("ok"):
            raise RuntimeError("; ".join(draft.get("warnings", [])) or "LLM failed")
        answer = draft.get("answer", "")

        # Reflection: РґР»СЏ code/project РР›Р РµСЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РІРєР»СЋС‡РёР» СЃРєРёР»Р»
        has_generated_files = any(a["type"] in ("image", "file") for a in _pending_attachments)
        should_reflect = (route in _REFLECTION_ROUTES) or use_reflection
        if should_reflect and answer.strip() and not has_generated_files:
            ref = run_reflection_loop(model_name=effective_model, profile_name=profile_name, user_input=raw_user_input, draft_text=answer, review_text="РЈР»СѓС‡С€Рё.", context=ctx)
            answer = ref.get("answer") or answer

        # Р”РѕР±Р°РІР»СЏРµРј РІР»РѕР¶РµРЅРёСЏ (РєР°СЂС‚РёРЅРєРё, С„Р°Р№Р»С‹)
        attachments = _get_and_clear_attachments()
        if attachments:
            answer += attachments

        # POST-РіРµРЅРµСЂР°С†РёСЏ: Word/Excel РёР· РѕС‚РІРµС‚Р° LLM
        post_files = _maybe_generate_files(raw_user_input, answer, enabled=use_file_gen)
        if post_files:
            answer += post_files

        identity_guard = _apply_identity_guard(raw_user_input, answer, timeline)
        answer = identity_guard.get("text", answer)
        provenance_guard = _apply_provenance_guard(raw_user_input, answer, timeline)
        answer = provenance_guard.get("text", answer)

        persona_meta = observe_dialogue(
            dialog_id=run["run_id"],
            session_id=str(session_id or run["run_id"]),
            profile_name=profile_name,
            model_name=effective_model,
            user_input=raw_user_input,
            answer_text=answer,
            route=route,
            outcome_ok=True,
        )
        result = {
            "ok": True,
            "answer": answer,
            "timeline": timeline,
            "tool_results": tool_results,
            "meta": {
                "model_name": effective_model,
                "profile_name": profile_name,
                "route": route,
                "tools": selected,
                "run_id": run["run_id"],
                "persona": persona_meta,
                "temporal": temporal,
                "web_plan": web_plan,
                "identity_guard": identity_guard if identity_guard.get("changed") else None,
                "provenance_guard": provenance_guard if provenance_guard.get("changed") else None,
            },
        }
        _HISTORY.finish_run(run["run_id"], result)
        _duration_ms = int((_time.monotonic() - _agent_start) * 1000)
        _record_agent_os_monitoring(
            agent_id=_effective_agent_id,
            run_id=run["run_id"],
            route=route,
            model_name=effective_model,
            ok=True,
            duration_ms=_duration_ms,
            streaming=False,
            num_ctx=num_ctx,
            selected_tools=selected,
        )

        # Agent OS: Р·Р°РїРёСЃС‹РІР°РµРј Р·Р°РїСѓСЃРє РІ СЂРµРµСЃС‚СЂ
        if agent_id or _registry_agent:
            try:
                from app.services.agent_registry import record_agent_run
                record_agent_run({
                    "agent_id": agent_id or (_registry_agent or {}).get("id", ""),
                    "run_id": run["run_id"],
                    "input_summary": raw_user_input[:500],
                    "output_summary": answer[:500],
                    "ok": True,
                    "route": route,
                    "model_used": effective_model,
                    "duration_ms": _duration_ms,
                })
            except Exception:
                pass
        _emit_agent_os_event(
            event_type="agent.run.completed",
            source_agent_id=_agent_os_source_id,
            payload={
                "run_id": run["run_id"],
                "profile_name": profile_name,
                "route": route,
                "ok": True,
                "model_used": effective_model,
                "duration_ms": _duration_ms,
                "session_id": str(session_id or ""),
                "streaming": False,
            },
        )

        return result
    except SandboxPolicyError as exc:
        err = {
            "ok": False,
            "answer": "",
            "timeline": timeline + [{"step": "sandbox", "title": "Sandbox", "status": "error", "detail": str(exc)}],
            "tool_results": tool_results,
            "meta": {
                "error": str(exc),
                "run_id": run["run_id"],
                "sandbox_reason": exc.reason,
                "sandbox_details": exc.details,
            },
        }
        _HISTORY.finish_run(run["run_id"], err)
        _duration_ms = int((_time.monotonic() - _agent_start) * 1000)
        _record_agent_os_monitoring(
            agent_id=_effective_agent_id,
            run_id=run["run_id"],
            route=locals().get("route", ""),
            model_name=locals().get("effective_model", model_name),
            ok=False,
            duration_ms=_duration_ms,
            streaming=False,
            num_ctx=num_ctx,
            selected_tools=locals().get("selected", []),
        )
        _emit_agent_os_event(
            event_type="agent.run.completed",
            source_agent_id=_agent_os_source_id,
            payload={
                "run_id": run["run_id"],
                "profile_name": profile_name,
                "route": locals().get("route", ""),
                "ok": False,
                "model_used": locals().get("effective_model", model_name),
                "duration_ms": _duration_ms,
                "error": str(exc)[:500],
                "session_id": str(session_id or ""),
                "streaming": False,
            },
        )
        return err
    except Exception as exc:
        err = {"ok": False, "answer": "", "timeline": timeline + [{"step": "error", "title": "РћС€РёР±РєР°", "status": "error", "detail": str(exc)}], "tool_results": tool_results, "meta": {"error": str(exc), "run_id": run["run_id"]}}
        _HISTORY.finish_run(run["run_id"], err)
        _duration_ms = int((_time.monotonic() - _agent_start) * 1000)

        # Agent OS: Р·Р°РїРёСЃС‹РІР°РµРј РѕС€РёР±РѕС‡РЅС‹Р№ Р·Р°РїСѓСЃРє
        _record_agent_os_monitoring(
            agent_id=_effective_agent_id,
            run_id=run["run_id"],
            route=locals().get("route", ""),
            model_name=locals().get("effective_model", model_name),
            ok=False,
            duration_ms=_duration_ms,
            streaming=False,
            num_ctx=num_ctx,
            selected_tools=locals().get("selected", []),
        )
        if agent_id or _registry_agent:
            try:
                from app.services.agent_registry import record_agent_run
                record_agent_run({
                    "agent_id": agent_id or (_registry_agent or {}).get("id", ""),
                    "run_id": run["run_id"],
                    "input_summary": raw_user_input[:500] if 'raw_user_input' in dir() else user_input[:500],
                    "output_summary": str(exc)[:500],
                    "ok": False,
                    "route": "",
                    "model_used": model_name,
                    "duration_ms": _duration_ms,
                })
            except Exception:
                pass

        _emit_agent_os_event(
            event_type="agent.run.completed",
            source_agent_id=_agent_os_source_id,
            payload={
                "run_id": run["run_id"],
                "profile_name": profile_name,
                "route": locals().get("route", ""),
                "ok": False,
                "model_used": locals().get("effective_model", model_name),
                "duration_ms": _duration_ms,
                "error": str(exc)[:500],
                "session_id": str(session_id or ""),
                "streaming": False,
            },
        )

        return err


# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
# run_agent_stream
# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ

def run_agent_stream(*, model_name, profile_name, user_input, session_id=None, use_memory=True, use_library=True, use_reflection=False, history=None, num_ctx=8192, use_web_search=True, use_python_exec=True, use_image_gen=True, use_file_gen=True, use_http_api=True, use_sql=True, use_screenshot=True, use_encrypt=True, use_archiver=True, use_converter=True, use_regex=True, use_translator=True, use_csv=True, use_webhook=True, use_plugins=True):
    import time as _time
    _agent_start = _time.monotonic()
    _effective_agent_id = resolve_effective_agent_id(profile_name=profile_name)
    history = _trim_history(history or [])
    _skill_flags = {"web_search": use_web_search, "python_exec": use_python_exec, "image_gen": use_image_gen, "file_gen": use_file_gen, "http_api": use_http_api, "sql": use_sql, "screenshot": use_screenshot, "encrypt": use_encrypt, "archiver": use_archiver, "converter": use_converter, "regex": use_regex, "translator": use_translator, "csv_analysis": use_csv, "webhook": use_webhook, "plugins": use_plugins}
    _disabled_skills = {k for k, v in _skill_flags.items() if not v}
    timeline, tool_results = [], []
    planner = PlannerV2Service()
    raw_user_input = user_input
    planner_input = _strip_frontend_project_context(user_input)
    run = _HISTORY.start_run(raw_user_input)
    _emit_agent_os_event(
        event_type="agent.run.started",
        source_agent_id=_effective_agent_id,
        payload={
            "run_id": run["run_id"],
            "profile_name": profile_name,
            "requested_model": model_name,
            "session_id": str(session_id or ""),
            "streaming": True,
        },
    )
    try:
        yield {"token": "", "done": False, "phase": "planning", "message": "Р”СѓРјР°СЋ..."}

        plan = planner.plan(planner_input)
        _HISTORY.add_event(run["run_id"], "planner", plan)
        route = plan.get("route", "chat")
        temporal = plan.get("temporal", {})
        web_plan = plan.get("web_plan", {"is_multi_intent": False, "subqueries": []})
        selected = [t for t in plan.get("tools", []) if not (t == "memory_search" and not use_memory) and not (t == "library_context" and not use_library) and not (t == "web_search" and not use_web_search)]
        if temporal.get("requires_web") and use_web_search and "web_search" not in selected:
            selected.append("web_search")
        strict_web_only = route == "research" and temporal.get("mode") == "hard" and temporal.get("freshness_sensitive")
        if strict_web_only:
            selected = [t for t in selected if t != "memory_search"]
        if is_memory_command(planner_input):
            selected = [t for t in selected if t != "memory_search"]

        # в•ђв•ђв•ђ РђР’РўРћ-Р’Р«Р‘РћР  РњРћР”Р•Р›Р (С‚РёС…Рѕ, Р±РµР· UI) в•ђв•ђв•ђ
        effective_model = pick_model_for_route(route, model_name)
        preflight_or_raise(
            agent_id=_effective_agent_id,
            num_ctx=num_ctx,
            selected_tools=selected,
            run_id=run["run_id"],
            route=route,
            streaming=True,
        )
        if effective_model != model_name:
            _tl(timeline, "auto_model", "РђРІС‚Рѕ-РјРѕРґРµР»СЊ", "ok", f"{model_name} в†’ {effective_model} (route={route})")

        # в•ђв•ђв•ђ РљР­РЁРР РћР’РђРќРР• в•ђв•ђв•ђ
        if should_cache(planner_input, route) and not history:
            cached = get_cached(planner_input, effective_model, profile_name)
            if cached:
                _tl(timeline, "cache_hit", "РљСЌС€", "ok", "РћС‚РІРµС‚ РёР· РєСЌС€Р°")
                identity_guard = _apply_identity_guard(raw_user_input, cached, timeline)
                cached = identity_guard.get("text", cached)
                provenance_guard = _apply_provenance_guard(raw_user_input, cached, timeline)
                cached = provenance_guard.get("text", cached)
                meta = {
                    "model_name": effective_model,
                    "profile_name": profile_name,
                    "route": route,
                    "tools": [],
                    "run_id": run["run_id"],
                    "cached": True,
                    "temporal": temporal,
                    "web_plan": web_plan,
                    "identity_guard": identity_guard if identity_guard.get("changed") else None,
                    "provenance_guard": provenance_guard if provenance_guard.get("changed") else None,
                }
                persona_meta = observe_dialogue(
                    dialog_id=run["run_id"],
                    session_id=str(session_id or run["run_id"]),
                    profile_name=profile_name,
                    model_name=effective_model,
                    user_input=raw_user_input,
                    answer_text=cached,
                    route=route,
                    outcome_ok=True,
                )
                meta["persona"] = persona_meta
                _HISTORY.finish_run(run["run_id"], {"ok": True, "answer": cached, "meta": meta})
                _record_agent_os_monitoring(
                    agent_id=_effective_agent_id,
                    run_id=run["run_id"],
                    route=route,
                    model_name=effective_model,
                    ok=True,
                    duration_ms=int((_time.monotonic() - _agent_start) * 1000),
                    streaming=True,
                    num_ctx=num_ctx,
                    selected_tools=selected,
                )
                _emit_agent_os_event(
                    event_type="agent.run.completed",
                    source_agent_id=_effective_agent_id,
                    payload={
                        "run_id": run["run_id"],
                        "profile_name": profile_name,
                        "route": route,
                        "ok": True,
                        "model_used": effective_model,
                        "duration_ms": int((_time.monotonic() - _agent_start) * 1000),
                        "session_id": str(session_id or ""),
                        "streaming": True,
                    },
                )
                # РЎС‚СЂРёРјРёРј РєСЌС€РёСЂРѕРІР°РЅРЅС‹Р№ РѕС‚РІРµС‚ РїРѕ С‚РѕРєРµРЅР°Рј (РІС‹РіР»СЏРґРёС‚ РµСЃС‚РµСЃС‚РІРµРЅРЅРѕ)
                words = cached.split(" ")
                for i, word in enumerate(words):
                    token = word if i == 0 else " " + word
                    yield {"token": token, "done": False}
                yield {"token": "", "done": True, "full_text": cached, "meta": meta, "timeline": timeline}
                return

        # РЈРјРЅР°СЏ РїР°РјСЏС‚СЊ: РёР·РІР»РµРєР°РµРј С„Р°РєС‚С‹
        try:
            extract_and_save(planner_input)
        except Exception:
            pass

        if "web_search" in selected:
            yield {"token": "", "done": False, "phase": "searching", "message": "РС‰Сѓ..."}
        elif selected:
            yield {"token": "", "done": False, "phase": "tools", "message": "РЎРѕР±РёСЂР°СЋ РєРѕРЅС‚РµРєСЃС‚..."}

        ctx = _collect_context(
            profile_name=profile_name,
            user_input=planner_input,
            tools=selected,
            tool_results=tool_results,
            timeline=timeline,
            use_reflection=use_reflection,
            temporal=temporal,
            web_plan=web_plan,
            source_agent_id=_effective_agent_id,
            run_id=run["run_id"],
        )

        # РЈРјРЅР°СЏ РїР°РјСЏС‚СЊ + RAG
        mem_count = 0
        if _should_recall_memory_context(planner_input, route, temporal):
            try:
                mem_limit, rag_limit = _get_memory_recall_limits(planner_input)
                mem_ctx = get_relevant_context(planner_input, max_items=mem_limit)
                if mem_ctx:
                    mem_count = mem_ctx.count("\n- ")
                if _HAS_RAG and rag_limit > 0:
                    rag_ctx = get_rag_context(planner_input, max_items=rag_limit)
                    if rag_ctx:
                        mem_ctx = (mem_ctx + "\n\n" + rag_ctx) if mem_ctx else rag_ctx
                if mem_ctx:
                    ctx = mem_ctx + "\n\n" + ctx if ctx else mem_ctx
            except Exception:
                pass

        yield {"token": "", "done": False, "phase": "thinking", "message": "РџРёС€Сѓ РѕС‚РІРµС‚..."}

        prompt = _build_prompt(raw_user_input, ctx, disabled_skills=_disabled_skills) + _compose_human_style_rules(temporal)
        full_text = ""
        task_context = f"РњР°СЂС€СЂСѓС‚: {route}. РРЅСЃС‚СЂСѓРјРµРЅС‚С‹: {', '.join(selected) if selected else 'РЅРµС‚ РґРѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹С… РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ'}."
        for token in run_chat_stream(model_name=effective_model, profile_name=profile_name, user_input=prompt, history=history, num_ctx=num_ctx, task_context=task_context):
            full_text += token
            yield {"token": token, "done": False}

        # Р”РѕР±Р°РІР»СЏРµРј РІР»РѕР¶РµРЅРёСЏ (РєР°СЂС‚РёРЅРєРё, С„Р°Р№Р»С‹) вЂ” Р±С‹СЃС‚СЂР°СЏ РѕРїРµСЂР°С†РёСЏ
        attachments = _get_and_clear_attachments()
        if attachments:
            full_text += attachments

        # РџСЂРѕРІРµСЂСЏРµРј РЅСѓР¶РЅС‹ Р»Рё С‚СЏР¶С‘Р»С‹Рµ РїРѕСЃС‚-РѕРїРµСЂР°С†РёРё
        has_generated_files = any(a["type"] in ("image", "file") for a in _pending_attachments)
        should_reflect = (route in _REFLECTION_ROUTES) or use_reflection
        ql_check = raw_user_input.lower()
        needs_file_gen = any(t in ql_check for t in _FILE_TRIGGERS_WORD + _FILE_TRIGGERS_EXCEL)

        # Р•СЃР»Рё РЅРµС‚ С‚СЏР¶С‘Р»С‹С… РѕРїРµСЂР°С†РёР№ вЂ” РѕС‚РїСЂР°РІР»СЏРµРј done РЎР РђР—РЈ (Р±С‹СЃС‚СЂС‹Р№ РїСѓС‚СЊ)
        if not should_reflect and not needs_file_gen:
            # РђРІС‚Рѕ-РІС‹РїРѕР»РЅРµРЅРёРµ Python (Р»С‘РіРєРѕРµ, С‚РѕР»СЊРєРѕ РµСЃР»Рё РµСЃС‚СЊ РєРѕРґ)
            try:
                full_text = _maybe_auto_exec_python(raw_user_input, full_text, timeline, enabled=use_python_exec)
            except Exception:
                pass
            post_files = _maybe_generate_files(raw_user_input, full_text, enabled=use_file_gen)
            if post_files:
                full_text += post_files
            identity_guard = _apply_identity_guard(raw_user_input, full_text, timeline)
            guarded_text = identity_guard.get("text", full_text)
            provenance_guard = _apply_provenance_guard(raw_user_input, guarded_text, timeline)
            guarded_text = provenance_guard.get("text", guarded_text)
            if guarded_text != full_text:
                full_text = guarded_text
                yield {"token": "", "done": False, "phase": "reflection_replace", "full_text": full_text}
            if should_cache(planner_input, route) and full_text.strip():
                try:
                    set_cached(planner_input, effective_model, profile_name, full_text)
                except Exception:
                    pass
            persona_meta = observe_dialogue(
                dialog_id=run["run_id"],
                session_id=str(session_id or run["run_id"]),
                profile_name=profile_name,
                model_name=effective_model,
                user_input=raw_user_input,
                answer_text=full_text,
                route=route,
                outcome_ok=True,
            )
            meta = {
                "model_name": effective_model,
                "profile_name": profile_name,
                "route": route,
                "tools": selected,
                "run_id": run["run_id"],
                "persona": persona_meta,
                "temporal": temporal,
                "web_plan": web_plan,
                "identity_guard": identity_guard if identity_guard.get("changed") else None,
                "provenance_guard": provenance_guard if provenance_guard.get("changed") else None,
            }
            _HISTORY.finish_run(run["run_id"], {"ok": True, "answer": full_text, "meta": meta})
            _record_agent_os_monitoring(
                agent_id=_effective_agent_id,
                run_id=run["run_id"],
                route=route,
                model_name=effective_model,
                ok=True,
                duration_ms=int((_time.monotonic() - _agent_start) * 1000),
                streaming=True,
                num_ctx=num_ctx,
                selected_tools=selected,
            )
            _emit_agent_os_event(
                event_type="agent.run.completed",
                source_agent_id=_effective_agent_id,
                payload={
                    "run_id": run["run_id"],
                    "profile_name": profile_name,
                    "route": route,
                    "ok": True,
                    "model_used": effective_model,
                    "duration_ms": int((_time.monotonic() - _agent_start) * 1000),
                    "session_id": str(session_id or ""),
                    "streaming": True,
                },
            )
            yield {"token": "", "done": True, "full_text": full_text, "meta": meta, "timeline": timeline}
        else:
            # РўСЏР¶С‘Р»С‹Р№ РїСѓС‚СЊ вЂ” reflection Рё/РёР»Рё РіРµРЅРµСЂР°С†РёСЏ С„Р°Р№Р»РѕРІ
            if should_reflect and full_text.strip() and not has_generated_files:
                yield {"token": "", "done": False, "phase": "reflecting", "message": "РџСЂРѕРІРµСЂСЏСЋ..."}
                try:
                    ref = run_reflection_loop(model_name=effective_model, profile_name=profile_name, user_input=raw_user_input, draft_text=full_text, review_text="РЈР»СѓС‡С€Рё.", context=ctx)
                    refined = ref.get("answer", "")
                    if refined and refined != full_text:
                        full_text = refined
                        yield {"token": "", "done": False, "phase": "reflection_replace", "full_text": refined}
                except Exception:
                    pass

            try:
                full_text = _maybe_auto_exec_python(raw_user_input, full_text, timeline, enabled=use_python_exec)
            except Exception:
                pass

            if needs_file_gen:
                yield {"token": "", "done": False, "phase": "generating_file", "message": "Р“РѕС‚РѕРІР»СЋ С„Р°Р№Р»..."}
            post_files = _maybe_generate_files(raw_user_input, full_text, enabled=use_file_gen)
            if post_files:
                full_text += post_files

            identity_guard = _apply_identity_guard(raw_user_input, full_text, timeline)
            guarded_text = identity_guard.get("text", full_text)
            provenance_guard = _apply_provenance_guard(raw_user_input, guarded_text, timeline)
            guarded_text = provenance_guard.get("text", guarded_text)
            if guarded_text != full_text:
                full_text = guarded_text
                yield {"token": "", "done": False, "phase": "reflection_replace", "full_text": full_text}

            # РљСЌС€РёСЂСѓРµРј РїРѕСЃР»Рµ РІСЃРµС… РїРѕСЃС‚-РѕР±СЂР°Р±РѕС‚РѕРє
            if should_cache(planner_input, route) and full_text.strip():
                try:
                    set_cached(planner_input, effective_model, profile_name, full_text)
                except Exception:
                    pass

            persona_meta = observe_dialogue(
                dialog_id=run["run_id"],
                session_id=str(session_id or run["run_id"]),
                profile_name=profile_name,
                model_name=effective_model,
                user_input=raw_user_input,
                answer_text=full_text,
                route=route,
                outcome_ok=True,
            )
            meta = {
                "model_name": effective_model,
                "profile_name": profile_name,
                "route": route,
                "tools": selected,
                "run_id": run["run_id"],
                "persona": persona_meta,
                "temporal": temporal,
                "web_plan": web_plan,
                "identity_guard": identity_guard if identity_guard.get("changed") else None,
                "provenance_guard": provenance_guard if provenance_guard.get("changed") else None,
            }
            _HISTORY.finish_run(run["run_id"], {"ok": True, "answer": full_text, "meta": meta})
            _record_agent_os_monitoring(
                agent_id=_effective_agent_id,
                run_id=run["run_id"],
                route=route,
                model_name=effective_model,
                ok=True,
                duration_ms=int((_time.monotonic() - _agent_start) * 1000),
                streaming=True,
                num_ctx=num_ctx,
                selected_tools=selected,
            )
            _emit_agent_os_event(
                event_type="agent.run.completed",
                source_agent_id=_effective_agent_id,
                payload={
                    "run_id": run["run_id"],
                    "profile_name": profile_name,
                    "route": route,
                    "ok": True,
                    "model_used": effective_model,
                    "duration_ms": int((_time.monotonic() - _agent_start) * 1000),
                    "session_id": str(session_id or ""),
                    "streaming": True,
                },
            )
            yield {"token": "", "done": True, "full_text": full_text, "meta": meta, "timeline": timeline}
    except Exception as exc:
        _HISTORY.finish_run(run["run_id"], {"ok": False, "error": str(exc)})
        _record_agent_os_monitoring(
            agent_id=_effective_agent_id,
            run_id=run["run_id"],
            route=locals().get("route", ""),
            model_name=locals().get("effective_model", model_name),
            ok=False,
            duration_ms=int((_time.monotonic() - _agent_start) * 1000),
            streaming=True,
            num_ctx=num_ctx,
            selected_tools=locals().get("selected", []),
        )
        _emit_agent_os_event(
            event_type="agent.run.completed",
            source_agent_id=_effective_agent_id,
            payload={
                "run_id": run["run_id"],
                "profile_name": profile_name,
                "route": locals().get("route", ""),
                "ok": False,
                "model_used": locals().get("effective_model", model_name),
                "duration_ms": int((_time.monotonic() - _agent_start) * 1000),
                "error": str(exc)[:500],
                "session_id": str(session_id or ""),
                "streaming": True,
            },
        )
        yield {"token": "", "done": True, "error": str(exc), "full_text": ""}
