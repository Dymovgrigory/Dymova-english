"""Phase 1 Identity: opaque sessions, no self-admin, family-ready links."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.world import api as world_api
from app.world import auth, core
from app.world.db import get_conn, reset_for_tests

HEADERS = {"X-World-Player": "child-tts"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("WORLD_PLAYER_SECRET", raising=False)
    reset_for_tests(str(tmp_path / "world.sqlite"))
    core.seed_quests()
    app = FastAPI()
    app.include_router(world_api.router)
    with TestClient(app) as c:
        c.post("/api/world/players", json={"display_name": "TTS"}, headers=HEADERS)
        yield c
    reset_for_tests(str(tmp_path / "world2.sqlite"))


def test_public_create_rejects_self_admin(client):
    r = client.post(
        "/api/world/players",
        json={"display_name": "Hacker", "role": "admin"},
        headers={"X-World-Player": "child-hack"},
    )
    assert r.status_code == 403
    assert get_conn().execute(
        "SELECT COUNT(*) AS n FROM players WHERE external_key=?", ("child-hack",)
    ).fetchone()["n"] == 0


def test_public_create_rejects_parent_and_teacher(client):
    for role in ("parent", "teacher"):
        r = client.post(
            "/api/world/players",
            json={"display_name": "Nope", "role": role},
            headers={"X-World-Player": f"child-{role}"},
        )
        assert r.status_code == 403, role


def test_create_player_returns_opaque_session_token(client):
    r = client.post(
        "/api/world/players",
        json={"display_name": "Мария"},
        headers={"X-World-Player": "child-sess"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "child"
    token = body["token"]
    assert token.startswith("wses.")
    assert body["external_key"] == "child-sess"

    me = client.get("/api/world/player", headers={"X-World-Player": token})
    assert me.status_code == 200
    assert me.json()["external_key"] == "child-sess"
    assert me.json()["display_name"] == "Мария"


def test_expired_session_is_rejected(client, monkeypatch):
    r = client.post(
        "/api/world/players",
        json={"display_name": "Старый"},
        headers={"X-World-Player": "child-exp"},
    )
    token = r.json()["token"]
    sid = token.split(".")[1]
    past = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    get_conn().execute("UPDATE auth_sessions SET expires_at=? WHERE id=?", (past, sid))

    bad = client.get("/api/world/player", headers={"X-World-Player": token})
    assert bad.status_code == 401


def test_legacy_hmac_token_still_works_with_secret(client, monkeypatch):
    monkeypatch.setenv("WORLD_PLAYER_SECRET", "test-secret")
    core.get_or_create_player("child-legacy", "Легаси")
    token = auth.sign("child-legacy")
    assert not token.startswith("wses.")
    me = client.get("/api/world/player", headers={"X-World-Player": token})
    assert me.status_code == 200
    assert me.json()["external_key"] == "child-legacy"


def test_guardianship_links_parent_to_child(tmp_path, monkeypatch):
    monkeypatch.delenv("WORLD_PLAYER_SECRET", raising=False)
    reset_for_tests(str(tmp_path / "family.sqlite"))
    parent = core.get_or_create_player("parent-1", "Папа", role="parent")
    child = core.get_or_create_player("child-1", "Сын", role="child")
    link = core.link_guardian(parent["id"], child["id"])
    assert link["parent_player_id"] == parent["id"]
    assert link["child_player_id"] == child["id"]
    kids = core.list_wards(parent["id"])
    assert [k["external_key"] for k in kids] == ["child-1"]
    # idempotent
    core.link_guardian(parent["id"], child["id"])
    assert len(core.list_wards(parent["id"])) == 1


def test_logout_revokes_session(client):
    r = client.post(
        "/api/world/players",
        json={"display_name": "Выход"},
        headers={"X-World-Player": "child-out"},
    )
    token = r.json()["token"]
    assert client.get("/api/world/player", headers={"X-World-Player": token}).status_code == 200
    out = client.post("/api/world/session/logout", headers={"X-World-Player": token})
    assert out.status_code == 200
    assert out.json()["ok"] is True
    assert client.get("/api/world/player", headers={"X-World-Player": token}).status_code == 401


def test_public_create_never_upgrades_existing_role(client):
    core.get_or_create_player("child-keep-role", "AdminSeed", role="admin")
    r = client.post(
        "/api/world/players",
        json={"display_name": "Hacker", "role": "child"},
        headers={"X-World-Player": "child-keep-role"},
    )
    assert r.status_code == 200
    # Public bootstrap must not demote/alter elevated roles via signup payload.
    row = get_conn().execute(
        "SELECT role FROM players WHERE external_key=?", ("child-keep-role",)
    ).fetchone()
    assert row["role"] == "admin"
    assert r.json()["role"] == "admin"


def test_tts_rate_limited_per_player(client, monkeypatch):
    from app.world import api as world_api

    monkeypatch.setattr(world_api, "TTS_RATE_LIMIT", 3)
    monkeypatch.setattr(world_api, "_tts_hits", {})

    def fake_synth(_q: str):
        from pathlib import Path
        import tempfile

        p = Path(tempfile.gettempdir()) / "world-tts-test.mp3"
        p.write_bytes(b"ID3" + b"\x00" * 2000)
        return p

    monkeypatch.setattr("app.world.tts.synth_english", fake_synth)
    ok = 0
    limited = 0
    for _ in range(5):
        r = client.get("/api/world/tts", params={"q": "Hi"}, headers=HEADERS)
        if r.status_code == 200:
            ok += 1
        elif r.status_code == 429:
            limited += 1
    assert ok == 3
    assert limited == 2
