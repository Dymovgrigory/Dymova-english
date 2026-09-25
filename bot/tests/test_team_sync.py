"""Парсер блока команды с сайта dymova-english.ru."""
import json

import httpx
import pytest

from app.config import settings
from app.knowledge import team_sync

# Вырезка реальной разметки #fxb-team (сайт, 2026-09-25), с намеренно
# добавленным соседним блоком #fxb-lang — парсер должен остановиться
# до него и не превратить его карточки в мусорных «педагогов».
FIXTURE_HTML = """
<div id="fxb-team">
  <div class="fxb-section">
    <div class="fxb-grid">
      <article class="fxb-card">
        <div class="fxb-photo" style="background-image:url(/team-media/salyahova.webp)"></div>
        <div class="fxb-body">
          <span class="fxb-role fxb-r-teacher">Педагог</span>
          <h3>Саляхова Алина</h3>
          <p>Педагог английского и немецкого языков</p>
          <div class="fxb-btns">
            <button class="fxb-vbtn" type="button" data-video="/team-media/salyahova.mp4">Видеовизитка</button>
            <button class="fxb-vbtn fxb-vbtn-2" type="button" data-video="/team-media/salyahova_lesson.mp4">Фрагмент урока</button>
          </div>
        </div>
      </article>

      <article class="fxb-card">
        <div class="fxb-photo" style="background-image:url(/team-media/anokhin.webp)"></div>
        <div class="fxb-body">
          <span class="fxb-role fxb-r-teacher">Педагог</span>
          <h3>Анохин Роман</h3>
          <p>Педагог английского языка</p>
          <div class="fxb-btns">
            <button class="fxb-vbtn" type="button" data-video="/team-media/anokhin.mp4">Видеовизитка</button>
            <button class="fxb-vbtn fxb-vbtn-2" type="button" data-video="">Фрагмент урока</button>
          </div>
        </div>
      </article>

      <article class="fxb-card">
        <div class="fxb-photo" style="background-image:url(/team-media/sporyhina.webp)"></div>
        <div class="fxb-body">
          <span class="fxb-role">Педагог испанского языка</span>
          <h3>Спорыхина Анастасия</h3>
          <p>Педагог испанского языка</p>
        </div>
      </article>

      <article class="fxb-card">
        <div class="fxb-body">
          <span class="fxb-role fxb-r-admin">Администратор</span>
          <h3>Джанузакова Салтанат</h3>
          <p>Поможет с расписанием и записью</p>
        </div>
      </article>

      <article class="fxb-card">
        <div class="fxb-photo" style="background-image:url(/team-media/ivanov.webp)"></div>
        <div class="fxb-body">
          <span class="fxb-role fxb-r-teacher">Педагог</span>
          <h3>Иванов Сергей</h3>
          <p>Педагог французского языка</p>
          <div class="fxb-btns">
            <button class="fxb-vbtn" type="button" data-video="/team-media/ivanov.mp4">Видеовизитка</button>
          </div>
        </div>
      </article>
    </div>
  </div>
</div>

<div id="fxb-lang">
  <div class="fxb-grid">
    <article class="fxb-card fxb-de">
      <div class="fxb-body">
        <div class="fxb-teacher">
          <div class="fxb-teacher-photo" style="background:linear-gradient(135deg,#7b4fc0,#662d92)"></div>
          <div>
            <h3>Саляхова Алина</h3>
            <span class="fxb-role">Педагог немецкого языка</span>
          </div>
        </div>
      </div>
    </article>
  </div>
</div>
"""

ORIGIN = "https://dymova-english.ru"


def test_parses_all_team_cards_only():
    people = team_sync.parse_team_html(FIXTURE_HTML, ORIGIN)
    assert [p["name"] for p in people] == [
        "Саляхова Алина", "Анохин Роман", "Спорыхина Анастасия", "Джанузакова Салтанат", "Иванов Сергей",
    ]


def test_photo_and_video_urls_are_absolute():
    people = team_sync.parse_team_html(FIXTURE_HTML, ORIGIN)
    salyahova = people[0]
    assert salyahova["photo"] == "https://dymova-english.ru/team-media/salyahova.webp"
    assert salyahova["video_intro"] == "https://dymova-english.ru/team-media/salyahova.mp4"
    assert salyahova["video_lesson"] == "https://dymova-english.ru/team-media/salyahova_lesson.mp4"


def test_missing_second_video_is_empty_not_crash():
    anokhin = team_sync.parse_team_html(FIXTURE_HTML, ORIGIN)[1]
    assert anokhin["video_intro"] == "https://dymova-english.ru/team-media/anokhin.mp4"
    assert anokhin["video_lesson"] == ""


