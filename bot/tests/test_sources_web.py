"""Тесты парсеров внешних источников и живого веб-поиска (без сети).

Фикстуры — реалистичные фрагменты разметки, снятые с живых страниц
(авг 2026): DDG html-версия, стена VK, t.me/s, Яндекс.Карты.
"""
import json

import httpx
import pytest

import app.web as web_module
from app import sources_config
from app.knowledge import sources as sources_module
from app.web import parse_ddg_results, search_web
from app.knowledge.sources import (
    extract_tg_posts,
    extract_vk_posts,
    get_source_documents,
    parse_ymaps,
    sync_sources,
)

# ---------- фикстуры HTML (фрагменты реальной разметки) ----------

DDG_HTML = """
<div class="result results_links results_links_deep web-result">
  <h2 class="result__title">
    <a rel="nofollow" class="result__a"
       href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fdymova-english.ru%2F&amp;rut=abc123">
       Фоксинбург — школа иностранных языков</a>
  </h2>
  <a class="result__snippet"
     href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fdymova-english.ru%2F">
     Курсы английского и китайского для детей и взрослых в Долгопрудном.</a>
</div>
<div class="result results_links web-result">
  <h2 class="result__title">
    <a rel="nofollow" class="result__a"
       href="https://yandex.ru/maps/org/foxinburg/162408588499/">
       Фоксинбург — Яндекс Карты</a>
  </h2>
  <a class="result__snippet" href="https://yandex.ru/maps/org/foxinburg/162408588499/">
     Рейтинг 5,0. 37 отзывов, 25 фото.</a>
</div>
"""

VK_HTML = """
<div id="wall_posts">
  <div class="wall_item"><div class="wi_body">
    <div class="wi_author">Фоксинбург</div>
    <div class="wall_post_text">Записываемся на сентябрь!<br>Группы для детей 7–10 лет,
    осталось 3 места. Подробности в сообщениях группы или по телефону &amp; на сайте.</div>
  </div></div>
  <div class="wall_item"><div class="wi_body">
    <div class="wall_post_text">ок</div>
  </div></div>
  <div class="wall_item"><div class="wi_body">
    <div class="wall_post_text">Записываемся на сентябрь!<br>Группы для детей 7–10 лет,
    осталось 3 места. Подробности в сообщениях группы или по телефону &amp; на сайте.</div>
  </div></div>
  <div class="wall_item"><div class="wi_body">
    <div class="wall_post_text">В субботу открытый урок для новичков: знакомство с педагогами,
    мини-тур по школе и подарки для всех гостей. Начало в 12:00, вход свободный по записи.</div>
  </div></div>
</div>
"""

TG_HTML = """
<section class="tgme_channel_history js-message_history">
  <div class="tgme_widget_message_wrap">
    <div class="tgme_widget_message text_not_supported_wrap js-widget_message">
      <div class="tgme_widget_message_text js-message_text" dir="auto">
        Летний интенсив по английскому: две недели разговорной практики,
        игры и проекты.<br/>Старт 16 июня, группа до 8 человек. Запись открыта!
      </div>
    </div>
  </div>
  <div class="tgme_widget_message_wrap">
    <div class="tgme_widget_message_text js-message_text" dir="auto">
      Поздравляем наших учеников с отличными результатами олимпиады!
      Пять призовых мест из семи — гордимся вами и благодарим педагогов за подготовку.
    </div>
  </div>
</section>
"""

YMAPS_HTML = """
<html><head>
<meta property="og:description" content="🏆 Обладатель награды «Хорошее место — 2026».
⭐️ Рейтинг 5,0. 37 отзывов, 25 фото." />
</head><body>
<div class="business-header-rating-view">
  <div class="business-rating-badge-view _size_m _weight_medium">
    <div aria-label="Оценка 5 Из 5" class="business-rating-badge-view__rating"></div>
  </div>
  <div class="business-header-rating-view__text _clickable">58 оценок</div>
</div>
<div class="business-review-view" itemProp="review" itemType="http://schema.org/Review" itemScope="">
  <span itemScope="" itemProp="reviewRating"><meta itemProp="ratingValue" content="5.0"/></span>
  <span class="business-review-view__date"><span>29 мая</span></span>
  <div dir="auto" class="business-review-view__body" itemProp="reviewBody">
    <span><span data-nosnippet="true"><div class="spoiler-view__text _collapsed">
      <span class=" spoiler-view__text-container">Сын ходит уже несколько лет в эту школу,
      заниматься нравится, ходит с охотой, мы как родители тоже довольны.
      Рекомендую, место хорошее.</span>
    </div></span></span>
  </div>
  <div class="business-review-view__actions"><div class="business-reactions-view"></div></div>
</div>
<div class="business-review-view" itemProp="review" itemType="http://schema.org/Review" itemScope="">
  <div dir="auto" class="business-review-view__body" itemProp="reviewBody">
    <span><span><div class="spoiler-view__text _collapsed">
      <span class=" spoiler-view__text-container">Отличная школа! Ребёнок полюбил английский,
      домашние задания делает сам — мотивирует внутренний рейтинг в приложении школы.</span>
    </div></span></span>
  </div>
  <div class="business-review-view__actions"><div class="business-reactions-view"></div></div>
</div>
</body></html>
"""


