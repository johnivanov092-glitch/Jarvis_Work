"""
multi_engine_search.py — мульти-поисковый движок.

Поддержка:
  • DuckDuckGo  — через библиотеку duckduckgo_search (основной)
  • Google      — scraping через requests + BeautifulSoup
  • Yandex      — scraping yandex.kz / ya.ru
  • Bing        — scraping bing.com
  • Yahoo       — scraping search.yahoo.com

Все движки работают параллельно (ThreadPoolExecutor).
Результаты объединяются и дедуплицируются по URL.
Если движок падает — остальные продолжают работать.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Общие настройки ──────────────────────────────────────────

_TIMEOUT = 8  # секунд на каждый движок
_MAX_WORKERS = 5  # параллельные запросы

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru,en;q=0.9",
}

_YANDEX_HEADERS = {
    **_HEADERS,
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 YaBrowser/24.6.0.0 Safari/537.36"
    ),
}


# ══════════════════════════════════════════════════════════════
# Отдельные движки
# ══════════════════════════════════════════════════════════════

def _search_duckduckgo(query: str, max_results: int = 8) -> list[dict[str, Any]]:
    """DuckDuckGo через библиотеку duckduckgo_search."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return []

    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
        results = []
        for item in raw:
            url = item.get("href") or item.get("url") or ""
            if not url:
                continue
            results.append({
                "title": item.get("title", ""),
                "url": url,
                "snippet": item.get("body", ""),
                "engine": "duckduckgo",
            })
        return results
    except Exception as e:
        logger.warning(f"DuckDuckGo error: {e}")
        return []


def _search_google(query: str, max_results: int = 8) -> list[dict[str, Any]]:
    """Google scraping через requests + BeautifulSoup."""
    try:
        url = f"https://www.google.com/search?q={quote_plus(query)}&num={max_results}&hl=ru"
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        # Google result blocks
        for g in soup.select("div.g, div[data-sokoban-container]"):
            a_tag = g.select_one("a[href]")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            if not href.startswith("http"):
                continue

            title_el = g.select_one("h3")
            title = title_el.get_text(strip=True) if title_el else ""

            snippet = ""
            for sel in ["div.VwiC3b", "span.aCOpRe", "div[data-sncf]", "div.IsZvec"]:
                s = g.select_one(sel)
                if s:
                    snippet = s.get_text(strip=True)
                    break

            if title or snippet:
                results.append({
                    "title": title,
                    "url": href,
                    "snippet": snippet,
                    "engine": "google",
                })

            if len(results) >= max_results:
                break

        return results
    except Exception as e:
        logger.warning(f"Google error: {e}")
        return []


