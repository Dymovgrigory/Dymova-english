"""Фото в MAX: вложение image попадает в CRM с файлом и разбирается как задание.

Раньше в ветке message_created сообщение без текста отбрасывалось (`if not text:
return`), поэтому фото домашки от клиентов MAX не сохранялось и не разбиралось.
"""
from unittest.mock import AsyncMock, patch

import pytest

from app import main as main_module


def test_max_image_url_takes_first_image_attachment():
    attachments = [
        {"type": "sticker", "payload": {"url": "https://x/sticker.png"}},
        {"type": "image", "payload": {"url": "https://cdn.example/hw.jpg", "token": "t"}},
    ]
    assert main_module.max_image_url(attachments) == "https://cdn.example/hw.jpg"


def test_max_image_url_is_none_without_image():
    assert main_module.max_image_url([{"type": "audio", "payload": {"url": "https://x/a.ogg"}}]) is None
    assert main_module.max_image_url([]) is None
    assert main_module.max_image_url([{"type": "image", "payload": {}}]) is None


@pytest.mark.asyncio
async def test_max_photo_is_saved_to_crm_and_explained():
    max_client = AsyncMock()
    max_client.download_file = AsyncMock(return_value=b"jpeg-bytes")
    max_client.send_message = AsyncMock(return_value=True)
    message = {"sender": {"user_id": 42, "name": "Аня"}, "body": {"attachments": []}}
    with patch("app.main.save_homework_image", return_value="homework/abc.jpg") as save, \
         patch("app.main.explain_homework_image", new=AsyncMock(return_value="📘 Разбор")), \
         patch("app.crm_ingest.ingest_inbound", return_value={"conversation_id": 1, "customer_id": 1}) as ingest, \
         patch("app.crm_ingest.ingest_outbound") as outbound, \
         patch("app.crm_store.record_homework_request", return_value=1) as record:
        await main_module._handle_max_photo(
            "https://cdn.example/hw.jpg", "42", "", message, {"update_id": 7}, max_client
        )
    max_client.download_file.assert_awaited_once_with(
        "https://cdn.example/hw.jpg", main_module.MAX_HOMEWORK_IMAGE_BYTES
    )
    save.assert_called_once()
    ingest_kwargs = ingest.call_args.kwargs
    assert ingest.call_args.args[2] == "[фото]"
    assert ingest_kwargs["payload"] == {"image_path": "homework/abc.jpg"}
    max_client.send_message.assert_awaited()
    assert "Разбор" in max_client.send_message.await_args.args[1]
    outbound.assert_called_once()
    assert record.call_args.kwargs["input_type"] == "image"
    assert record.call_args.kwargs["image_path"] == "homework/abc.jpg"


@pytest.mark.asyncio
async def test_max_photo_download_failure_asks_for_smaller_photo():
    max_client = AsyncMock()
    max_client.download_file = AsyncMock(return_value=None)
    max_client.send_message = AsyncMock(return_value=True)
    message = {"sender": {"user_id": 42}, "body": {"attachments": []}}
    with patch("app.crm_ingest.ingest_inbound", return_value=None):
        await main_module._handle_max_photo(
            "https://cdn.example/big.jpg", "42", "", message, {}, max_client
        )
    text = max_client.send_message.await_args.args[1]
    assert "фото" in text.lower()


def test_text_with_image_attachment_keeps_normal_text_flow():
    """Регрессия: сообщение с текстом и картинкой (скриншот, превью ссылки) не
    должно уходить в разбор домашки вместо обычного ответа."""
    assert main_module.max_image_url([{"type": "image", "payload": {"url": "https://x/a.jpg"}}]) is not None
    routed = main_module.should_route_max_photo(
        "привет, какие у вас курсы?", [{"type": "image", "payload": {"url": "https://x/a.jpg"}}]
    )
    assert routed is False


def test_pure_photo_is_routed_to_homework_photo_flow():
    assert main_module.should_route_max_photo(
        "", [{"type": "image", "payload": {"url": "https://x/a.jpg"}}]
    ) is True
