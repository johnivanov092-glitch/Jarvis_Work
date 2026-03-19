"""
web_service.py — веб-поиск через DuckDuckGo (один надёжный движок).

Упрощено: один запрос, без дублей, без таймаутов на Google/Yandex scraping.
"""
from __future__ import annotations
from typing import Any
from urllib.parse import quote_plus

DDGS = None
try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        pass


def search_web(query: str, max_results: int = 8) -> dict[str, Any]:
    """Единый поиск через DuckDuckGo. Возвращает sources + context."""
    query = (query or "").strip()
    if not query:
        return {"ok": False, "query": query, "sources": [], "engines_used": [], "context": ""}

    sources = []
    engines_used = []
    
    if DDGS is not None:
        try:
            with DDGS() as ddgs:
                raw = list(ddgs.text(query, max_results=max_results * 2))
            for item in raw:
                url = item.get("href") or item.get("url") or ""
                if not url or not url.startswith("http"):
                    continue
                title = item.get("title", "")
                snippet = item.get("body") or item.get("snippet") or ""
                sources.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "engine": "duckduckgo",
                })
            engines_used.append("duckduckgo")
        except Exception:
            pass

    # Дедупликация
    seen = set()
    unique = []
    for s in sources:
        key = s["url"].rstrip("/").lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)
    
    final = unique[:max_results]
    
    # Контекст для LLM
    context = ""
    if final:
        lines = [f"- {s['title']}: {s['snippet']} ({s['url']})" for s in final[:6]]
        context = "\n".join(lines)

    return {
        "ok": bool(final),
        "query": query,
        "sources": final,
        "engines_used": engines_used,
        "count": len(final),
        "context": context,
        "engine_links": [
            {"name": "Google", "url": f"https://www.google.com/search?q={quote_plus(query)}"},
            {"name": "Yandex", "url": f"https://yandex.kz/search/?text={quote_plus(query)}"},
            {"name": "DuckDuckGo", "url": f"https://duckduckgo.com/?q={quote_plus(query)}"},
        ],
    }


def research_web(query: str, max_results: int = 8):
    return search_web(query, max_results).get("sources", [])