# ---------- вспомогательные фейки httpx ----------

class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


class _FakeClient:
    """Подменяет httpx.AsyncClient: GET/POST по сценарию из kwargs экземпляра."""

    scenario: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, *args, **kwargs):
        action = self.scenario.get("get")
        if isinstance(action, Exception):
            raise action
        return action

    async def post(self, *args, **kwargs):
        action = self.scenario.get("post")
        if isinstance(action, Exception):
            raise action
        return action


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch, tmp_path):
    """Изоляция: чистый кэш веб-поиска, пустой список документов, кэш в tmp_path."""
    web_module._cache.clear()
    sources_module._source_documents = []
    monkeypatch.setattr(
        sources_config.get_sources_settings(),
        "SOURCES_CACHE_FILE",
        str(tmp_path / "sources_cache.json"),
        raising=False,
    )
    yield
    web_module._cache.clear()
    sources_module._source_documents = []


# ---------- DuckDuckGo ----------

def test_parse_ddg_results_extracts_and_decodes():
    results = parse_ddg_results(DDG_HTML, limit=4)
    assert len(results) == 2
    first = results[0]
    assert first["title"] == "Фоксинбург — школа иностранных языков"
    # uddg-редирект развёрнут в прямой URL
    assert first["url"] == "https://dymova-english.ru/"
    assert "Долгопрудном" in first["snippet"]
    # прямой href остаётся как есть
    assert results[1]["url"] == "https://yandex.ru/maps/org/foxinburg/162408588499/"


def test_parse_ddg_results_respects_limit():
    assert len(parse_ddg_results(DDG_HTML, limit=1)) == 1
    assert parse_ddg_results("", limit=4) == []


@pytest.fixture
def _web_search_on(monkeypatch):
    """Тесты самого поиска включают его явно: по умолчанию он в тестах выключен."""
    monkeypatch.setattr(
        sources_config.get_sources_settings(), "WEB_SEARCH_ENABLED", True
    )


@pytest.mark.asyncio
async def test_search_web_parses_response(monkeypatch, _web_search_on):
    _FakeClient.scenario = {
        "get": _FakeResponse(DDG_HTML),
        "post": httpx.ConnectError("should not be called"),
    }
    monkeypatch.setattr(web_module.httpx, "AsyncClient", _FakeClient)
    results = await search_web("фоксинбург")
    assert len(results) == 2
    assert results[0]["url"] == "https://dymova-english.ru/"


@pytest.mark.asyncio
async def test_search_web_falls_back_to_post_on_antibot(monkeypatch, _web_search_on):
    _FakeClient.scenario = {
        "get": _FakeResponse("<html>anomaly challenge</html>", status_code=202),
        "post": _FakeResponse(DDG_HTML),
    }
    monkeypatch.setattr(web_module.httpx, "AsyncClient", _FakeClient)
    results = await search_web("фоксинбург")
    assert len(results) == 2


@pytest.mark.asyncio
async def test_search_web_network_error_returns_empty(monkeypatch, _web_search_on):
    _FakeClient.scenario = {
        "get": httpx.ConnectError("boom"),
        "post": httpx.ConnectError("boom"),
    }
    monkeypatch.setattr(web_module.httpx, "AsyncClient", _FakeClient)
    assert await search_web("фоксинбург") == []


@pytest.mark.asyncio
async def test_search_web_uses_cache(monkeypatch, _web_search_on):
    _FakeClient.scenario = {"get": _FakeResponse(DDG_HTML)}
    monkeypatch.setattr(web_module.httpx, "AsyncClient", _FakeClient)
    first = await search_web("кэш-запрос")
    # второй вызов — с упавшей сетью, но из кэша
    _FakeClient.scenario = {"get": httpx.ConnectError("boom"),
                            "post": httpx.ConnectError("boom")}
    second = await search_web("кэш-запрос")
    assert first == second and len(second) == 2


