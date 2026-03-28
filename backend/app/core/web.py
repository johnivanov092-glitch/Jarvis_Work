"""web.py — мульти-поиск + параллельная загрузка страниц."""
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Iterable
from urllib.parse import quote, urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

from .files import truncate_text

import json as _json

# Yandex оставлен в _ENGINE_FUNCS но убран из дефолтов (дублирует SearXNG, часто блокирует)
DEFAULT_SEARCH_ENGINES = ("duckduckgo", "searxng", "wikipedia", "bing", "google")
_ENGINE_LABELS = {
    "duckduckgo": "DuckDuckGo",
    "bing": "Bing",
    "google": "Google",
    "yandex": "Yandex",
    "searxng": "SearXNG",
    "wikipedia": "Wikipedia",
}

# ── SearXNG ──
# Публичные инстансы SearXNG (fallback-цепочка).
# Можно переопределить через переменную окружения SEARXNG_URL.
import os as _os
_SEARXNG_INSTANCES = [
    _os.environ.get("SEARXNG_URL", ""),
    "https://search.sapti.me",
    "https://searx.tiekoetter.com",
    "https://search.bus-hit.me",
    "https://searxng.site",
]
_SEARXNG_INSTANCES = [u for u in _SEARXNG_INSTANCES if u]  # убираем пустые


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    })
    return s


def _clean_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("/url?"):
        try:
            q = parse_qs(urlparse(url).query)
            url = q.get("q", [url])[0]
        except Exception:
            pass
    if url.startswith("http://www.google.com/url?") or url.startswith("https://www.google.com/url?"):
        try:
            q = parse_qs(urlparse(url).query)
            url = q.get("q", [url])[0]
        except Exception:
            pass
    return unquote(url)


def _dedupe_results(results: Iterable[Dict[str, str]], max_results: int) -> List[Dict[str, str]]:
    unique = []
    seen = set()
    for item in results:
        href = _clean_url(item.get("href", ""))
        title = (item.get("title", "") or "").strip()
        body = (item.get("body", "") or "").strip()
        engine = (item.get("engine", "") or "").strip()
        key = href or f"{title}|{body}"
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append({
            "title": title,
            "href": href,
            "body": body,
            "engine": engine,
        })
        if len(unique) >= max_results:
            break
    return unique


def _search_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "href": _clean_url(r.get("href", "")),
                "body": r.get("body", ""),
                "engine": "duckduckgo",
            })
    return results


