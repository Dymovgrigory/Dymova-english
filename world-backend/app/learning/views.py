"""Модели чтения для экранов: курсы, главная, путь, словарь."""
from __future__ import annotations

from app.world import core

from . import clock, mastery, progress
from .content import Course


def courses(course: Course) -> dict:
    return {
        "books": [
            {
                "id": book.id, "title": book.title, "grade": book.grade, "cefr": book.cefr, "band": book.band,
                "modules": [
                    {"id": m.id, "order": m.order, "title_en": m.title_en, "title_ru": m.title_ru}
                    for m in course.modules_of(book.id)
                ],
            }
            for book in course.books
        ]
    }


def path(external_key: str, course: Course, book_id: str) -> dict:
    player_id = int(core.get_player(external_key)["id"])
    profile = progress.get_profile(player_id)
    statuses = progress.node_statuses(course, player_id, book_id, profile)
    done = progress.completed_nodes(player_id)
    book = course.book(book_id)
    return {
        "book": {"id": book.id, "title": book.title, "grade": book.grade, "cefr": book.cefr, "band": book.band},
        "modules": [
            {
                "id": m.id, "order": m.order, "title_en": m.title_en, "title_ru": m.title_ru,
                "nodes": [
                    {"id": n.id, "kind": n.kind, "status": statuses[n.id], "stars": done.get(n.id, {}).get("stars", 0)}
                    for n in m.nodes
                ],
            }
            for m in course.modules_of(book_id)
        ],
    }


def _current_node(course: Course, player_id: int, profile: dict) -> dict | None:
    home_grade = course.book(profile["book_id"]).grade
    for book in course.books:
        if book.grade < home_grade:
            continue
        statuses = progress.node_statuses(course, player_id, book.id, profile)
        for module, node in course.nodes_of(book.id):
            if statuses[node.id] == progress.CURRENT:
                return {"id": node.id, "kind": node.kind, "book_id": book.id, "module_id": module.id,
                        "module_title_en": module.title_en, "module_title_ru": module.title_ru}
    return None


def home(external_key: str, course: Course) -> dict:
    player = core.get_player(external_key)
    player_id = int(player["id"])
    profile = progress.get_profile(player_id)
    now = clock.now()
    today = progress.today_xp(player_id, now=now)
    return {
        "player": {"display_name": player["display_name"], "xp": player["xp"], "coins": player["coins"],
                   "level": player["level"]},
        "profile": profile,
        "streak_days": progress.streak_days(player_id, now=now),
        "today_xp": today,
        "daily_goal_xp": profile["daily_goal_xp"],
        "goal_reached": today >= profile["daily_goal_xp"],
        "current_node": _current_node(course, player_id, profile),
        "due_count": len(mastery.due_atoms(player_id, limit=99, now=now)),
    }


def words(external_key: str, course: Course, book_id: str) -> dict:
    player_id = int(core.get_player(external_key)["id"])
    done = progress.completed_nodes(player_id)
    modules = [m for m in course.modules_of(book_id) if any(n.id in done for n in m.nodes)]
    strengths = mastery.strengths(player_id, [w.id for m in modules for w in m.words])
    return {
        "modules": [
            {
                "id": m.id, "title_en": m.title_en, "title_ru": m.title_ru,
                "words": [
                    {"id": w.id, "en": w.en, "ru": w.ru, "image": w.image, "strength": strengths.get(w.id, 0)}
                    for w in m.words
                ],
            }
            for m in modules
        ]
    }
