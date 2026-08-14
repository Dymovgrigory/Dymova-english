"""AI Core: оркестратор «мышления» бота.

Перед каждым ответом проходит цикл принятия решения:
  что хочет пользователь → какая цель → какая информация нужна → где её найти →
  нужно ли уточнять / продавать / записывать / передавать человеку → ответ.

Соединяет распознавание намерения, память, поиск по базе знаний, продажи,
подбор курса, сбор лида и передачу администратору.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time

from app import intent as I
from app import runtime
from app import registration
from app.bigben import get_bigben
from app.config import settings
from app.knowledge.kb import get_kb, _stem, _tokens
from app.llm import get_llm
from app.llm_gateway import ROLE_REASONING, get_gateway
from app.max_client import get_max
from app import critic
from app import emotion
from app import intent_ai
from app import pii
from app import recall
from app import recommender
from app import smart
from app.memory import (
    Conversation,
    STAGE_DISCOVERY,
    STAGE_DONE,
    STAGE_HANDOFF,
    STAGE_LEAD,
    STAGE_OBJECTION,
    get_store,
)
from app import insights
from app import sales
from app import lead_manager
from app.admin_router import hand_off
from app.web import search_web

logger = logging.getLogger(__name__)

_FACTUAL_INTENTS = {I.PRICE, I.COURSES, I.CONTACTS, I.ABOUT}
_TEAM_TRIGGER_RE = re.compile(
    r"педагог|учител|препода|видеовизит|визитк|фрагмент.{0,15}урок|кто ведёт|кто ведет",
    re.IGNORECASE,
)
_TEAM_LANGS = (("англ", "английск"), ("немец", "немецк"), ("китай", "китайск"))

_UNKNOWN_MARKER = "[UNKNOWN]"
_UNCERTAIN_RE = re.compile(
    r"не обладаю (?:такой |этой |данной )?информаци|"
    r"нет (?:точной |такой |этой )?информаци|"
    r"не наш[ёе]л точных данных|не могу сказать точно|"
    r"лучше уточнить у администратор|уточните у администратор",
    re.IGNORECASE,
)
_WEAK_KB_SCORE = 0.34

_TOPIC_MAP = {
    I.PRICE: "цены",
    I.COURSES: "курсы",
    I.CONTACTS: "контакты",
    I.ABOUT: "о школе",
    I.WANT_SIGNUP: "запись",
    I.REGISTER: "регистрация",
    I.HANDOFF: "администратор",
    I.OBJECTION: "сомнение",
}


def _capture_entities(conv: Conversation, text: str) -> None:
    """Опортунистически вытаскиваем возраст/телефон/формат из любого сообщения."""
    age = I.extract_age(text)
    if age and not conv.lead.age:
        conv.lead.age = age
    phone = I.extract_phone(text)
    if phone and not conv.lead.phone:
        conv.lead.phone = phone
    low = text.lower()
    if "онлайн" in low and not conv.selected_format:
        conv.selected_format = "Онлайн"
    elif ("офлайн" in low or "оффлайн" in low) and not conv.selected_format:
        conv.selected_format = "Офлайн"


def _remember_dialogue_state(conv: Conversation, text: str, intent: str) -> None:
    conv.last_user_intent = intent
    conv.last_user_topic = _TOPIC_MAP.get(intent, conv.last_user_topic)
    # Состояние пишем всегда, включая нейтральное: иначе одно раздражённое
    # сообщение делало весь остаток разговора «раздражённым» навсегда.
    conv.last_user_mood = emotion.detect(text, conv.last_user_mood)


def _wants_manager(text: str) -> bool:
    low = text.lower()
    return any(word in low for word in ("руковод", "директор", "администрат", "начальник"))


def _drop_trailing_question(text: str) -> str:
    stripped = text.rstrip()
    if stripped.endswith("?"):
        stripped = stripped[:-1].rstrip()
        cut = max(stripped.rfind("."), stripped.rfind("!"), stripped.rfind("…"))
        if cut >= 0:
            stripped = stripped[: cut + 1]
        elif stripped:
            stripped += "."
    return stripped


def _handoff_followup_reply(conv: Conversation, text: str) -> str:
    if _wants_manager(text):
        return (
            "Понимаю, сейчас подключу руководителя или администратора — "
            "он скоро ответит. Если срочно, можно позвонить: 8 993 923-23-09 "
            "(Лихачевский) или 8 916 732-31-69 (Ракетостроителей)."
        )
    variants = [
        "Я уже передал ваш вопрос администратору — он скоро ответит. Если нужно что-то ещё, напишите, я помогу. 😊",
        "Вопрос уже у администратора, он скоро подключится. Если хотите, могу пока подсказать по курсам или расписанию. 😊",
    ]
    return variants[len(conv.history) % len(variants)]


def _grounded_fact_reply(kb, text: str, intent: str) -> str:
    docs = kb.search(text, limit=4)
    if not docs:
        return (
            "Проверил сайт и соцсети, но не нашёл подтверждённых данных по "
            "этому вопросу. Не хочу придумывать цифры или факты. Могу "
            "передать вопрос администратору."
        )

    title_map = {
        I.PRICE: "Вот подтверждённые данные по стоимости с сайта и соцсетей:",
        I.CONTACTS: "Вот подтверждённые контакты и филиалы с сайта и соцсетей:",
        I.COURSES: "Вот подтверждённые программы и направления с сайта и соцсетей:",
        I.ABOUT: "Вот подтверждённые факты о школе с сайта и соцсетей:",
    }
    lines = [title_map.get(intent, "Вот что удалось подтвердить на сайте и в соцсетях:")]
    for doc in docs:
        lines.append(f"• {doc.as_answer()}")
    if intent == I.PRICE:
        lines.append("Если хотите, я ещё уточню стоимость по возрасту и формату.")
    elif intent == I.CONTACTS:
        lines.append("Если нужно, подскажу, какой филиал ближе.")
    elif intent == I.COURSES:
        lines.append("Если скажете возраст, подберу подходящую программу.")
    elif intent == I.ABOUT:
        lines.append("Если хотите, отдельно соберу факты по методике, лицензии или результатам.")
    return "\n".join(lines)


def _is_uncertain_reply(reply: str) -> bool:
    return reply.lstrip().startswith(_UNKNOWN_MARKER) or bool(_UNCERTAIN_RE.search(reply))


async def _refer_to_admin(conv: Conversation, text: str, reason: str, score: float) -> str:
    """Мягкий перевод на администратора при вопросе без подтверждённого ответа.

    Вопрос логируется в журнал пробелов (insights), администраторы получают
    уведомление с контекстом, но диалог не блокируется — бот продолжает
    помогать по остальным темам.
    """
    insights.log_gap(text, reason=reason, score=score, user_id=conv.user_id)
    await hand_off(get_max(), conv, reason="бот не знал точного ответа")
    conv.stage = STAGE_DISCOVERY
    return (
        f"{_empathy_prefix(conv)}Не хочу вводить вас в заблуждение: точных "
        "данных по этому вопросу у меня нет, а придумывать не буду. Передал "
        "вопрос администратору — он ответит здесь. Если срочно, можно "
        "позвонить: 8 993 923-23-09 (Лихачевский) или 8 916 732-31-69 "
        "(Ракетостроителей)."
    )


async def _ask(messages: list[dict], vault) -> str | None:
    """Запрос к модели через Gateway с редакцией ПДн.

    Отдельная функция, потому что вызывается и в основном пути, и в повторе
    с веб-контекстом: редакция не должна зависеть от того, какая это попытка.
    """
    return await get_gateway().complete(ROLE_REASONING, messages, vault=vault)


def _empathy_prefix(conv: Conversation) -> str:
    return emotion.opening(conv.last_user_mood)


def _vault_for(conv: Conversation):
    """Хранилище ПДн для этого диалога — или None, если редакция выключена."""
    if not getattr(settings, "LLM_PII_REDACTION", True):
        return None
    vault = pii.vault_for(conv)
    return vault if vault else None


async def _consult_with_context(
    conv: Conversation, text: str, kb_context: str, kb_score: float = 1.0,
    allow_web_retry: bool = False, school_related: bool | None = None,
) -> str:
    kb = get_kb()
    llm = get_llm()
    if llm.enabled:
        vault = _vault_for(conv)
        system = sales.build_system_prompt(kb, conv, kb_context, vault=vault)
        messages = [{"role": "system", "content": system}]
        history_turns = max(0, int(getattr(settings, "LLM_HISTORY_TURNS", 8)))
        messages.extend(conv.history[-history_turns:])
        reply = await _ask(messages, vault)
        if reply:
            if _is_uncertain_reply(reply) and allow_web_retry:
                # Вторая попытка с живым веб-поиском: вопрос мог быть про
                # актуальное (новости, даты, требования), чего нет в базе.
                if school_related is None:
                    school_related = bool(_SCHOOL_SCOPE_RE.search(text))
                web_ctx = await _web_context_for(text, school_related=school_related)
                if web_ctx:
                    retry_context = (kb_context + "\n\n" if kb_context else "") + web_ctx
                    system = sales.build_system_prompt(kb, conv, retry_context, vault=vault)
                    messages[0] = {"role": "system", "content": system}
                    retry = await _ask(messages, vault)
                    if retry and not _is_uncertain_reply(retry):
                        return retry
            if _is_uncertain_reply(reply):
                return await _refer_to_admin(conv, text, reason="llm_uncertain", score=kb_score)
            return reply
    if kb_context:
        plain = _plain_answer(kb, text)
        if plain:
            nudge = sales.sales_nudge(conv)
            reply = f"{_empathy_prefix(conv)}{plain}"
            return f"{reply}\n\n{nudge}" if nudge else reply
    return await _refer_to_admin(conv, text, reason="no_answer", score=0.0)


def _plain_answer(kb, text: str, limit: int = 2) -> str:
    """Ответ из базы знаний без модели — так, как его можно показать человеку.

    Раньше сюда попадал тот же текст, что уходит модели: с заголовками в
    квадратных скобках и вопросами из FAQ. Человек видел выгрузку документов,
    в которой бот будто задаёт вопросы вместо ответа.
    """
    docs = kb.search(text, limit=limit)
    return "\n\n".join(doc.as_answer().strip() for doc in docs if doc.as_answer().strip())


async def _web_context_for(text: str, school_related: bool) -> str:
    """Живой поиск в интернете (DuckDuckGo) — подстраховка, когда база знаний
    и синхронизированные источники не покрыли вопрос. Никогда не падает."""
    if not getattr(settings, "WEB_SEARCH_ENABLED", True):
        return ""
    query = f"Фоксинбург Долгопрудный школа английского {text}" if school_related else text
    try:
        results = await search_web(query, limit=4)
    except Exception:
        logger.exception("web_search: ошибка поиска")
        return ""
    if not results:
        return ""
    lines = ["ИЗ ИНТЕРНЕТА (живой поиск; используй осторожно, школьные факты сверяй с базой):"]
    for r in results:
        title = (r.get("title") or "").strip()
        snippet = (r.get("snippet") or "").strip()
        url = (r.get("url") or "").strip()
        if title or snippet:
            lines.append(f"• {title}: {snippet} ({url})")
    return "\n".join(lines) if len(lines) > 1 else ""


_SCHOOL_SCOPE_RE = re.compile(
    r"фоксинбург|фокси|долгопрудн|dymova|foxy|лихачевск|ракетостроител",
    re.IGNORECASE,
)


async def _consult(conv: Conversation, text: str, allow_web: bool = False, school_related: bool | None = None) -> str:
    """Свободный консультативный ответ: база знаний + живые источники,
    при слабом покрытии — живой веб-поиск (RAG-lite)."""
    kb = get_kb()
    scored = kb.search_scored(text, limit=5)
    kb_context = "\n\n".join(doc.render() for _, doc in scored)
    top_score = scored[0][0] if scored else 0.0
    if scored and top_score < _WEAK_KB_SCORE:
        insights.log_gap(text, reason="weak_kb_match", score=top_score, user_id=conv.user_id)
    context = kb_context
    if allow_web and top_score < _WEAK_KB_SCORE:
        if school_related is None:
            school_related = bool(_SCHOOL_SCOPE_RE.search(text))
        web_ctx = await _web_context_for(text, school_related=school_related)
        if web_ctx:
            context = (kb_context + "\n\n" if kb_context else "") + web_ctx
    return await _consult_with_context(
        conv, text, context, kb_score=top_score,
        allow_web_retry=allow_web, school_related=school_related,
    )


# Разбор потребности выполняется ДО генерации ответа, поэтому его дедлайн
# должен быть заметно меньше общего: иначе служебный запрос съест окно,
# отведённое на сам ответ.
NEED_EXTRACTION_TIMEOUT_SEC = 6.0

# Переписывание ответа критиком идёт уже после генерации, то есть человек
# всё это время ждёт. Улучшение не стоит того, чтобы удваивать ожидание.
REWRITE_TIMEOUT_SEC = 8.0

# Сжатие давних сообщений — служебная работа перед ответом; не свернулось
# вовремя, значит свернётся на следующей реплике.
MEMORY_FOLD_TIMEOUT_SEC = 5.0

# Разбор намерения стоит перед ответом, поэтому лимит жёсткий: лучше общий
# ответ по существу, чем правильный маршрут через пять секунд.
INTENT_TIMEOUT_SEC = 4.0

TIMEOUT_REPLY = (
    "Мне нужно чуть больше времени на этот вопрос 🙏 Напишите, пожалуйста, "
    "ещё раз — отвечу сразу. Если срочно, позвоните: 8 993 923-23-09 "
    "(Лихачевский) или 8 916 732-31-69 (Ракетостроителей)."
)

ERROR_REPLY = (
    "Что-то у меня сейчас не сложилось на техничеcкой стороне 🙈 "
    "Попробуйте, пожалуйста, ещё раз через минуту — или позвоните: "
    "8 993 923-23-09 (Лихачевский), 8 916 732-31-69 (Ракетостроителей)."
)


async def handle_message(user_id: str, text: str, platform: str = "max") -> str:
    """Главная точка входа: принимает сообщение пользователя, возвращает ответ бота.

    Три гарантии, без которых бот выглядит зависшим:
    1. сообщения одного пользователя обрабатываются строго по очереди —
       иначе параллельные апдейты мутируют один Conversation и затирают
       историю друг друга;
    2. ответ приходит не позже REPLY_TIMEOUT_SEC (включая ожидание очереди) —
       по истечении отдаём честный фолбэк вместо молчания;
    3. любое исключение превращается в человеческий текст, а не в тишину.
    """
    request_id = runtime.get_request_id() or runtime.new_request_id()
    runtime.set_request_id(request_id)
    started = time.monotonic()
    runtime.log_event(
        "REQUEST_RECEIVED", user_id=user_id, platform=platform, chars=len(text)
    )
    timeout = float(getattr(settings, "REPLY_TIMEOUT_SEC", 60.0) or 0) or None
    try:
        reply = await asyncio.wait_for(
            _handle_message_serialized(user_id, text, platform), timeout=timeout
        )
        status = "ok"
    except asyncio.TimeoutError:
        status = "timeout"
        reply = _record_fallback(user_id, text, platform, TIMEOUT_REPLY)
    except asyncio.CancelledError:
        runtime.log_event("REQUEST_CANCELLED", user_id=user_id, platform=platform)
        raise
    except Exception:
        status = "error"
        logger.exception("handle_message failed user_id=%s platform=%s", user_id, platform)
        reply = _record_fallback(user_id, text, platform, ERROR_REPLY)
    runtime.log_event(
        "RESPONSE_READY",
        user_id=user_id,
        platform=platform,
        status=status,
        took=f"{time.monotonic() - started:.2f}s",
    )
    return reply


def _record_fallback(user_id: str, text: str, platform: str, reply: str) -> str:
    """Сохраняет пару «вопрос → честный фолбэк», чтобы контекст остался связным.

    Без этого после таймаута в истории висел вопрос без ответа, и следующая
    реплика («а сколько стоит?») уходила в LLM с оборванным диалогом.
    """
    try:
        store = get_store()
        conv = store.get(user_id, platform=platform)
        if not conv.history or conv.history[-1] != {"role": "user", "content": text}:
            conv.add("user", text)
        conv.add("assistant", reply)
        store.save(conv)
    except Exception:
        logger.exception("не удалось сохранить фолбэк для user_id=%s", user_id)
    return reply


async def _handle_message_serialized(user_id: str, text: str, platform: str) -> str:
    async with runtime.conversation_lock(platform, user_id):
        return await _handle_message_locked(user_id, text, platform)


async def _handle_message_locked(user_id: str, text: str, platform: str) -> str:
    store = get_store()
    kb = get_kb()
    conv = store.get(user_id, platform=platform)
    conv.add("user", text)
    _capture_entities(conv, text)
    await _update_need(conv, text)
    intent = await _detect_intent(conv, text)
    _remember_dialogue_state(conv, text, intent)

    if not registration.is_registered(conv):
        if conv.stage != registration.STAGE_REGISTRATION:
            reply = registration.start_registration(conv)
        else:
            reply, _done = await registration.handle_registration_step(
                conv, text, get_bigben()
            )
        conv.add("assistant", reply)
        store.save(conv)
        return reply

    await _fold_memory(conv)

    runtime.log_event("ROUTING", user_id=user_id, intent=intent, stage=conv.stage)
    reply = await _route(conv, text, kb, intent)
    reply = await _review(conv, text, reply)

    conv.add("assistant", reply)
    store.save(conv)
    return reply


async def _detect_intent(conv: Conversation, text: str) -> str:
    """Намерение: сначала ключевые слова, затем — по смыслу.

    Модель подключается только там, где разбор по словам ничего не понял
    (общий QUESTION). Так все уже работающие сценарии остаются такими же
    быстрыми и бесплатными, а платим мы за неоднозначные реплики.
    """
    intent = I.detect_intent(text)
    if intent != I.QUESTION:
        return intent
    try:
        refined = await asyncio.wait_for(
            intent_ai.refine(text, conv.history, vault=_vault_for(conv)),
            timeout=INTENT_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        runtime.log_event("INTENT_REFINE_TIMEOUT", user_id=conv.user_id)
        return intent
    except Exception:
        logger.exception("intent: разбор по смыслу не удался user_id=%s", conv.user_id)
        return intent
    if refined and refined != intent:
        runtime.log_event("INTENT_REFINED", user_id=conv.user_id, intent=refined)
        return refined
    return intent


async def _fold_memory(conv: Conversation) -> None:
    """Сворачивает выпавшие из окна сообщения в долгосрочную память.

    Делается до генерации ответа: пересказ нужен уже в этом системном
    промпте, иначе бот ответит, не зная того, что человек рассказал раньше.
    """
    if not recall.needs_fold(conv):
        return
    try:
        await asyncio.wait_for(
            recall.fold(conv, vault=_vault_for(conv)), timeout=MEMORY_FOLD_TIMEOUT_SEC
        )
    except asyncio.TimeoutError:
        # Опоздавшее сжатие не повод задерживать ответ: сообщения остаются в
        # очереди и свернутся на следующей реплике.
        runtime.log_event("MEMORY_FOLD_TIMEOUT", user_id=conv.user_id)
    except Exception:
        logger.exception("recall: сжатие памяти не удалось user_id=%s", conv.user_id)


def _seed_need_from_conversation(conv: Conversation) -> None:
    """Переносит в профиль то, что диалог знал ещё до появления SMART.

    Клиенты, начавшие разговор на прошлой версии бота, имеют заполненные
    lead.age и selected_format, но пустой профиль потребности. Без переноса
    бот заново спросил бы возраст у человека, который его уже называл, —
    именно то, за что диалог ощущается роботизированным.
    """
    profile = conv.need
    if not profile.child_age and conv.lead.age:
        profile.child_age = conv.lead.age
    if not profile.preferred_format and conv.selected_format:
        profile.preferred_format = conv.selected_format.lower()
    if not profile.who and (conv.lead.fio_child or conv.lead.age):
        profile.who = smart.WHO_PARENT
    if not profile.objections and conv.last_objection:
        profile.objections.append(conv.last_objection)


async def _update_need(conv: Conversation, text: str) -> None:
    """Обновляет профиль потребности после очередной реплики клиента.

    Дешёвый детерминированный разбор — всегда: он работает и без LLM, и когда
    модель ничего не нашла. Разбор моделью — только пока потребность неясна:
    как только её достаточно, тратить на это запрос в каждой реплике незачем.
    """
    profile = conv.need
    _seed_need_from_conversation(conv)
    smart.enrich_from_text(profile, text)
    if profile.stage() == smart.STAGE_READY:
        return
    if not smart.looks_informative(text):
        # Справочный вопрос о потребности ничего не сообщает — незачем платить
        # за разбор и, главное, задерживать ответ лишним round trip.
        return
    try:
        extracted = await asyncio.wait_for(
            smart.extract(conv.history, vault=_vault_for(conv)),
            timeout=NEED_EXTRACTION_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        # Разбор — улучшение ответа, а не его условие. Опоздал — работаем без
        # него: пользователь не должен ждать служебный запрос.
        runtime.log_event("NEED_EXTRACTION_TIMEOUT", user_id=conv.user_id)
        return
    except Exception:
        logger.exception("smart: разбор потребности не удался user_id=%s", conv.user_id)
        return
    profile.merge(extracted)


async def _review(conv: Conversation, user_text: str, reply: str) -> str:
    """Пропускает ответ через критика перед отправкой.

    Порядок важен: сначала чиним то, что чинится текстом (это бесплатно и
    без риска потерять факты), и только оставшиеся нарушения отдаём на
    переписывание модели. Ровно одна попытка: вторая стоила бы пользователю
    ещё нескольких секунд ожидания ради всё менее заметного улучшения.
    """
    if not reply:
        return reply
    allowed = sales.offer_allowed(conv)
    issues = critic.inspect(reply, conv, allowed)
    if not issues:
        return reply

    runtime.log_event("CRITIC_ISSUES", user_id=conv.user_id, issues=",".join(issues))
    reply = critic.repair(reply, issues)
    remaining = critic.inspect(reply, conv, allowed)
    if not critic.needs_rewrite(remaining):
        return reply

    rewritten = await _rewrite(conv, user_text, reply, remaining)
    if not rewritten:
        # Переписать не вышло — отдаём то, что есть. Молчание или
        # шаблонная отписка хуже неидеальной, но осмысленной реплики.
        return reply
    fixed = critic.repair(rewritten, critic.inspect(rewritten, conv, allowed))
    # Вторая версия принимается, только если она реально лучше: модель
    # вполне может переписать в те же самые грабли.
    if len(critic.inspect(fixed, conv, allowed)) < len(remaining):
        runtime.log_event("CRITIC_REWRITTEN", user_id=conv.user_id)
        return fixed
    return reply


async def _rewrite(
    conv: Conversation, user_text: str, reply: str, issues: list[str]
) -> str | None:
    """Одна попытка переписать ответ с замечаниями критика."""
    note = critic.feedback(issues)
    if not note or not get_llm().enabled:
        return None
    vault = _vault_for(conv)
    system = sales.build_system_prompt(get_kb(), conv, "", vault=vault)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": reply},
        {"role": "user", "content": note},
    ]
    try:
        return await asyncio.wait_for(
            _ask(messages, vault), timeout=REWRITE_TIMEOUT_SEC
        )
    except asyncio.TimeoutError:
        runtime.log_event("CRITIC_REWRITE_TIMEOUT", user_id=conv.user_id)
        return None
    except Exception:
        logger.exception("critic: переписывание не удалось user_id=%s", conv.user_id)
        return None


def reset_conversation_locks() -> None:
    """Сброс очередей между тестами."""
    runtime.reset_locks()


async def _route(conv: Conversation, text: str, kb, intent: str) -> str:
    max_client = get_max()
    bigben = get_bigben()

    # 1. Если уже идёт сбор данных для заявки — продолжаем его,
    #    но позволяем выйти к оператору.
    if conv.stage == STAGE_LEAD:
        if intent == I.HANDOFF:
            await hand_off(max_client, conv, reason="запрос оператора")
            return _handoff_reply()
        reply, _submitted = await lead_manager.step(conv, text, kb, bigben, max_client)
        if reply == lead_manager.OFF_TOPIC:
            # Вопрос не про заявку. Отвечаем по существу и только потом
            # возвращаемся к анкете: глушить вопрос ради формы — верный
            # способ выглядеть роботом.
            if intent == I.GREETING:
                # На «привет» не ищут ответ в базе знаний.
                answer = "Здравствуйте! 😊"
            else:
                # _consult по пути может сменить этап (например, эскалация
                # «не знаю» переводит в handoff). Незавершённую заявку это
                # обнуляло молча — человек больше не видел её вообще.
                saved_stage, saved_step = conv.stage, conv.lead_step
                answer = await _consult(conv, text)
                conv.stage, conv.lead_step = saved_stage, saved_step
            return f"{answer}\n\n{lead_manager.pending_question(conv)}"
        return reply

    # 2. Уже передан администратору — не перебиваем, но подтверждаем.
    #    Исключение: явное желание записаться — не должно теряться навсегда
    #    в шаблонных ответах, если клиент решил продолжить оформление заявки.
    if conv.stage == STAGE_HANDOFF:
        if intent == I.WANT_SIGNUP:
            conv.stage = STAGE_LEAD
            reply, _submitted = await lead_manager.step(conv, text, kb, bigben, max_client)
            return reply
        return _handoff_followup_reply(conv, text)

    # 3. Запрос живого человека / нестандартная ситуация.
    if intent == I.HANDOFF:
        await hand_off(max_client, conv, reason="запрос оператора")
        return _handoff_reply()

    # 4. Возражение — отрабатываем по сценарию и подталкиваем к диагностике.
    if intent == I.OBJECTION:
        conv.stage = STAGE_OBJECTION
        key = I.detect_objection(text) or "подумаю"
        if get_llm().enabled:
            return await _consult_with_context(conv, text, sales.handle_objection(kb, key, conv))
        return sales.handle_objection(kb, key, conv)

    # 4б. Вопрос о педагогах — структурированный ответ со ссылками на видео.
    if intent != I.WANT_SIGNUP:
        team = team_reply(kb, text)
        if team:
            conv.stage = STAGE_DISCOVERY
            return team

    # 4в. Человек описал проблему, а не спросил справку.
    #     «Ребёнок не хочет заниматься английским» по ключевым словам попадает
    #     в COURSES и раньше получало в ответ список программ — то есть на
    #     рассказ о трудности приходил прайс. Сначала признаём проблему и
    #     выясняем причину; предложение появится, когда станет ясна потребность.
    pain = smart.pain_in_text(text)
    if pain and not sales.offer_allowed(conv):
        conv.stage = STAGE_DISCOVERY
        if get_llm().enabled:
            # У модели уже есть в промпте и сама боль, и запрет предлагать —
            # живой ответ лучше заготовки.
            return await _consult(conv, text)
        acknowledgement, question = smart.pain_reply(pain)
        smart.mark_asked(conv.need, question)
        return f"{acknowledgement} {question}"

    # 4г. Спрашивают про программы, и мы уже понимаем, для кого. Отвечаем
    #     подбором с обоснованием, а не перечислением каталога: список
    #     программ — это тот же прайс, только другими словами. Если
    #     уверенного подбора нет, ниже отработает обычный ответ по базе.
    if intent == I.COURSES:
        pick = recommender.suggest(kb, conv)
        if pick and pick.next_best_action != recommender.NEXT_ASK:
            conv.stage = STAGE_DISCOVERY
            conv.recommended_program = pick.program
            runtime.log_event(
                "RECOMMENDED",
                user_id=conv.user_id,
                program=pick.program,
                confidence=pick.confidence,
            )
            return pick.as_text()

    if intent in _FACTUAL_INTENTS:
        conv.stage = STAGE_DISCOVERY
        if (
            intent == I.PRICE
            and not conv.need.knows_situation()
            and not conv.selected_course
            # Спрашиваем про ученика один раз. Раньше от зацикливания
            # защищали три наслоившихся условия (есть ли в тексте название
            # курса, было ли оно в паре прошлых реплик, известен ли
            # возраст) — каждое добавляли после очередного бага. Теперь
            # достаточно журнала заданных вопросов: он же не даёт спросить
            # то же самое дважды во всех остальных сценариях.
            and "who" not in conv.need.asked_slots
        ):
            # Голый "сколько стоит?" без курса/возраста находит по ключевым
            # словам нерелевантный документ (например, про частоту занятий),
            # LLM честно отказывается называть цену по слабому контексту
            # (это в промпте — не выдумывать цифры), и это перехватывается
            # как "не знаю" → шаблонная передача администратору, хотя цены
            # для конкретных курсов есть в базе знаний. Уточняющий вопрос
            # вместо отказа — и дешевле, и больше похоже на живого менеджера.
            # has_course_hint защищает от того же паттерна на новом месте:
            # без него "сколько стоит английский для ребёнка?" (нет цифры,
            # selected_course нигде не присваивается) получал бы тот же
            # уточняющий вопрос бесконечно, хотя курс уже назван.
            # recent_course_hint смотрит и на пару предыдущих реплик: в диалоге
            # «расскажите про летнюю академию» → «сколько стоит смена?»
            # курс ясен из контекста, уточнять не нужно (сессия 36, стресс-тест).
            #
            # Формулировка вопроса берётся из SMART, а не пишется здесь:
            # иначе бот на любой вопрос о цене отвечает одной и той же
            # заготовкой, а профиль потребности не пополняется.
            question = smart.next_question(conv.need) or (
                "Для какого курса и возраста уточнить стоимость?"
            )
            smart.mark_asked(conv.need, question)
            return (
                "Конечно, подскажу. Чтобы не отправлять вам общий прайс, "
                f"уточню одну вещь. {question}"
            )
        if not kb.search(text, limit=1) and not get_llm().enabled:
            # Без LLM и без совпадений в базе знаний ответить нечем — handoff.
            return await _refer_to_admin(conv, text, reason="no_kb_match", score=0.0)
        if get_llm().enabled:
            # LLM разберётся сам: сильный контекст из KB, иначе живой веб-поиск;
            # администратор подключается только если уверенного ответа нет нигде.
            return await _consult(conv, text, allow_web=True, school_related=True)
        return _grounded_fact_reply(kb, text, intent)

    # 5. Явное намерение открыть кабинет — запускаем регистрацию.
    if intent == I.REGISTER:
        return registration.start_registration(conv)

    # 6. Явное намерение записаться — запускаем сбор лида.
    if intent == I.WANT_SIGNUP:
        return lead_manager.start(conv)

    # 7. Приветствие — короткое, человеческое, без простыни про школу.
    #    Срабатывает на любое приветствие, не только на первое сообщение —
    #    иначе повторное «привет» уходит в KB-поиск, не находит документов
    #    и ошибочно логируется как пробел базы знаний (см. insights.jsonl).
    if intent == I.GREETING:
        conv.stage = STAGE_DISCOVERY
        if len(conv.history) <= 2:
            # Приветствие не продаёт: сначала выясняем, для кого занятия.
            # Прежний вариант сразу предлагал диагностику — ровно та ранняя
            # продажа, которую запрещает SMART.
            question = smart.next_question(conv.need)
            smart.mark_asked(conv.need, question)
            opener = "Здравствуйте! Меня зовут Фокси, я консультант школы «Фоксинбург»."
            return f"{opener} {question}" if question else opener
        return "Здравствуйте! Чем могу помочь?"

    # 9. Во всех прочих случаях — консультативный ответ по базе знаний.
    #    Веб-поиск подключаем только для содержательных вопросов (не для
    #    коротких реплик вида «ок», «спасибо», «понятно»).
    if conv.stage not in (STAGE_DONE,):
        conv.stage = STAGE_DISCOVERY
    looks_like_question = "?" in text or len(text.strip()) >= 25
    return await _consult(conv, text, allow_web=looks_like_question)


def _teacher_language(about: str) -> str:
    langs = [full for key, full in _TEAM_LANGS if key in about.lower()]
    return " и ".join(f"{lang}ий" for lang in langs) if langs else ""


def _format_teacher(person: dict) -> str:
    lang = _teacher_language(person.get("about", ""))
    header = f"👩‍🏫 {person.get('name', '')}" + (f" — {lang} язык" if lang else "")
    lines = [header]
    if person.get("video_intro"):
        lines.append(f"▶️ Видеовизитка: {person['video_intro']}")
    if person.get("video_lesson"):
        lines.append(f"🎬 Фрагмент урока: {person['video_lesson']}")
    return "\n".join(lines)


def team_reply(kb, text: str) -> str | None:
    """Структурированный ответ о педагогах: ФИО, язык, ссылки на видео каждого."""
    raw = getattr(kb, "raw", {}) or {}
    teachers = [p for p in (raw.get("team") or []) if p.get("role") == "Педагог"]
    if not teachers:
        return None
    text_stems = set(_tokens(text))

    named = [
        p for p in teachers
        if any(_stem(part) in text_stems for part in p.get("name", "").split())
    ]
    if named:
        cards = "\n\n".join(_format_teacher(p) for p in named)
        return f"{cards}\n\nЗаписать вас на бесплатную диагностику? 😊"

    if not _TEAM_TRIGGER_RE.search(text):
        return None
    low = text.lower()
    wanted = [full for key, full in _TEAM_LANGS if key in low]
    if wanted:
        selected = [
            p for p in teachers
            if any(w in p.get("about", "").lower() for w in wanted)
        ]
    else:
        selected = teachers
    if not selected:
        return None
    cards = "\n\n".join(_format_teacher(p) for p in selected)
    return (
        f"Наши педагоги:\n\n{cards}\n\n"
        "Могу записать на бесплатную диагностику — познакомитесь с педагогом лично. 😊"
    )


def _handoff_reply() -> str:
    return (
        "Конечно, подключаю администратора — он скоро напишет вам здесь. 🙌\n"
        "Если вопрос срочный, можно позвонить: 8 993 923-23-09 "
        "(Лихачевский) или 8 916 732-31-69 (Ракетостроителей)."
    )


async def handle_start(user_id: str, platform: str = "max") -> str:
    """Ответ на команду /start или событие bot_started."""
    store = get_store()
    conv = store.get(user_id, platform=platform)
    if not registration.is_registered(conv):
        reply = registration.start_registration(conv)
        conv.add("assistant", reply)
        store.save(conv)
        return reply
    if conv.is_returning():
        # Помнить надо по-человечески: «мы обсуждали занятия для Маши», а не
        # «я помню ваш прошлый диалог» — и уж точно не с датой и временем.
        remembered = recall.returning_line(conv)
        reply = "С возвращением! " + (
            f"{remembered} Что-то изменилось с тех пор?"
            if remembered
            else "Расскажите, на чём мы остановились?"
        )
        conv.add("assistant", reply)
        store.save(conv)
        return reply
    conv.stage = STAGE_DISCOVERY
    reply = (
        "Здравствуйте! Я Фокси, консультант языковой школы «Фоксинбург» в "
        "Долгопрудном.\n\n"
        "Расскажите, для кого ищете занятия — и что для вас сейчас важнее "
        "всего?"
    )
    conv.add("assistant", reply)
    store.save(conv)
    return reply


__all__ = [
    "handle_message",
    "handle_start",
    "reset_conversation_locks",
    "_consult_with_context",
    "_drop_trailing_question",
    "_handoff_followup_reply",
    "_wants_manager",
]
