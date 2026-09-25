"""Разбираем блок «Команда» с сайта школы — список педагогов с фото и видео."""
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
# `<div id="fxb-...">`, который всегда открывается в начале строки (после `\n`).
# Ограничиваться нужно строго: сразу после команды идёт блок «Другие языки»
# с ДРУГОЙ разметкой карточек (fxb-teacher-photo, не fxb-photo) — без границы
# туда попадёт мусор поверх настоящих карточек. Требование `\n` перед границей
# защищает от вложенных элементов со своим id внутри блока команды.
_TEAM_BLOCK_RE = re.compile(r'<div id="fxb-team">(.*?)\n<div id="fxb-', re.DOTALL)
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


def teaching_groups(site_name: str) -> list[str]:
    """Активные группы этого педагога. Сопоставление по фамилии: на сайте
    имя «Фамилия Имя», group_teacher() отдаёт «Имя Фамилия» — фамилия у
    неё последним словом."""
    from app.platform import bot_bridge, booking

    words = (site_name or "").split()
    if not words:
        return []
    surname = words[0].lower()
    out: list[str] = []
    for group in bot_bridge.active_groups():
        teacher = booking.group_teacher(group["id"], group.get("caption", ""))
        teacher_words = teacher.split()
        if teacher_words and teacher_words[-1].lower() == surname:
            out.append(group.get("caption", ""))
    return out


_TEAM_CACHE: list[dict] | None = None


def _snapshot_path() -> Path:
    return Path(settings.TEAM_SNAPSHOT_PATH)


def _load_snapshot() -> list[dict]:
    path = _snapshot_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        logger.warning("team_sync: снимок на диске повреждён — игнорирую")
        return []


def _save_snapshot(people: list[dict]) -> None:
    path = _snapshot_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(people, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logger.warning("team_sync: не удалось сохранить снимок на диск", exc_info=True)


def _yaml_fallback() -> list[dict]:
    """Последняя линия обороны: список из data.yaml, если ни разу не
    удалось синхронизироваться и снимка на диске нет (холодный старт без
    сети)."""
    from app.knowledge.kb import get_kb

    return list(get_kb().raw.get("team", []))


def get_team() -> list[dict]:
    """Текущий список команды: память → снимок на диске → data.yaml."""
    global _TEAM_CACHE
    if _TEAM_CACHE is not None:
        return _TEAM_CACHE
    from_disk = _load_snapshot()
    if from_disk:
        _TEAM_CACHE = from_disk
        return _TEAM_CACHE
    return _yaml_fallback()


async def sync_once() -> int:
    """Скачивает и обновляет команду. Возвращает число людей (0 — сбой,
    прежний снимок не трогаем, мини-приложение не остаётся пустым)."""
    global _TEAM_CACHE
    url = settings.TEAM_SYNC_URL.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except Exception as exc:
        logger.warning("team_sync: не удалось скачать %s: %s", url, exc)
        return 0
    people = parse_team_html(resp.text, url)
    for person in people:
        person["teaching"] = teaching_groups(person["name"]) if _is_teacher(person["role"]) else []
    if not people:
        logger.warning("team_sync: на странице %s не нашлось карточек команды — оставляю прежние", url)
        return 0
    _TEAM_CACHE = people
    _save_snapshot(people)
    logger.info("team_sync: обновлено %s карточек команды", len(people))
    return len(people)
