"""HTTP API ЛК: /api/lk/auth/* и /api/lk/me."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.world import core

from . import bridge, password_auth, service, words, world_link
from .learning.catalog import available_units
from .learning import sessions as learning_sessions
from .learning import progression
from .schemas import ConfirmBot, LoginIn, MeOut, PasswordIn, RegisterIn, StartAuth

router = APIRouter(prefix="/api/lk", tags=["lk"])


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    return ip, request.headers.get("user-agent")


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except core.Conflict as e:
        raise HTTPException(409, str(e)) from e
    except bridge.BridgeError as e:
        raise HTTPException(502, "bot_unreachable") from e


def _token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "unauthorized")
    return authorization[len("Bearer "):].strip()


@router.post("/auth/start")
def auth_start(body: StartAuth, request: Request):
    ip, ua = _client_meta(request)
    return _guard(service.start_auth, body.phone, body.parent_name, body.consents, ip, ua)


@router.get("/auth/status")
def auth_status(phone: str):
    from app.identity.schemas import normalize_phone
    try:
        phone_n = normalize_phone(phone)
    except ValueError:
        raise HTTPException(422, "bad phone") from None
    return service.get_status(phone_n)


def _phone_guard(fn, *a, **kw):
    try:
        return _guard(fn, *a, **kw)
    except ValueError:
        raise HTTPException(422, "bad_phone") from None


@router.get("/health/crm")
def health_crm():
    """Есть ли доступ к пульту BigBen (вход по «Данным для входа», карточки при регистрации)."""
    from . import bigben_internal
    return bigben_internal.health()


@router.post("/auth/login")
def auth_login(body: LoginIn):
    """Вход по телефону и паролю."""
    return _phone_guard(password_auth.login, body.phone, body.password)


@router.post("/auth/register")
def auth_register(body: RegisterIn, request: Request):
    """Регистрация нового клиента: аккаунт с паролем + заявка в CRM."""
    ip, _ = _client_meta(request)
    return _phone_guard(password_auth.register, body.phone, body.password, body.parent_name,
                        body.child_name, body.child_age, body.consents, ip)


@router.post("/auth/password")
def auth_password(body: PasswordIn, authorization: str | None = Header(None)):
    """Задать или сменить пароль из кабинета."""
    return _guard(password_auth.set_password, _token(authorization), body.password)


@router.post("/auth/confirm-bot")
def auth_confirm_bot(body: ConfirmBot):
    return _guard(service.confirm_via_bot, body.phone)


@router.get("/me", response_model=MeOut)
def me(authorization: str | None = Header(None)):
    return _guard(service.me, _token(authorization))


@router.get("/schedule")
def schedule(authorization: str | None = Header(None), student_id: int = 0,
             date_from: str = "", date_to: str = ""):
    return _guard(service.schedule, _token(authorization), student_id,
                  date_from, date_to)


@router.post("/attendance")
def attendance_ingest(body: dict):
    """Внутренний relay: бот пересылает сюда вебхук lesson.completed."""
    return _guard(service.ingest_attendance, body)


@router.post("/group-members")
def group_members_ingest(body: dict):
    """Внутренний relay: бот пересылает сюда вебхук group.enrolled."""
    return _guard(service.ingest_membership, body)


@router.get("/learning/catalog")
def learning_catalog(level: str | None = None, topic: str | None = None,
                     authorization: str | None = Header(None)):
    """Каталог LMS-обучения; World-каталог намеренно не используется."""
    account = service.resolve_session(_token(authorization))
    if account is None:
        raise HTTPException(401, "unauthorized")
    return {"units": [item.__dict__ for item in available_units(level=level, topic=topic)]}


def _learning_key(token: str, student_id: int) -> str:
    _, profile = words._profile(token, student_id)
    return words._learner_key(profile)


@router.post("/learning/sessions")
def learning_session_start(body: dict, authorization: str | None = Header(None)):
    token = _token(authorization)
    return _guard(learning_sessions.start, _learning_key(token, int(body.get("student_id") or 0)), str(body.get("unit_id") or ""))


@router.post("/learning/sessions/{session_id}/answer")
def learning_session_answer(session_id: str, body: dict, authorization: str | None = Header(None)):
    token = _token(authorization)
    return _guard(learning_sessions.answer, _learning_key(token, int(body.get("student_id") or 0)), session_id,
                  str(body.get("challenge_id") or ""), body.get("answer") or {})


@router.post("/learning/sessions/{session_id}/finish")
def learning_session_finish(session_id: str, body: dict, authorization: str | None = Header(None)):
    token = _token(authorization)
    return _guard(learning_sessions.finish, _learning_key(token, int(body.get("student_id") or 0)), session_id)


@router.get("/learning/progress")
def learning_progress(student_id: int = 0, authorization: str | None = Header(None)):
    token = _token(authorization)
    return _guard(progression.summary, _learning_key(token, student_id))


# ---------- Этап 3: тренажёр слов ----------

def _import_key() -> str:
    import os

    return os.environ.get("LK_IMPORT_KEY", "").strip()


@router.get("/words/sets")
def words_sets(authorization: str | None = Header(None), student_id: int = 0):
    return _guard(words.list_sets, _token(authorization), student_id)


@router.get("/words/sets/{set_id}")
def words_set_detail(set_id: int, authorization: str | None = Header(None),
                     student_id: int = 0):
    return _guard(words.set_words, _token(authorization), student_id, set_id)


@router.post("/words/train")
def words_train(body: dict, authorization: str | None = Header(None)):
    return _guard(words.start_training, _token(authorization),
                  int(body.get("student_id") or 0), int(body.get("set_id") or 0))


@router.post("/words/answer")
def words_answer(body: dict, authorization: str | None = Header(None)):
    return _guard(words.answer, _token(authorization),
                  int(body.get("student_id") or 0), int(body.get("word_id") or 0),
                  bool(body.get("correct")), str(body.get("mode") or ""),
                  str(body.get("event_key") or ""))


@router.post("/words/finish")
def words_finish(body: dict, authorization: str | None = Header(None)):
    return _guard(words.finish_session, _token(authorization), int(body.get("student_id") or 0),
                  int(body.get("set_id") or 0), int(body.get("correct") or 0), int(body.get("total") or 0))


@router.post("/words/goal")
def words_goal(body: dict, authorization: str | None = Header(None)):
    return _guard(words.set_goal, _token(authorization), int(body.get("student_id") or 0),
                  int(body.get("goal") or 50))


@router.post("/words/claim")
def words_claim(body: dict, authorization: str | None = Header(None)):
    """Забрать награду: задание дня (kind=quest) или сундук недели (kind=chest)."""
    return _guard(words.claim_reward, _token(authorization), int(body.get("student_id") or 0),
                  str(body.get("kind") or ""))


@router.get("/words/my")
def words_my(authorization: str | None = Header(None), student_id: int = 0):
    """«Мой словарь»: слова ученика по силе знания и трудные слова."""
    return _guard(words.my_words, _token(authorization), student_id)


@router.get("/words/foxi")
def words_foxi(authorization: str | None = Header(None), student_id: int = 0):
    """«Создай своего Фокси»: сохранённый облик (None — ещё не создавал)."""
    return _guard(words.get_foxi, _token(authorization), student_id)


@router.post("/words/foxi")
def words_foxi_save(body: dict, authorization: str | None = Header(None)):
    return _guard(words.set_foxi, _token(authorization), int(body.get("student_id") or 0), body.get("foxi"))


@router.get("/words/stats")
def words_stats(authorization: str | None = Header(None), student_id: int = 0):
    return _guard(words.stats, _token(authorization), student_id)


@router.get("/words/tts")
def words_tts(q: str = "", authorization: str | None = Header(None)):
    """Озвучка слова: тот же кэш TTS, что и в Мире. Rate-limit на сессию."""
    account = service.resolve_session(_token(authorization))
    if account is None:
        raise HTTPException(401, "unauthorized")
    import re

    text = re.sub(r"[^A-Za-z0-9 .,!?'\-]", "", (q or "").strip())[:80] or "hello"
    from app.world.tts import media_path, synth_english

    path = synth_english(text)
    if path is None:
        raise HTTPException(503, "tts unavailable")
    from fastapi.responses import FileResponse

    return FileResponse(str(path), media_type="audio/mpeg",
                        filename=path.name)


@router.post("/words/import")
def words_import(body: dict, x_import_key: str | None = Header(None)):
    """Конструктор наборов (методист). Защищён LK_IMPORT_KEY — отдельным
    секретом, не токеном сессии: загружать словари может и сервис."""
    if not _import_key() or x_import_key != _import_key():
        raise HTTPException(401, "unauthorized")
    return _guard(words.import_set, body)


@router.post("/words/assign")
def words_assign(body: dict, x_import_key: str | None = Header(None)):
    if not _import_key() or x_import_key != _import_key():
        raise HTTPException(401, "unauthorized")
    return _guard(words.assign_set, int(body.get("set_id") or 0),
                  str(body.get("kind") or ""),
                  body.get("group_id"), body.get("student_id"),
                  body.get("age_from"), body.get("age_to"))


# ---------- Этап 4: Мир Фоксинбурга ----------

@router.post("/world/session")
def lk_world_session(body: dict, authorization: str | None = Header(None)):
    """SSO: сессия Мира (wses.*) для профиля ЛК."""
    return _guard(world_link.world_session, _token(authorization),
                  int(body.get("student_id") or 0))


@router.get("/world/progress")
def lk_world_progress(authorization: str | None = Header(None),
                      student_id: int = 0):
    """Прогресс ребёнка в Мире для дашборда ЛК."""
    return _guard(world_link.world_progress, _token(authorization), student_id)


@router.post("/auth/logout")
def auth_logout(authorization: str | None = Header(None)):
    return _guard(service.logout, _token(authorization))
