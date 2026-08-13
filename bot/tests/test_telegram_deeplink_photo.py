"""Telegram: источник перехода из deeplink и разбор фото задания в чате."""
from __future__ import annotations

import pytest

import app.main as main
from app.main import parse_start_payload
from app.memory import get_store


class FakeTelegram:
    """Клиент, умеющий скачивать файлы — как настоящий."""

    def __init__(self, file_bytes: bytes | None = b"\x89PNG\r\n\x1a\nfake"):
        self.sent: list[dict] = []
        self.file_bytes = file_bytes
        self.download_calls: list[tuple[str, int]] = []

    async def send_message(self, chat_id, text, buttons=None):
        self.sent.append({"chat_id": chat_id, "text": text, "buttons": buttons})
        return True

    async def send_chat_action(self, chat_id, action="typing"):
        return True

    async def download_file(self, file_id, max_bytes):
        self.download_calls.append((file_id, max_bytes))
        return self.file_bytes


class BareTelegram:
    """Клиент без скачивания файлов — урезанный адаптер."""

    def __init__(self):
        self.sent: list[dict] = []

    async def send_message(self, chat_id, text, buttons=None):
        self.sent.append({"chat_id": chat_id, "text": text})
        return True


@pytest.fixture(autouse=True)
def _fresh_store():
    get_store()._data.clear()


# --------------------------- deeplink ---------------------------

def test_payload_parsed_into_utm_labels():
    """t.me/bot?start=utm_source-vk__utm_campaign=avgust приходит как /start …"""
    assert parse_start_payload("/start utm_source-vk__utm_campaign-avgust") == {
        "utm_source": "vk",
        "utm_campaign": "avgust",
    }


def test_unstructured_payload_is_kept_whole():
    """Код партнёра или id объявления терять нельзя, даже если формат чужой."""
    assert parse_start_payload("/start partner42") == {"deeplink": "partner42"}


def test_plain_start_has_no_payload():
    assert parse_start_payload("/start") == {}
    assert parse_start_payload("") == {}


def test_payload_length_is_bounded():
    """Полем из deeplink управляет кто угодно — в CRM оно должно уехать усечённым."""
    utm = parse_start_payload("/start " + "x" * 500)
    assert len(utm["deeplink"]) == 100


async def test_start_with_payload_is_recognised_as_start(monkeypatch):
    """Раньше сравнение шло со всей строкой, и /start с payload не срабатывал."""
    telegram = FakeTelegram()
    update = {
        "update_id": 900,
        "message": {"chat": {"id": 555}, "text": "/start utm_source-vk"},
    }
    await main._process_telegram_update(update, telegram)

    assert telegram.sent, "на /start с payload бот обязан ответить"
    conv = get_store().get("tg:555", platform="telegram")
    assert conv.utm.get("utm_source") == "vk"


async def test_first_source_wins_over_later_ones():
    """В бота человека привёл первый переход, а не последний."""
    telegram = FakeTelegram()
    for source in ("vk", "yandex"):
        await main._process_telegram_update(
            {"update_id": None, "message": {"chat": {"id": 556}, "text": f"/start utm_source-{source}"}},
            telegram,
        )
    conv = get_store().get("tg:556", platform="telegram")
    assert conv.utm["utm_source"] == "vk"


# --------------------------- фото задания ---------------------------

async def test_photo_is_sent_to_vision(monkeypatch):
    """Бот сам просит прислать фото — значит, обязан его разобрать."""
    seen = {}

    async def fake_explain(image_bytes, content_type, note=""):
        seen["note"] = note
        seen["bytes"] = image_bytes
        return "Смотри: здесь нужно поставить am/is/are по лицу подлежащего."

    monkeypatch.setattr(main, "explain_homework_image", fake_explain)
    telegram = FakeTelegram()
    update = {
        "update_id": 901,
        "message": {
            "chat": {"id": 557},
            "caption": "Задание 3",
            "photo": [
                {"file_id": "small", "file_size": 100},
                {"file_id": "large", "file_size": 900},
            ],
        },
    }
    await main._process_telegram_update(update, telegram)

    # Мелкое превью модель не прочитает — берём самый крупный размер.
    assert telegram.download_calls[0][0] == "large"
    assert seen["note"] == "Задание 3"
    assert "am/is/are" in telegram.sent[-1]["text"]


async def test_photo_download_limit_is_passed(monkeypatch):
    async def fake_explain(*args, **kwargs):
        return "ок"

    monkeypatch.setattr(main, "explain_homework_image", fake_explain)
    telegram = FakeTelegram()
    await main._process_telegram_update(
        {"update_id": 902, "message": {"chat": {"id": 558},
                                       "photo": [{"file_id": "f1", "file_size": 10}]}},
        telegram,
    )
    assert telegram.download_calls[0][1] == main.MAX_HOMEWORK_IMAGE_BYTES


async def test_undownloadable_photo_gets_a_human_answer(monkeypatch):
    telegram = FakeTelegram(file_bytes=None)
    await main._process_telegram_update(
        {"update_id": 903, "message": {"chat": {"id": 559},
                                       "photo": [{"file_id": "f1", "file_size": 10}]}},
        telegram,
    )
    reply = telegram.sent[-1]["text"].lower()
    assert "фото" in reply
    assert "ошибка" not in reply


async def test_vision_failure_falls_back_to_text_request(monkeypatch):
    async def fake_explain(*args, **kwargs):
        return None

    monkeypatch.setattr(main, "explain_homework_image", fake_explain)
    telegram = FakeTelegram()
    await main._process_telegram_update(
        {"update_id": 904, "message": {"chat": {"id": 560},
                                       "photo": [{"file_id": "f1", "file_size": 10}]}},
        telegram,
    )
    assert "текстом" in telegram.sent[-1]["text"].lower()


async def test_client_without_download_degrades_instead_of_failing():
    """Урезанный адаптер — не повод показывать пользователю ошибку."""
    telegram = BareTelegram()
    await main._process_telegram_update(
        {"update_id": 905, "message": {"chat": {"id": 561},
                                       "photo": [{"file_id": "f1", "file_size": 10}]}},
        telegram,
    )
    reply = telegram.sent[-1]["text"].lower()
    assert "фото" in reply
    assert "не так" not in reply


async def test_caption_with_its_own_intent_is_answered_as_text(monkeypatch):
    """«Сколько стоит?» с приложенной картинкой — вопрос, а не домашка."""
    async def fake_handle_message(user_id, text, platform="max"):
        return f"ответ на: {text}"

    monkeypatch.setattr(main, "handle_message", fake_handle_message)
    monkeypatch.setattr(main, "_contextual_buttons", lambda question, reply: [])
    telegram = FakeTelegram()

    await main._process_telegram_update(
        {"update_id": 907, "message": {"chat": {"id": 563},
                                       "photo": [{"file_id": "f1", "file_size": 10}],
                                       "caption": "Сколько стоит?"}},
        telegram,
    )
    assert telegram.download_calls == []
    assert "Сколько стоит?" in telegram.sent[-1]["text"]


async def test_photo_without_file_id_is_ignored():
    telegram = FakeTelegram()
    await main._process_telegram_update(
        {"update_id": 906, "message": {"chat": {"id": 562}, "photo": [{"file_size": 10}]}},
        telegram,
    )
    assert telegram.sent == []
