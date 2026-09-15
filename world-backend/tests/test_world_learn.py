"""Дом, магазин, практика, каталог курса."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.world import catalog, core, engine
from app.world.db import reset_for_tests

HEADERS = {"X-World-Player": "child-learn"}


@pytest.fixture()
def client(tmp_path):
    reset_for_tests(str(tmp_path / "world.sqlite"))
    core.seed_quests()
    app = FastAPI()
    from app.world import api as world_api
    app.include_router(world_api.router)
    with TestClient(app) as c:
        c.post("/api/world/players", json={"display_name": "Мария"}, headers=HEADERS)
        yield c
    reset_for_tests(str(tmp_path / "world2.sqlite"))


def test_catalog_volume():
    order = catalog.unit_order()
    assert order[0] == "family" and order[6] == "satp" and len(order) == 18
    total = 0
    for uid in order:
        unit = catalog.get_unit(uid)
        total += len(unit["spots"])
        assert len(unit["words"]) >= 8
        assert len(unit["phrases"]) >= 8
        assert len(unit["spots"]) == 6
        assert unit["book"] in ("starter-oral", "prep-phonics")
        assert len(unit["lessons"]) == 6
        assert all(w.get("image") or w.get("teach_ru") for w in unit["lessons"][0]["words"])
    assert total == 108
    text = " ".join(
        card["body_ru"]
        for u in ("family", "school", "room", "pets", "food", "play")
        for ls in catalog.get_unit(u)["lessons"]
        for card in ls["cards"]
    ).lower()
    assert "chuckles" not in text
    assert "гадк" not in text
    assert "spotlight" not in text


def test_home_and_path_over_http(client):
    home = client.get("/api/world/learn/home", headers=HEADERS).json()
    assert home["current_lesson_id"] == "family-L1"
    assert home["course"]["source"] == "foxi-year1"
    assert home["hearts"]["current"] == 5
    path = client.get("/api/world/learn/path", headers=HEADERS).json()
    assert path["units"][0]["id"] == "family"
    assert "player" in path
    assert path["stickers_owned"] == 0
    words = client.get("/api/world/learn/words/family", headers=HEADERS).json()
    assert any(w["en"] == "hello" for w in words["words"])


def test_shop_refill_hearts(client):
    core.award("child-learn", xp=0, coins=500, source="test", type_="TEST",
               idempotency_key="give-coins")
    engine.set_hearts(core.get_player("child-learn")["id"], 1)
    bad = client.post("/api/world/learn/shop/buy", json={"sku": "nope"}, headers=HEADERS)
    assert bad.status_code == 404
    ok = client.post("/api/world/learn/shop/buy", json={"sku": "hearts_refill"}, headers=HEADERS)
    assert ok.status_code == 200
    assert ok.json()["player"]["hearts"] == 5
    album = client.get("/api/world/learn/stickers", headers=HEADERS).json()
    assert album["total"] >= 8
    assert album["owned"] == 0
    rainbow = client.post("/api/world/learn/shop/buy", json={"sku": "sticker_rainbow"}, headers=HEADERS)
    assert rainbow.status_code == 200
    assert "sticker-rainbow" in rainbow.json()["items_granted"]
    album2 = client.get("/api/world/learn/stickers", headers=HEADERS).json()
    assert album2["owned"] == 1


def test_tts_english_audio(client):
    r = client.get("/api/world/tts", params={"q": "Hello"})
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert len(r.content) > 8000


def test_sprint_and_shop_cape(client):
    from app.world import learn

    pack = learn.sprint("child-learn")
    assert pack["words"]
    assert pack["unit_id"]
    fin = client.post("/api/world/learn/sprint/finish", json={"score": 3, "total": 8}, headers=HEADERS)
    assert fin.status_code == 200
    assert fin.json()["score"] == 3
    core.award("child-learn", xp=0, coins=200, source="test", type_="TEST", idempotency_key="cape-coins")
    cape = client.post("/api/world/learn/shop/buy", json={"sku": "foxi_cape"}, headers=HEADERS)
    assert cape.status_code == 200
    assert "foxi-cape" in cape.json()["items_granted"]


def test_practice_starts(client):
    r = client.post("/api/world/learn/practice/start", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["practice"] is True
    assert body["total"] >= 6
    assert body.get("place_ru") == "Двор тренировки"
    assert all("correct_index" not in it for it in body["items"])


def test_zero_english_lesson_has_pictures_and_stages(client):
    r = client.post(
        "/api/world/learn/lessons/start",
        json={"lesson_id": "family-L1", "seed": 7},
        headers=HEADERS,
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[0]["kind"] == "explain"
    assert items[0]["visual_id"] == "foxi-hello"
    assert any(it.get("speak") for it in items if it.get("kind") == "explain")
    assert any(
        it.get("kind") == "word_card" and str(it.get("image", "")).endswith((".svg", ".jpg", ".png", ".webp"))
        for it in items
    )
    stages = [it.get("stage") for it in items]
    assert stages[0] == "warmup"
    assert "listen" in stages and "practice" in stages and stages[-1] == "wrap"
    assert items[0]["foxi_pose"] == "wave"
    hello = next(it for it in items if it.get("kind") == "word_card" and it.get("en") == "hello")
    assert hello["foxi_pose"] == "wave"
    assert str(hello.get("image", "")).endswith((".svg", ".jpg", ".png", ".webp"))
    name = next(it for it in items if it.get("kind") == "word_card" and it.get("en") == "name")
    assert not name.get("image")
    assert "зовут" in (name.get("teach_ru") or "").lower()
    no = next(it for it in items if it.get("kind") == "word_card" and it.get("en") == "no")
    assert not no.get("image")
    assert "согласен" in (no.get("teach_ru") or "")
    assert any(it.get("kind") == "phrase_card" for it in items)
    assert items[-1]["foxi_pose"] == "cheer"
    assert sum(1 for it in items if it["kind"] == "explain") >= 4
    titles = [it["title_ru"] for it in items if it["kind"] == "explain"]
    assert titles[0].startswith("1 ·")
    assert any(t.startswith("2 ·") for t in titles)
    assert any(t.startswith("3 ·") for t in titles)
    assert any(t.startswith("4 ·") for t in titles)
    fourth = [it for it in items if it["kind"] == "explain"][3]
    assert fourth.get("visual_id") != "letters-st"
    assert fourth.get("image")


def test_colour_cards_teach_phrases_not_glossary(client):
    r = client.post(
        "/api/world/learn/lessons/start",
        json={"lesson_id": "family-L5", "seed": 7},
        headers=HEADERS,
    )
    assert r.status_code == 200
    items = r.json()["items"]
    blob = " ".join(it.get("body_ru") or "" for it in items if it["kind"] == "explain").lower()
    assert "red — красный" not in blob
    assert "pet —" not in blob
    red = next(it for it in items if it.get("kind") == "word_card" and it.get("en") == "red")
    assert (red.get("example_en") or "").lower().startswith("it is red")
    assert "it is red" in (red.get("teach_ru") or "").lower()
    titles = [it["title_ru"] for it in items if it["kind"] == "explain"]
    assert titles[0].startswith("1 ·")
    assert "Цель" in titles[0]


def test_theory_cards_differ_by_lesson(client):
    def theory(lesson_id: str) -> list[dict]:
        r = client.post(
            "/api/world/learn/lessons/start",
            json={"lesson_id": lesson_id, "seed": 3},
            headers=HEADERS,
        )
        assert r.status_code == 200
        return [it for it in r.json()["items"] if it["kind"] == "explain"]

    a = theory("family-L1")
    b = theory("family-L5")
    c = theory("pets-L1")
    assert len(a) >= 4 and len(b) >= 4 and len(c) >= 4
    assert a[3]["title_ru"] != b[3]["title_ru"]
    assert a[3]["body_ru"] != b[3]["body_ru"]
    assert b[3]["title_ru"] != c[3]["title_ru"]
    assert a[3].get("visual_id") != "letters-st"
    assert b[3].get("visual_id") != "letters-st"
    assert c[3].get("visual_id") != "letters-st"
    assert a[3].get("image") != b[3].get("image")
    assert len(a[0]["body_ru"]) > 80
    speaks = [it.get("speak") or "" for it in a[:4]]
    assert speaks[0] == ""
    assert speaks[3] == ""
    assert speaks[1] != speaks[2]


def test_oral_practice_uses_english_not_glossary(client):
    r = client.post(
        "/api/world/learn/lessons/start",
        json={"lesson_id": "family-L5", "seed": 7},
        headers=HEADERS,
    )
    assert r.status_code == 200
    items = r.json()["items"]
    listen = [it for it in items if it["kind"] == "listen"]
    assert listen
    blob = " ".join(opt for it in listen for opt in it.get("options") or [])
    assert "красн" not in blob.lower()
    assert all(opt.isascii() and any(ch.isalpha() for ch in opt) for it in listen for opt in it["options"])
    match = next(it for it in items if it["kind"] == "match")
    assert any("it is" in x.lower() for x in (match.get("right") or []))
    phrases = [it for it in items if it["kind"] == "phrase_card"]
    assert len(phrases) >= 3


def test_cannot_start_without_hearts(client):
    pid = core.get_player("child-learn")["id"]
    engine.set_hearts(pid, 0)
    r = client.post(
        "/api/world/learn/lessons/start",
        json={"lesson_id": "family-L1"},
        headers=HEADERS,
    )
    assert r.status_code == 409
    restored = client.post("/api/world/learn/hearts/restore", headers=HEADERS)
    assert restored.status_code == 200
    assert restored.json()["hearts"] == 5
    ok = client.post(
        "/api/world/learn/lessons/start",
        json={"lesson_id": "family-L1"},
        headers=HEADERS,
    )
    assert ok.status_code == 200


def test_league_ranks_real_players(client):
    from app.world import learn

    core.get_or_create_player("child-fast", "Пётр")
    core.get_or_create_player("child-slow", "Аня")
    core.award("child-learn", xp=200, coins=0, source="t", type_="TEST", idempotency_key="w1")
    core.award("child-fast", xp=600, coins=0, source="t", type_="TEST", idempotency_key="w2")
    core.award("child-slow", xp=50, coins=0, source="t", type_="TEST", idempotency_key="w3")

    top = learn.league("child-fast")
    assert top["tier"] == "gold"
    assert top["weekly_xp"] == 600
    assert top["rank"] == 1
    assert top["size"] == 3
    assert [row["display_name"] for row in top["top"]][:2] == ["Пётр", "Мария"]
    assert top["top"][0]["is_me"] is True

    mid = learn.league("child-learn")
    assert (mid["rank"], mid["tier"]) == (2, "silver")
    low = learn.league("child-slow")
    assert (low["rank"], low["tier"]) == (3, "bronze")

    over_http = client.get("/api/world/learn/league", headers=HEADERS).json()
    assert over_http["rank"] == 2 and over_http["size"] == 3


def test_starter_word_photos_are_not_wikimedia_junk(client):
    from app.world.catalog import load_units
    from app.world.word_library import image_path

    load_units.cache_clear()
    assert image_path("six") == ""
    assert image_path("one") == ""
    assert image_path("dad") == ""
    assert image_path("toy") == ""
    assert str(image_path("hello")).endswith("wave.png")
    assert str(image_path("cat")).endswith("cat.jpg")
    assert str(image_path("cake")).endswith("cake.jpg")
    assert str(image_path("rubber")).endswith("rubber.jpg")
    r = client.post(
        "/api/world/learn/lessons/start",
        json={"lesson_id": "school-L3", "seed": 7},
        headers=HEADERS,
    )
    assert r.status_code == 200
    six = next(it for it in r.json()["items"] if it.get("kind") == "word_card" and it.get("en") == "six")
    assert not six.get("image")
