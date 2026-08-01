"""Живой веб-поиск через HTML-версию DuckDuckGo.

Используется как запасной вариант, когда база знаний не дала уверенного
ответа: бот может подсмотреть свежую информацию в интернете.

Парсинг — простыми regex/строковыми операциями (BeautifulSoup в проекте нет).
При любой ошибке сети или парсинга возвращается пустой список — поиск
никогда не роняет диалог. Результаты кэшируются в памяти на 30 минут.

Разметка подтверждена живым запросом (авг 2026):
- ссылка результата:  <a rel="nofollow" class="result__a" href="...">тайтл</a>
- сниппет результата: <a ... class="result__snippet" href="...">текст</a>
- href иногда обёрнут в редирект //duckduckgo.com/l/?uddg=<urlencoded>
- GET с части IP отдаёт анти-бот 202 (anomaly challenge), тогда пробуем POST.
"""
from __future__ import annotations

import html as html_mod
import logging
import re
import time
import urllib.parse

import httpx

from app.sources_config import get_sources_settings

logger = logging.getLogger(__name__)

_DDG_URL = "https://html.duckduckgo.com/html/"
_TIMEOUT = 10
_CACHE_TTL_SEC = 30 * 60

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
}

_ANCHOR_RE = re.compile(r"<a\b[^>]*>.*?</a>", re.IGNORECASE | re.DOTALL)
_HREF_RE = re.compile(r'href="([^"]*)"', re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")

# query (lower) -> (timestamp, results)
_cache: dict[str, tuple[float, list[dict]]] = {}


def _clean(fragment: str) -> str:
    text = _TAG_RE.sub(" ", fragment)
    text = html_mod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _decode_ddg_url(href: str) -> str:
    """Разворачивает редирект DDG //duckduckgo.com/l/?uddg=<urlencoded>."""
    href = html_mod.unescape(href).strip()
    if "uddg=" not in href:
        return href
    try:
        parsed = urllib.parse.urlparse("https:" + href if href.startswith("//") else href)
        uddg = urllib.parse.parse_qs(parsed.query).get("uddg")
        if uddg and uddg[0]:
            return uddg[0]
    except Exception:
        pass
    return href


def parse_ddg_results(page_html: str, limit: int = 4) -> list[dict]:
    """Извлекает из HTML DDG список {"title", "url", "snippet"}."""
    results: list[dict] = []
    current: dict | None = None
    for anchor in _ANCHOR_RE.findall(page_html or ""):
        href_m = _HREF_RE.search(anchor)
        href = href_m.group(1) if href_m else ""
        inner = anchor[anchor.find(">") + 1 : anchor.rfind("<")]
        if "result__a" in anchor:
            url = _decode_ddg_url(href)
            title = _clean(inner)
            if not url or not title:
                continue
            current = {"title": title, "url": url, "snippet": ""}
            results.append(current)
        elif "result__snippet" in anchor and current is not None and not current["snippet"]:
            current["snippet"] = _clean(inner)
    return results[:limit]


def _cache_get(query: str) -> list[dict] | None:
    entry = _cache.get(query.lower())
    if not entry:
        return None
    ts, results = entry
    if time.monotonic() - ts > _CACHE_TTL_SEC:
        _cache.pop(query.lower(), None)
        return None
    return results


def _cache_put(query: str, results: list[dict]) -> None:
    if len(_cache) > 500:  # простая защита от разрастания
        _cache.clear()
    _cache[query.lower()] = (time.monotonic(), results)


async def search_web(query: str, limit: int = 4) -> list[dict]:
    """Ищет в DuckDuckGo и возвращает [{"title", "url", "snippet"}].

    Никогда не падает: при любой ошибке (сеть, анти-бот, разметка)
    возвращает пустой список.
    """
    query = (query or "").strip()
    if not query or not get_sources_settings().WEB_SEARCH_ENABLED:
        return []
    cached = _cache_get(query)
    if cached is not None:
        return cached[:limit]

    results: list[dict] = []
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, follow_redirects=True, headers=_HEADERS
        ) as client:
            try:
                resp = await client.get(_DDG_URL, params={"q": query})
            except Exception as exc:
                logger.warning("web_search: GET %s не удался: %s", _DDG_URL, exc)
                resp = None
            if resp is not None and resp.status_code == 200:
                results = parse_ddg_results(resp.text, limit=limit)
            if not results:
                # С части IP GET отдаёт анти-бот 202 — пробуем POST-форму.
                try:
                    resp = await client.post(_DDG_URL, data={"q": query})
                    if resp.status_code == 200:
                        results = parse_ddg_results(resp.text, limit=limit)
                except Exception as exc:
                    logger.warning("web_search: POST %s не удался: %s", _DDG_URL, exc)
    except Exception as exc:  # pragma: no cover - страховка верхнего уровня
        logger.warning("web_search: неожиданная ошибка: %s", exc)
        return []

    _cache_put(query, results)
    return results
