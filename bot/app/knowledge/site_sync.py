"""Живая синхронизация базы знаний с сайтом dymova-english.ru.

Периодически скачивает страницы сайта, разбивает их на текстовые фрагменты
и добавляет в KB как «живые» документы (категория site). Бот отвечает по
актуальному содержимому сайта, даже если data.yaml ещё не обновлён.

При ошибке сети предыдущие живые документы сохраняются — бот не «слепнет».
"""
from __future__ import annotations

import html as html_mod
import logging
import re

import httpx

from app.config import settings
from app.knowledge.kb import Document, _tokens, get_kb

logger = logging.getLogger(__name__)

_BLOCK_SPLIT_RE = re.compile(r"</(?:p|div|li|h[1-6]|section|article|td|tr)>", re.IGNORECASE)
_DROP_RE = re.compile(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

_MIN_CHUNK = 60
_MAX_CHUNK = 700
_MAX_CHUNKS_PER_PAGE = 80


def _clean(fragment: str) -> str:
    text = _TAG_RE.sub(" ", fragment)
    text = html_mod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_chunks(html: str) -> tuple[str, list[str]]:
    """Возвращает (заголовок страницы, список текстовых фрагментов)."""
    m = _TITLE_RE.search(html)
    title = _clean(m.group(1)) if m else ""
    html = _DROP_RE.sub(" ", html)
    chunks: list[str] = []
    seen: set[str] = set()
    for fragment in _BLOCK_SPLIT_RE.split(html):
        text = _clean(fragment)
        if not (_MIN_CHUNK <= len(text) <= _MAX_CHUNK):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        chunks.append(text)
        if len(chunks) >= _MAX_CHUNKS_PER_PAGE:
            break
    return title, chunks


def _sync_urls() -> list[str]:
    raw = settings.SITE_SYNC_URLS or ""
    urls = [u.strip() for u in raw.split(",") if u.strip()]
    return urls or ["https://dymova-english.ru"]


async def sync_once() -> int:
    """Скачивает страницы и обновляет живые документы KB. Возвращает их число."""
    docs: list[Document] = []
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        for url in _sync_urls():
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("site_sync: не удалось скачать %s: %s", url, exc)
                continue
            title, chunks = extract_chunks(resp.text)
            page_title = title or url
            for chunk in chunks:
                doc = Document(category="site", title=f"Сайт: {page_title}", text=chunk)
                doc.tokens = set(_tokens(f"{page_title} {chunk}"))
                docs.append(doc)
    if docs:
        get_kb().set_live_documents(docs)
        logger.info("site_sync: обновлено %s живых документов с сайта", len(docs))
    else:
        logger.warning("site_sync: ни одного документа не получено — оставляю прежние")
    return len(docs)