# ---------- VK ----------

def test_extract_vk_posts_filters_and_dedupes():
    posts = extract_vk_posts(VK_HTML)
    assert len(posts) == 2  # «ок» отброшен (<80), дубликат склеен
    assert any("сентябрь" in p for p in posts)
    assert any("открытый урок" in p for p in posts)
    assert all("<" not in p and "&amp;" not in p for p in posts)
    assert extract_vk_posts("") == []


# ---------- Telegram ----------

def test_extract_tg_posts():
    posts = extract_tg_posts(TG_HTML)
    assert len(posts) == 2
    assert any("Летний интенсив" in p for p in posts)
    assert any("олимпиады" in p for p in posts)
    assert all("<" not in p for p in posts)


# ---------- Яндекс.Карты ----------

def test_parse_ymaps_rating_and_reviews():
    data = parse_ymaps(YMAPS_HTML)
    assert data is not None
    assert data["rating"] == "5"
    assert data["scores"] == 58
    assert data["reviews_count"] == 37
    assert len(data["reviews"]) == 2
    assert any("Сын ходит" in r for r in data["reviews"])
    text = sources_module._ymaps_text(data)
    assert "Рейтинг 5 из 5" in text and "58 оценок" in text and "Отзывы:" in text


def test_parse_ymaps_broken_markup_returns_none():
    assert parse_ymaps("<html><body>капча</body></html>") is None
    assert parse_ymaps("") is None


# ---------- sync_sources: кэш и устойчивость ----------

@pytest.mark.asyncio
async def test_sync_sources_writes_cache(tmp_path, monkeypatch):
    from app.knowledge.kb import Document

    async def fake_vk(client):
        return [Document(category="vk", title="VK Фоксинбург: пост",
                         text="Свежий пост из ВК про набор в группы на новый учебный год.")]

    async def fake_empty(client):
        return []

    monkeypatch.setattr(sources_module, "_fetch_vk", fake_vk)
    monkeypatch.setattr(sources_module, "_fetch_ymaps", fake_empty)
    monkeypatch.setattr(sources_module, "_fetch_telegram", fake_empty)

    count = await sync_sources()
    assert count == 1
    cache_file = tmp_path / "sources_cache.json"
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    assert payload["vk"][0]["category"] == "vk"
    assert "набор в группы" in payload["vk"][0]["text"]


@pytest.mark.asyncio
async def test_sync_sources_falls_back_to_cache(tmp_path, monkeypatch):
    cache_file = tmp_path / "sources_cache.json"
    cache_file.write_text(json.dumps({
        "vk": [{"category": "vk", "title": "VK Фоксинбург: пост",
                "text": "Кэшированный пост о расписании занятий и ценах на обучение."}],
        "ymaps": [{"category": "ymaps", "title": "Яндекс.Карты: рейтинг и отзывы Фоксинбург",
                   "text": "Рейтинг 5 из 5 (58 оценок). Отзывы: Отличная школа."}],
    }, ensure_ascii=False), encoding="utf-8")

    async def failing(client):
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(sources_module, "_fetch_vk", failing)
    monkeypatch.setattr(sources_module, "_fetch_ymaps", failing)
    monkeypatch.setattr(sources_module, "_fetch_telegram", failing)

    count = await sync_sources()
    assert count == 2  # оба источника поднялись из кэша
    docs = get_source_documents()
    assert {d.category for d in docs} == {"vk", "ymaps"}
    # кэш не должен быть перезаписан пустотой
    assert json.loads(cache_file.read_text(encoding="utf-8"))["vk"]


@pytest.mark.asyncio
async def test_sync_sources_no_network_no_cache_returns_zero(monkeypatch):
    async def failing(client):
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(sources_module, "_fetch_vk", failing)
    monkeypatch.setattr(sources_module, "_fetch_ymaps", failing)
    monkeypatch.setattr(sources_module, "_fetch_telegram", failing)
    assert await sync_sources() == 0
    assert get_source_documents() == []


@pytest.mark.asyncio
async def test_sync_sources_disabled(monkeypatch):
    monkeypatch.setattr(
        sources_config.get_sources_settings(), "SOURCES_SYNC_ENABLED", False, raising=False
    )
    assert await sync_sources() == 0
