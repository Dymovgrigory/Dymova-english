"""Согласия на обработку ПД: хранение, версия, отметка по умолчанию."""
import pytest

from app import consents, crm_store


@pytest.fixture(autouse=True)
def fresh_db():
    crm_store.reset()
    yield
    crm_store.reset()


def test_required_consents_missing_by_default():
    assert consents.has_required("telegram", "tg:1") is False


def test_record_and_read_back_with_version_and_default_flag():
    consents.record("telegram", "tg:1",
                    {"pd_child": True, "privacy": True, "marketing": True},
                    channel="miniapp")
    got = consents.latest("telegram", "tg:1")
    assert got["pd_child"]["accepted"] is True
    assert got["pd_child"]["legal_version"] == consents.LEGAL_VERSION
    assert got["marketing"]["default_checked"] is True
    assert got["pd_child"]["default_checked"] is False
    assert consents.has_required("telegram", "tg:1") is True


def test_unchecked_marketing_is_stored_as_declined():
    consents.record("max", "42",
                    {"pd_child": True, "privacy": True, "marketing": False},
                    channel="miniapp")
    assert consents.latest("max", "42")["marketing"]["accepted"] is False
    assert consents.has_required("max", "42") is True


def test_latest_record_wins():
    consents.record("max", "42", {"pd_child": True, "privacy": True, "marketing": True}, channel="miniapp")
    consents.record("max", "42", {"pd_child": True, "privacy": True, "marketing": False}, channel="miniapp")
    assert consents.latest("max", "42")["marketing"]["accepted"] is False


def test_summary_line_mentions_every_type_and_version():
    consents.record("telegram", "tg:1", {"pd_child": True, "privacy": True, "marketing": True}, channel="miniapp")
    line = consents.summary_line("telegram", "tg:1")
    assert "ПД ребёнка: да" in line
    assert "политика: да" in line
    assert "рассылки: да" in line
    assert consents.LEGAL_VERSION in line


def test_parse_accepted_defaults_missing_to_false():
    # Общий разбор для анкеты и ручки /api/miniapp/consents: неотмеченный
    # или отсутствующий чекбокс — это False, а не пропуск ключа.
    assert consents.parse_accepted({"pd_child": True}) == {
        "pd_child": True, "privacy": False, "marketing": False,
    }


def test_parse_accepted_ignores_non_dict_input():
    assert consents.parse_accepted(None) == {
        "pd_child": False, "privacy": False, "marketing": False,
    }
