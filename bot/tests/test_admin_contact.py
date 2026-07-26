"""Tests for admin notification contact block."""
from app.admin_router import _client_contact_block
from app.memory import Conversation, Lead


def test_max_user_with_phone():
    conv = Conversation(user_id="12345", max_username="anna_iv")
    conv.lead = Lead(fio_parent="Иванова Анна", phone="+79991234567")
    block = _client_contact_block(conv)
    assert "Иванова Анна" in block
    assert "+79991234567" in block
    assert "https://max.ru/anna_iv" in block
    assert "ID:" not in block  # phone + link present → no raw ID


def test_max_user_no_phone():
    conv = Conversation(user_id="12345", max_username="anna_iv")
    conv.lead = Lead(fio_parent="Иванова Анна")
    block = _client_contact_block(conv)
    assert "Иванова Анна" in block
    assert "https://max.ru/anna_iv" in block
    assert "ID: 12345" in block  # fallback


def test_telegram_user_with_phone():
    conv = Conversation(user_id="tg:987654")
    conv.lead = Lead(fio_parent="Петров Иван", phone="+79167654321")
    block = _client_contact_block(conv)
    assert "Петров Иван" in block
    assert "+79167654321" in block
    assert "tg://user?id=987654" in block
    assert "ID:" not in block


def test_telegram_user_no_phone():
    conv = Conversation(user_id="tg:987654")
    block = _client_contact_block(conv)
    assert "tg://user?id=987654" in block
    assert "ID: tg:987654" in block


def test_web_user_with_phone():
    conv = Conversation(user_id="web:session123")
    conv.lead = Lead(fio_parent="Сидорова Мария", phone="+79001112233")
    block = _client_contact_block(conv)
    assert "Сидорова Мария" in block
    assert "+79001112233" in block
    assert "Веб-виджет" in block
    assert "ID: web:session123" in block  # без ссылки ID показываем всегда


def test_web_user_no_phone():
    conv = Conversation(user_id="web:session123")
    block = _client_contact_block(conv)
    assert "Веб-виджет" in block
    assert "ID: web:session123" in block


def test_no_name_still_works():
    conv = Conversation(user_id="55555", max_username="user55")
    conv.lead = Lead(phone="+79998887766")
    block = _client_contact_block(conv)
    assert "+79998887766" in block
    assert "https://max.ru/user55" in block
    assert "👤" not in block  # no name → no name line