def test_card_without_photo_or_video_block_survives():
    admin = team_sync.parse_team_html(FIXTURE_HTML, ORIGIN)[3]
    assert admin["name"] == "Джанузакова Салтанат"
    assert admin["role"] == "Администратор"
    assert admin["photo"] == ""
    assert admin["video_intro"] == "" and admin["video_lesson"] == ""


def test_role_without_modifier_class_still_read():
    sporyhina = team_sync.parse_team_html(FIXTURE_HTML, ORIGIN)[2]
    assert sporyhina["role"] == "Педагог испанского языка"
    assert sporyhina["about"] == "Педагог испанского языка"


def test_lang_block_cards_never_leak_into_team():
    people = team_sync.parse_team_html(FIXTURE_HTML, ORIGIN)
    # #fxb-lang не должен дать шестого человека с role="Педагог немецкого языка"
    # без about/фото — это была бы карточка-мусор поверх настоящей Саляховой.
    assert len(people) == 5


def test_single_video_button_no_second_video():
    ivanov = team_sync.parse_team_html(FIXTURE_HTML, ORIGIN)[4]
    assert ivanov["name"] == "Иванов Сергей"
    assert ivanov["video_intro"] == "https://dymova-english.ru/team-media/ivanov.mp4"
    assert ivanov["video_lesson"] == ""


def test_is_teacher_matches_role_variants():
    assert team_sync._is_teacher("Педагог") is True
    assert team_sync._is_teacher("Педагог немецкого языка") is True
    assert team_sync._is_teacher("Администратор") is False
    assert team_sync._is_teacher("Руководитель школы") is False


def test_empty_html_returns_empty_list():
    assert team_sync.parse_team_html("<html></html>", ORIGIN) == []


@pytest.fixture(autouse=True)
def _reset_team_cache():
    team_sync._TEAM_CACHE = None
    yield
    team_sync._TEAM_CACHE = None


def test_get_team_falls_back_to_yaml_when_nothing_synced_yet(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TEAM_SNAPSHOT_PATH", str(tmp_path / "missing.json"))
    people = team_sync.get_team()
    # data.yaml реально существует в репозитории и содержит команду —
    # значит фолбэк не пустой.
    assert len(people) > 0
    assert all("name" in p for p in people)


def test_get_team_reads_snapshot_from_disk_after_restart(tmp_path, monkeypatch):
    snapshot = tmp_path / "team_snapshot.json"
    snapshot.write_text(json.dumps([{"name": "Тест Тестов", "role": "Педагог",
                                     "about": "", "photo": "", "video_intro": "",
                                     "video_lesson": ""}]), encoding="utf-8")
    monkeypatch.setattr(settings, "TEAM_SNAPSHOT_PATH", str(snapshot))
    people = team_sync.get_team()
    assert people == [{"name": "Тест Тестов", "role": "Педагог", "about": "",
                       "photo": "", "video_intro": "", "video_lesson": ""}]


@pytest.mark.asyncio
async def test_sync_once_writes_snapshot_and_updates_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TEAM_SYNC_URL", "https://dymova-english.ru")
    monkeypatch.setattr(settings, "TEAM_SNAPSHOT_PATH", str(tmp_path / "team_snapshot.json"))

    async def fake_get(self, url, **kwargs):
        return httpx.Response(200, text=FIXTURE_HTML, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    count = await team_sync.sync_once()
    assert count == 5
    assert json.loads((tmp_path / "team_snapshot.json").read_text(encoding="utf-8"))
    assert team_sync.get_team()[0]["name"] == "Саляхова Алина"


@pytest.mark.asyncio
async def test_sync_once_network_failure_keeps_previous_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TEAM_SNAPSHOT_PATH", str(tmp_path / "team_snapshot.json"))
    team_sync._TEAM_CACHE = [{"name": "Старые Данные", "role": "", "about": "",
                              "photo": "", "video_intro": "", "video_lesson": ""}]

    async def fake_get(self, url, **kwargs):
        raise httpx.ConnectError("сеть недоступна", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    count = await team_sync.sync_once()
    assert count == 0
    assert team_sync.get_team()[0]["name"] == "Старые Данные"


@pytest.mark.asyncio
async def test_sync_once_empty_parse_keeps_previous_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TEAM_SNAPSHOT_PATH", str(tmp_path / "team_snapshot.json"))
    team_sync._TEAM_CACHE = [{"name": "Старые Данные", "role": "", "about": "",
                              "photo": "", "video_intro": "", "video_lesson": ""}]

    async def fake_get(self, url, **kwargs):
        return httpx.Response(200, text="<html>совсем не та страница</html>",
                              request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    count = await team_sync.sync_once()
    assert count == 0
    assert team_sync.get_team()[0]["name"] == "Старые Данные"
