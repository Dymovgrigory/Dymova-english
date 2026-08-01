"""Синхронизация внешних источников (VK, Яндекс.Карты, Telegram) в документы KB.

Собирает «живые» документы из публичных страниц школы и складывает их в
модульный список (get_source_documents) + JSON-кэш на диске. Слияние этого
списка с живыми документами site_sync выполняет вызывающая сторона —
модуль намеренно не трогает kb.set_live_documents, чтобы не затирать
документы сайта.

Устойчивость:
- все три источника скачиваются конкурентно (asyncio.gather);
- при ошибке сети/разметки источник возвращает [] и пишет warning в лог;
- если источник не ответил, подставляются его документы из дискового кэша;
- после успешной синхронизации кэш перезаписывается свежими документами.

Разметка подтверждена живыми запросами (авг 2026):
- Яндекс.Карты: aria-label="Оценка 5 Из 5", «58 оценок», «37 отзывов»,
  отзывы — <div class="business-review-view" itemProp="review"> с
  itemProp="reviewBody" и <span class=" spoiler-view__text-container">текст</span>.
- DuckDuckGo — см. app.web.
- t.me/s/<канал>: <div class="tgme_widget_message_text ...">текст поста</div>.
- VK: анонимно отдаёт анти-бот стену с части IP; парсер ориентирован на
  классы wall_post_text / post_text / wi_body / pi_text (десктоп и m.vk.com).
"""
from __future__ import annotations

import asyncio
import html as html_mod
import json
import logging
import re
from pathlib import Path

import httpx

from app.knowledge.kb import Document, _tokens
from app.sources_config import get_sources_settings

logger = logging.getLogger(__name__)

_TIMEOUT = 10
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
}

_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)

# Ограничения на текст поста/отзыва
_POST_MIN = 80
_POST_MAX = 600
_MAX_POSTS = 10
_REVIEW_MAX = 400
_MAX_REVIEWS = 5

_SOURCE_NAMES = ("vk", "ymaps", "telegram")

# Документы последней успешной синхронизации (или из кэша).
_source_documents: list[Document] = []


def get_source_documents() -> list[Document]:
    """Документы внешних источников из последней синхронизации (копия)."""
    return list(_source_documents)


def _default_cache_path() -> Path:
    # bot/app/knowledge/sources.py -> bot/data/sources_cache.json
    return Path(__file__).resolve().parents[2] / "data" / "sources_cache.json"


def _cache_path() -> Path:
    raw = get_sources_settings().SOURCES_CACHE_FILE
    return Path(raw) if raw else _default_cache_path()


def _clean(fragment: str) -> str:
    fragment = _BR_RE.sub(" ", fragment)
    text = _TAG_RE.sub(" ", fragment)
    text = html_mod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _make_doc(category: str, title: str, text: str) -> Document:
    doc = Document(category=category, title=title, text=text)
    doc.tokens = set(_tokens(f"{title} {text}"))
    return doc


def _doc_to_dict(doc: Document) -> dict:
    return {"category": doc.category, "title": doc.title, "text": doc.text}


def _docs_from_dicts(items: list[dict]) -> list[Document]:
    docs: list[Document] = []
    for item in items or []:
        try:
            text = (item.get("text") or "").strip()
            if not text:
                continue
            docs.append(_make_doc(item.get("category", "sources"),
                                  item.get("title", "Источник"), text))
        except Exception:
            continue
    return docs


def _load_cache() -> dict[str, list[dict]]:
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if isinstance(v, list)}
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.warning("sources: не удалось прочитать кэш %s: %s", _cache_path(), exc)
    return {}


def _save_cache(docs_by_source: dict[str, list[Document]]) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {name: [_doc_to_dict(d) for d in docs] for name, docs in docs_by_source.items()}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as exc:
        logger.warning("sources: не удалось записать кэш %s: %s", path, exc)


