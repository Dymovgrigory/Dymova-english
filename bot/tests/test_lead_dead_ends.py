"""Тупики на шаге заявки — по реальной переписке из прод-базы (10.08.2026).

Клиент писал «Привет», потом «Не будем завершать» — и оба раза получал
дословно один и тот же экран подтверждения с фразой «сначала завершим
заявку». Выйти можно было только словом «отмена», о котором никто не знает.
Плюс правка «Родитель Григорий, ребенок Аделина» применялась наполовину:
имя ребёнка приходилось диктовать вторым сообщением.
"""
import pytest

from app import lead_manager
from app.knowledge.kb import get_kb
from app.memory import Conversation, STAGE_DISCOVERY


class FakeBigBen:
    def __init__(self):
        self.created = []

    async def create_lead(self, lead, source="", note="", utm=None):
        self.created.append(lead)
        return True


class FakeMax:
    configured = False

    async def send_message(self, *a, **k):
        return True


def _ready_conv(user_id: str) -> Conversation:
    conv = Conversation(user_id=user_id)
    conv.lead.fio_parent = "Григорий"
    conv.lead.fio_child = "Папа"
    conv.lead.age = "9"
    conv.lead.phone = "+79999999999"
    conv.selected_branch = "Филиал на Лихачевском"
    conv.lead_step = "confirm"
    return conv


# --- выход из заявки -------------------------------------------------------


@pytest.mark.parametrize(
    "refusal",
    [
        "Не будем завершать",
        "не будем",
        "не хочу это заполнять",
        "хватит",
        "стоп",
        "не готов пока",
    ],
)
@pytest.mark.asyncio
async def test_refusal_exits_instead_of_repeating_the_form(refusal):
    conv = _ready_conv("dead-end-refusal")

    reply, submitted = await lead_manager.step(
        conv, refusal, get_kb(), FakeBigBen(), FakeMax()
    )

    assert submitted is False
    assert conv.stage == STAGE_DISCOVERY
    assert conv.lead_step == ""
    assert "Проверьте" not in reply


@pytest.mark.asyncio
async def test_explicit_send_wins_over_a_refusal_word():
    """«не буду ничего менять, отправляйте» — это согласие, а не отказ."""
    conv = _ready_conv("dead-end-send")
    bigben = FakeBigBen()

    reply, submitted = await lead_manager.step(
        conv, "не буду ничего менять, отправляйте", get_kb(), bigben, FakeMax()
    )

    assert submitted is True
    assert len(bigben.created) == 1


# --- правка нескольких полей одним сообщением ------------------------------


@pytest.mark.asyncio
async def test_correction_applies_every_field_in_one_message():
    conv = _ready_conv("dead-end-correct")
    conv.lead_step = "correcting"

    await lead_manager.step(
        conv, "Родитель Григорий, ребенок Аделина", get_kb(), FakeBigBen(), FakeMax()
    )

    assert conv.lead.fio_parent == "Григорий"
    assert conv.lead.fio_child == "Аделина"


@pytest.mark.asyncio
async def test_correction_of_child_and_phone_together():
    conv = _ready_conv("dead-end-correct-2")
    conv.lead_step = "correcting"

    await lead_manager.step(
        conv, "ребёнок Миша, телефон 89991234567", get_kb(), FakeBigBen(), FakeMax()
    )

    assert conv.lead.fio_child == "Миша"
    assert conv.lead.phone == "+79991234567"


@pytest.mark.asyncio
async def test_confirmation_names_what_changed():
    """Дословный повтор того же блока читается как «бот меня не услышал»."""
    conv = _ready_conv("dead-end-ack")
    conv.lead_step = "correcting"

    reply, _ = await lead_manager.step(
        conv, "ребенок Аделина", get_kb(), FakeBigBen(), FakeMax()
    )

    assert "Аделина" in reply
    assert reply != lead_manager._confirmation_text(conv)


# --- вопрос не по теме заявки ----------------------------------------------


@pytest.mark.asyncio
async def test_off_topic_question_is_handed_back_to_the_assistant():
    """Заявка не имеет права глушить вопрос: step сообщает вызывающему, что
    сообщение — не про заявку, и на него нужно ответить по существу."""
    conv = _ready_conv("dead-end-off-topic")

    reply, submitted = await lead_manager.step(
        conv, "А есть ли у вас китайский?", get_kb(), FakeBigBen(), FakeMax()
    )

    assert submitted is False
    assert reply == lead_manager.OFF_TOPIC
    assert conv.lead_step == "confirm"  # заявка не потеряна


@pytest.mark.asyncio
async def test_production_transcript_replayed_end_to_end():
    """Тот самый диалог из прод-базы, целиком через настоящую точку входа."""
    from app.ai_core import handle_message
    from app.memory import get_store

    uid = "dead-end-replay"
    store = get_store()
    store.reset(uid)

    await handle_message(uid, "Хочу записаться на пробное занятие")
    await handle_message(uid, "Григорий")
    await handle_message(uid, "Папа")
    await handle_message(uid, "9 лет")
    await handle_message(uid, "+79999999999")
    await handle_message(uid, "Лихачевский")

    reply = await handle_message(uid, "Нет")
    assert "поправить" in reply.lower()

    # Раньше обновлялся только родитель — ребёнка приходилось диктовать снова.
    reply = await handle_message(uid, "Родитель Григорий, ребенок Аделина")
    assert store.get(uid).lead.fio_child == "Аделина"
    assert "Аделина" in reply

    # Вопрос посреди заявки: раньше — «сначала завершим заявку» и тот же блок.
    reply = await handle_message(uid, "Привет")
    assert "сначала завершим" not in reply.lower()
    # И заявка при этом не должна потеряться: ответ на посторонний вопрос
    # уводил этап в handoff/discovery, после чего анкеты больше не было.
    assert store.get(uid).stage == "lead"
    assert "Проверьте" in reply

    # И выход без магического слова «отмена».
    reply = await handle_message(uid, "Не будем завершать")
    conv = store.get(uid)
    assert conv.stage == STAGE_DISCOVERY
    assert "Проверьте" not in reply
    assert conv.lead.fio_child == "Аделина"  # данные не потеряны


def test_pending_question_reminds_about_the_open_form():
    conv = _ready_conv("dead-end-pending")

    reminder = lead_manager.pending_question(conv)

    assert "Проверьте" in reminder