def _search_bing(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    url = f"https://www.bing.com/search?q={quote(query)}&count={max_results}"
    resp = _session().get(url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for li in soup.select("li.b_algo"):
        a = li.select_one("h2 a")
        if not a:
            continue
        desc = li.select_one(".b_caption p")
        results.append({
            "title": a.get_text(" ", strip=True),
            "href": _clean_url(a.get("href", "")),
            "body": desc.get_text(" ", strip=True) if desc else "",
            "engine": "bing",
        })
        if len(results) >= max_results:
            break
    return results


def _search_google(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    url = f"https://www.google.com/search?q={quote(query)}&num={max_results}&hl=ru"
    resp = _session().get(url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if not href.startswith("/url?"):
            continue
        clean = _clean_url(href)
        if not clean.startswith("http"):
            continue
        h3 = a.select_one("h3")
        title = h3.get_text(" ", strip=True) if h3 else a.get_text(" ", strip=True)
        if not title:
            continue
        body = ""
        parent = a.find_parent()
        if parent:
            txt = parent.get_text(" ", strip=True)
            if txt and txt != title:
                body = txt.replace(title, "", 1).strip()
        results.append({
            "title": title,
            "href": clean,
            "body": truncate_text(body, 300),
            "engine": "google",
        })
        if len(results) >= max_results:
            break
    return results


def _search_yandex(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    url = f"https://yandex.ru/search/?text={quote(query)}"
    resp = _session().get(url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    selectors = [
        "li.serp-item",
        ".Organic",
    ]
    nodes = []
    for sel in selectors:
        nodes.extend(soup.select(sel))
    if not nodes:
        nodes = soup.select("a.Link")
    for node in nodes:
        a = node.select_one("a[href]") if hasattr(node, "select_one") else node
        if not a:
            continue
        href = _clean_url(a.get("href", ""))
        if not href.startswith("http"):
            continue
        title = a.get_text(" ", strip=True)
        body = ""
        if hasattr(node, "get_text"):
            txt = node.get_text(" ", strip=True)
            if txt and txt != title:
                body = txt.replace(title, "", 1).strip()
        results.append({
            "title": title,
            "href": href,
            "body": truncate_text(body, 300),
            "engine": "yandex",
        })
        if len(results) >= max_results:
            break
    return results


def _search_searxng(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Поиск через публичный SearXNG инстанс (мета-поисковик)."""
    results = []
    last_err = None
    for base_url in _SEARXNG_INSTANCES:
        try:
            url = f"{base_url.rstrip('/')}/search"
            params = {
                "q": query,
                "format": "json",
                "categories": "general",
                "language": "ru-RU",
                "pageno": 1,
            }
            resp = _session().get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for r in data.get("results", [])[:max_results]:
                href = _clean_url(r.get("url", ""))
                if not href.startswith("http"):
                    continue
                results.append({
                    "title": (r.get("title") or "").strip(),
                    "href": href,
                    "body": truncate_text((r.get("content") or "").strip(), 300),
                    "engine": "searxng",
                })
            if results:
                break  # Успех — не пробуем другие инстансы
        except Exception as e:
            last_err = e
            continue
    if not results and last_err:
        raise last_err
    return results


def _search_wikipedia(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Поиск по Wikipedia API (русская + английская)."""
    results = []
    for lang in ("ru", "en"):
        if len(results) >= max_results:
            break
        try:
            url = f"https://{lang}.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": min(max_results, 5),
                "format": "json",
                "utf8": 1,
            }
            resp = _session().get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("query", {}).get("search", []):
                title = item.get("title", "")
                # Убираем HTML-теги из snippet
                snippet = re.sub(r"<[^>]+>", "", item.get("snippet", ""))
                page_url = f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
                # Проверяем дубликаты (одна статья на двух языках)
                if any(r["title"] == title for r in results):
                    continue
                results.append({
                    "title": f"{title} (Wikipedia {lang.upper()})",
                    "href": page_url,
                    "body": snippet,
                    "engine": "wikipedia",
                })
                if len(results) >= max_results:
                    break
        except Exception:
            continue
    return results


_ENGINE_FUNCS = {
    "duckduckgo": _search_duckduckgo,
    "bing": _search_bing,
    "google": _search_google,
    "yandex": _search_yandex,
    "searxng": _search_searxng,
    "wikipedia": _search_wikipedia,
}


def search_web(query: str, max_results: int = 5, engines: Iterable[str] | None = None,
               per_engine: int | None = None) -> List[Dict[str, str]]:
    engines = list(engines or DEFAULT_SEARCH_ENGINES)
    per_engine = per_engine or max(3, max_results)
    combined = []
    errors = []
    for engine in engines:
        fn = _ENGINE_FUNCS.get(engine)
        if not fn:
            continue
        try:
            combined.extend(fn(query, max_results=per_engine))
        except Exception as e:
            errors.append({"title": f"Ошибка поиска ({engine})", "href": "", "body": str(e), "engine": engine})
    merged = _dedupe_results(combined, max_results=max_results)
    if not merged and errors:
        return errors[:max_results]
    if len(merged) < max_results and errors:
        merged.extend(errors[: max_results - len(merged)])
    return merged[:max_results]


def format_search_results(results: List[Dict[str, str]]) -> str:
    return "\n\n".join(
        f"[{i}] {item.get('title','')}\n"
        f"Поисковик: {_ENGINE_LABELS.get(item.get('engine',''), item.get('engine','') or '—')}\n"
        f"Ссылка: {item.get('href','')}\n"
        f"Описание: {item.get('body','')}"
        for i, item in enumerate(results, start=1)
    )


def fetch_page_text(url: str) -> str:
    try:
        resp = _session().get(url, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = re.sub(r"\n{2,}", "\n\n", soup.get_text("\n"))
        return truncate_text(text, 10000)
    except Exception as e:
        return f"Ошибка чтения страницы: {e}"


def research_web(query: str, max_results: int = 5, pages_to_read: int = 3,
                 engines: Iterable[str] | None = None) -> str:
    """Параллельно загружает страницы из агрегированного поиска."""
    results = search_web(query, max_results=max_results, engines=engines)
    to_fetch = [item for item in results[:pages_to_read] if item.get("href")]
    page_texts: Dict[str, str] = {}
    if to_fetch:
        with ThreadPoolExecutor(max_workers=min(len(to_fetch), 5)) as executor:
            future_map = {executor.submit(fetch_page_text, item["href"]): item["href"]
                          for item in to_fetch}
            for future in as_completed(future_map):
                url = future_map[future]
                try:
                    page_texts[url] = future.result()
                except Exception as e:
                    page_texts[url] = f"Ошибка: {e}"
    parts = ["Результаты веб-исследования:"]
    for i, item in enumerate(results[:pages_to_read], start=1):
        href = item.get("href", "")
        parts += [
            f"\n=== Источник {i} ===",
            f"Поисковик: {_ENGINE_LABELS.get(item.get('engine',''), item.get('engine','') or '—')}",
            f"Заголовок: {item.get('title','')}",
            f"Ссылка: {href}",
            f"Описание: {item.get('body','')}",
        ]
        if href and href in page_texts:
            parts += ["Текст страницы:", page_texts[href]]
    return truncate_text("\n".join(parts), 22000)