def _fit_post(text: str) -> str | None:
    """Приводит текст поста к диапазону 80–600 символов или отбраковывает."""
    text = text.strip()
    if len(text) > _POST_MAX:
        text = text[:_POST_MAX].rsplit(" ", 1)[0].rstrip(" ,.;:—-") + "…"
    if len(text) < _POST_MIN:
        return None
    return text


# ---------- VK ----------

_VK_POST_RE = re.compile(
    r'<div\b[^>]*class="[^"]*(?:wall_post_text|post_text|pi_text)[^"]*"[^>]*>(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)


def extract_vk_posts(page_html: str) -> list[str]:
    """Тексты последних постов со стены группы VK (до 10 штук)."""
    posts: list[str] = []
    seen: set[str] = set()
    for fragment in _VK_POST_RE.findall(page_html or ""):
        text = _fit_post(_clean(fragment))
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        posts.append(text)
        if len(posts) >= _MAX_POSTS:
            break
    return posts


async def _fetch_vk(client: httpx.AsyncClient) -> list[Document]:
    url = get_sources_settings().VK_GROUP_URL
    resp = await client.get(url)
    resp.raise_for_status()
    posts = extract_vk_posts(resp.text)
    if not posts:
        logger.warning("sources: VK — посты не найдены в разметке (%s)", url)
        return []
    return [_make_doc("vk", "VK Фоксинбург: пост", p) for p in posts]


# ---------- Яндекс.Карты ----------

_YM_RATING_LABEL_RE = re.compile(r'aria-label="Оценка\s+([\d]+[,\.]?[\d]*)\s+Из\s+5"', re.IGNORECASE)
_YM_RATING_JSON_RE = re.compile(r'"ratingValue"\s*:\s*"?([\d]+[,\.]?[\d]*)"?')
_YM_RATING_OG_RE = re.compile(r"Рейтинг\s+([\d]+[,\.]?[\d]*)")
_YM_SCORES_RE = re.compile(r"([\d][\d\s]*)\s+оценок")
_YM_REVIEWS_COUNT_RE = re.compile(r"([\d][\d\s]*)\s+отзыв")
_YM_REVIEW_BODY_RE = re.compile(
    r'itemProp="reviewBody"[^>]*>(.*?)(?:<div class="business-review-view__actions"|</main)',
    re.IGNORECASE | re.DOTALL,
)
_YM_REVIEW_TEXT_RE = re.compile(
    r'spoiler-view__text-container">(.*?)</span>', re.IGNORECASE | re.DOTALL
)


def parse_ymaps(page_html: str) -> dict | None:
    """Извлекает рейтинг, число оценок/отзывов и тексты отзывов.

    Возвращает {"rating", "scores", "reviews_count", "reviews": [...]}
    или None, если разметка не поддалась.
    """
    html = page_html or ""
    rating = None
    for rx in (_YM_RATING_LABEL_RE, _YM_RATING_JSON_RE, _YM_RATING_OG_RE):
        m = rx.search(html)
        if m:
            rating = m.group(1).replace(",", ".")
            break

    def _count(rx: re.Pattern) -> int | None:
        m = rx.search(html)
        if not m:
            return None
        try:
            return int(m.group(1).replace(" ", "").replace("\xa0", ""))
        except ValueError:
            return None

    scores = _count(_YM_SCORES_RE)
    reviews_count = _count(_YM_REVIEWS_COUNT_RE)

    reviews: list[str] = []
    for body in _YM_REVIEW_BODY_RE.findall(html):
        m = _YM_REVIEW_TEXT_RE.search(body)
        text = _clean(m.group(1)) if m else _clean(body)
        if not text:
            continue
        if len(text) > _REVIEW_MAX:
            text = text[:_REVIEW_MAX].rsplit(" ", 1)[0].rstrip(" ,.;:—-") + "…"
        if len(text) < 20:
            continue
        reviews.append(text)
        if len(reviews) >= _MAX_REVIEWS:
            break

    if rating is None and not reviews:
        return None
    return {
        "rating": rating,
        "scores": scores,
        "reviews_count": reviews_count,
        "reviews": reviews,
    }


def _ymaps_text(data: dict) -> str:
    parts = []
    if data.get("rating"):
        chunk = f"Рейтинг {data['rating']} из 5"
        if data.get("scores"):
            chunk += f" ({data['scores']} оценок"
            if data.get("reviews_count"):
                chunk += f", {data['reviews_count']} отзывов"
            chunk += ")"
        elif data.get("reviews_count"):
            chunk += f", {data['reviews_count']} отзывов"
        parts.append(chunk + ".")
    if data.get("reviews"):
        parts.append("Отзывы: " + " | ".join(data["reviews"]))
    return " ".join(parts)


async def _fetch_ymaps(client: httpx.AsyncClient) -> list[Document]:
    url = get_sources_settings().YANDEX_MAPS_URL
    resp = await client.get(url)
    resp.raise_for_status()
    data = parse_ymaps(resp.text)
    if not data:
        logger.warning("sources: Яндекс.Карты — разметка не поддалась (%s)", url)
        return []
    return [_make_doc("ymaps", "Яндекс.Карты: рейтинг и отзывы Фоксинбург",
                      _ymaps_text(data))]


# ---------- Telegram ----------

_TG_POST_RE = re.compile(
    r'<div\b[^>]*class="[^"]*tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)


def extract_tg_posts(page_html: str) -> list[str]:
    """Тексты последних постов публичного Telegram-канала (до 10 штук)."""
    posts: list[str] = []
    seen: set[str] = set()
    for fragment in _TG_POST_RE.findall(page_html or ""):
        text = _fit_post(_clean(fragment))
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        posts.append(text)
        if len(posts) >= _MAX_POSTS:
            break
    return posts


async def _fetch_telegram(client: httpx.AsyncClient) -> list[Document]:
    url = get_sources_settings().TELEGRAM_CHANNEL_URL
    resp = await client.get(url)
    resp.raise_for_status()
    posts = extract_tg_posts(resp.text)
    if not posts:
        logger.warning("sources: Telegram — посты не найдены (%s)", url)
        return []
    return [_make_doc("telegram", "Telegram Фоксинбург: пост", p) for p in posts]


# ---------- оркестратор ----------

async def sync_sources(kb=None) -> int:
    """Обновляет документы внешних источников. Возвращает их число.

    Параметр kb зарезервирован под интеграцию с KnowledgeBase — слияние
    с живыми документами сайта выполняет вызывающая сторона через
    get_source_documents(), поэтому здесь kb не используется.
    """
    del kb  # см. docstring
    global _source_documents
    if not get_sources_settings().SOURCES_SYNC_ENABLED:
        logger.info("sources: синхронизация отключена (SOURCES_SYNC_ENABLED=false)")
        return len(_source_documents)

    cache = _load_cache()
    docs_by_source: dict[str, list[Document]] = {}
    got_fresh = False

    async with httpx.AsyncClient(
        timeout=_TIMEOUT, follow_redirects=True, headers=_HEADERS
    ) as client:
        results = await asyncio.gather(
            _fetch_vk(client),
            _fetch_ymaps(client),
            _fetch_telegram(client),
            return_exceptions=True,
        )

    for name, result in zip(_SOURCE_NAMES, results):
        if isinstance(result, BaseException):
            logger.warning("sources: источник %s завершился ошибкой: %s", name, result)
            result = []
        if result:
            docs_by_source[name] = result
            got_fresh = True
        else:
            cached = _docs_from_dicts(cache.get(name, []))
            if cached:
                logger.info("sources: %s — беру %d документов из кэша", name, len(cached))
            docs_by_source[name] = cached

    if got_fresh:
        _save_cache(docs_by_source)

    _source_documents = [d for name in _SOURCE_NAMES for d in docs_by_source[name]]
    logger.info("sources: собрано %d документов из внешних источников "
                "(vk=%d, ymaps=%d, telegram=%d)",
                len(_source_documents),
                len(docs_by_source["vk"]),
                len(docs_by_source["ymaps"]),
                len(docs_by_source["telegram"]))
    return len(_source_documents)
