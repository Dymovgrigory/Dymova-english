"""Живые данные о команде школы: скачиваем и парсим блок «Команда» с сайта.

Раньше список педагогов в мини-приложении жил только в data.yaml и правился
руками — на сайте уже 17 человек с актуальными фото, а в приложении
оставалось 10 устаревших. Источник истины теперь один: сайт. Ошибка сети
или парсинга не должна оставить мини-приложение без команды — остаётся
последний удачный снимок, а если снимка ещё не было (холодный старт без
сети) — data.yaml как фолбэк.
"""
from __future__ import annotations

import html as html_mod
import json
import logging
import re
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Раздел команды на сайте — от своего id до следующего соседнего блока
# `<div id="fxb-...">`. Ограничиваться нужно строго: сразу после команды
# идёт блок «Другие языки» с ДРУГОЙ разметкой карточек (fxb-teacher-photo,
# не fxb-photo) — без границы туда попадёт мусор поверх настоящих карточек.
_TEAM_BLOCK_RE = re.compile(r'<div id="fxb-team">(.*?)<div id="fxb-', re.DOTALL)
_CARD_RE = re.compile(r'<article class="fxb-card">(.*?)</article>', re.DOTALL)
_PHOTO_RE = re.compile(r'class="fxb-photo"\s+style="background-image:url\(([^)]*)\)"')
_ROLE_RE = re.compile(r'<span class="fxb-role[^"]*">([^<]*)</span>')
_NAME_RE = re.compile(r'<h3>([^<]*)</h3>')
_ABOUT_RE = re.compile(r'</h3>\s*<p>([^<]*)</p>')
# Кнопка видео: класс fxb-vbtn-2 отличает «фрагмент урока» от «видеовизитки».
_VIDEO_RE = re.compile(r'class="fxb-vbtn( fxb-vbtn-2)?"[^>]*data-video="([^"]*)"')


def _clean(text: str) -> str:
    return html_mod.unescape(text or "").strip()


def _abs_url(path: str, origin: str) -> str:
    path = (path or "").strip()
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return origin.rstrip("/") + "/" + path.lstrip("/")


def _is_teacher(role: str) -> bool:
    """Педагог — по тексту роли, не по CSS-классу: три карточки на сайте
    несут роль «Педагог немецкого языка» без модификатора fxb-r-teacher."""
    return "педагог" in (role or "").lower()


def _parse_card(card_html: str, origin: str) -> dict | None:
    name_m = _NAME_RE.search(card_html)
    if not name_m:
        return None
    name = _clean(name_m.group(1))
    if not name:
        return None
    role_m = _ROLE_RE.search(card_html)
    role = _clean(role_m.group(1)) if role_m else ""
    about_m = _ABOUT_RE.search(card_html)
    about = _clean(about_m.group(1)) if about_m else ""
    photo_m = _PHOTO_RE.search(card_html)
    photo = _abs_url(photo_m.group(1) if photo_m else "", origin)
    video_intro = ""
    video_lesson = ""
    for is_second, url in _VIDEO_RE.findall(card_html):
        resolved = _abs_url(url, origin)
        if is_second:
            video_lesson = resolved
        else:
            video_intro = resolved
    return {
        "name": name,
        "role": role,
        "about": about,
        "photo": photo,
        "video_intro": video_intro,
        "video_lesson": video_lesson,
    }


def parse_team_html(html: str, origin: str) -> list[dict]:
    """Список педагогов/сотрудников из HTML страницы. Пустой список — блок
    команды не найден или в нём нет карточек с именем (не считается ошибкой
    парсинга снаружи — вызывающий код сам решает, что делать с пустым)."""
    block_m = _TEAM_BLOCK_RE.search(html)
    if not block_m:
        return []
    block = block_m.group(1)
    people: list[dict] = []
    for card_m in _CARD_RE.finditer(block):
        person = _parse_card(card_m.group(1), origin)
        if person:
            people.append(person)
    return people