def _search_yandex(query: str, max_results: int = 8) -> list[dict[str, Any]]:
    """Yandex scraping через requests + BeautifulSoup (yandex.kz)."""
    try:
        url = f"https://yandex.kz/search/?text={quote_plus(query)}&lr=162"
        resp = requests.get(url, headers=_YANDEX_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []

        # Yandex organic results
        for item in soup.select("li.serp-item, div.serp-item"):
            a_tag = item.select_one("a[href]")
            if not a_tag:
                continue
            href = a_tag.get("href", "")

            # Yandex иногда оборачивает URL в редирект
            if "yandex.kz/clck" in href or "yandex.ru/clck" in href:
                # Пробуем извлечь реальный URL
                parsed = parse_qs(urlparse(href).query)
                real_url = parsed.get("url", parsed.get("l", [""]))[0]
                if real_url:
                    href = unquote(real_url)

            if not href.startswith("http"):
                continue

            # Title
            title = ""
            for sel in ["h2", "div.OrganicTitle-LinkText", "span.OrganicTitleContentSpan"]:
                t = item.select_one(sel)
                if t:
                    title = t.get_text(strip=True)
                    break
            if not title:
                title = a_tag.get_text(strip=True)

            # Snippet
            snippet = ""
            for sel in ["div.OrganicText", "div.text-container", "span.OrganicTextContentSpan"]:
                s = item.select_one(sel)
                if s:
                    snippet = s.get_text(strip=True)
                    break

            if title or snippet:
                results.append({
                    "title": title,
                    "url": href,
                    "snippet": snippet,
                    "engine": "yandex",
                })

            if len(results) >= max_results:
                break

        return results
    except Exception as e:
        logger.warning(f"Yandex error: {e}")
        return []


def _search_bing(query: str, max_results: int = 8) -> list[dict[str, Any]]:
    """Bing scraping через requests + BeautifulSoup."""
    try:
        url = f"https://www.bing.com/search?q={quote_plus(query)}&count={max_results}"
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []

        for li in soup.select("li.b_algo"):
            a_tag = li.select_one("h2 a[href]")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            if not href.startswith("http"):
                continue

            title = a_tag.get_text(strip=True)

            snippet = ""
            p = li.select_one("div.b_caption p, p.b_lineclamp2, p.b_lineclamp3")
            if p:
                snippet = p.get_text(strip=True)

            if title or snippet:
                results.append({
                    "title": title,
                    "url": href,
                    "snippet": snippet,
                    "engine": "bing",
                })

            if len(results) >= max_results:
                break

        return results
    except Exception as e:
        logger.warning(f"Bing error: {e}")
        return []


def _search_yahoo(query: str, max_results: int = 8) -> list[dict[str, Any]]:
    """Yahoo scraping через requests + BeautifulSoup."""
    try:
        url = f"https://search.yahoo.com/search?p={quote_plus(query)}&n={max_results}"
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []

        for item in soup.select("div.algo, div.dd"):
            a_tag = item.select_one("a[href]")
            if not a_tag:
                continue
            href = a_tag.get("href", "")

            # Yahoo оборачивает URL в редирект
            if "yahoo.com/RU=" in href or "r.search.yahoo.com" in href:
                match = re.search(r"RU=([^/]+)/", href)
                if match:
                    href = unquote(match.group(1))

            if not href.startswith("http"):
                continue

            title = ""
            h = item.select_one("h3, h3.title a")
            if h:
                title = h.get_text(strip=True)
            if not title:
                title = a_tag.get_text(strip=True)

            snippet = ""
            for sel in ["p.lh-l", "div.compText", "span.fc-falcon"]:
                s = item.select_one(sel)
                if s:
                    snippet = s.get_text(strip=True)
                    break

            if title or snippet:
                results.append({
                    "title": title,
                    "url": href,
                    "snippet": snippet,
                    "engine": "yahoo",
                })

            if len(results) >= max_results:
                break

        return results
    except Exception as e:
        logger.warning(f"Yahoo error: {e}")
        return []


# ══════════════════════════════════════════════════════════════
# Оркестратор
# ══════════════════════════════════════════════════════════════

# Реестр движков: имя → функция
_ENGINE_REGISTRY: dict[str, Any] = {
    "duckduckgo": _search_duckduckgo,
    "google": _search_google,
    "yandex": _search_yandex,
    "bing": _search_bing,
    "yahoo": _search_yahoo,
}

# Порядок по приоритету (DuckDuckGo основной — самый надёжный)
DEFAULT_ENGINES = ["duckduckgo", "google", "yandex", "bing", "yahoo"]


def multi_engine_search(
    query: str,
    engines: list[str] | None = None,
    max_results_per_engine: int = 6,
    max_total: int = 15,
) -> dict[str, Any]:
    """
    Параллельный поиск по нескольким движкам.

    Returns:
        {
            "ok": bool,
            "query": str,
            "results": [...],
            "engines_used": [...],
            "engines_failed": [...],
            "count": int,
        }
    """
    query = (query or "").strip()
    if not query:
        return {"ok": False, "query": query, "results": [], "engines_used": [], "engines_failed": [], "count": 0}

    engines = engines or DEFAULT_ENGINES
    engines_used = []
    engines_failed = []
    all_results: list[dict[str, Any]] = []

    # Параллельный запуск
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {}
        for engine_name in engines:
            func = _ENGINE_REGISTRY.get(engine_name)
            if not func:
                continue
            future = executor.submit(func, query, max_results_per_engine)
            futures[future] = engine_name

        for future in as_completed(futures, timeout=_TIMEOUT + 2):
            engine_name = futures[future]
            try:
                results = future.result(timeout=1)
                if results:
                    all_results.extend(results)
                    engines_used.append(engine_name)
                else:
                    engines_failed.append(engine_name)
            except Exception as e:
                logger.warning(f"Engine {engine_name} failed: {e}")
                engines_failed.append(engine_name)

    # Дедупликация по URL (нормализованному)
    seen_urls: set[str] = set()
    unique_results: list[dict[str, Any]] = []

    for item in all_results:
        url = (item.get("url") or "").rstrip("/").lower()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        unique_results.append(item)

    # Лимитируем
    final = unique_results[:max_total]

    return {
        "ok": bool(final),
        "query": query,
        "results": final,
        "engines_used": engines_used,
        "engines_failed": engines_failed,
        "count": len(final),
    }
