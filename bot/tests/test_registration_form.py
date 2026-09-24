"""Серверная валидация анкеты мини-приложения."""
from app import registration_form as rf
from app.memory import Conversation

OK = {
    "fio_parent": "Анна Петрова",
    "fio_child": "Маша",
    "child_birth": "15.03.2016",
    "phone": "+7 (916) 123-45-67",
    "consents": {"pd_child": True, "privacy": True, "marketing": True},
}


def test_valid_form_passes():
    form, errors = rf.validate(OK)
    assert errors == {}
    assert form.fio_parent == "Анна Петрова"
    assert form.birthday == "2016-03-15"
    assert form.age == ""
    assert form.phone.endswith("9161234567")


def test_age_instead_of_birthday():
    form, errors = rf.validate({**OK, "child_birth": "9 лет"})
    assert errors == {}
    assert form.age == "9" and form.birthday == ""


def test_garbage_names_rejected():
    _, errors = rf.validate({**OK, "fio_parent": "привет", "fio_child": "ааа"})
    assert set(errors) >= {"fio_parent", "fio_child"}


def test_bad_phone_and_birth_rejected():
    _, errors = rf.validate({**OK, "phone": "123", "child_birth": "1890-01-01"})
    assert set(errors) >= {"phone", "child_birth"}


def test_required_consents_enforced_marketing_optional():
    _, errors = rf.validate({**OK, "consents": {"pd_child": True, "privacy": False}})
    assert "consents" in errors
    form, errors = rf.validate({**OK, "consents": {"pd_child": True, "privacy": True}})
    assert errors == {} and form.consents["marketing"] is False


def test_apply_marks_registered_and_fills_lead():
    conv = Conversation(user_id="tg:1")
    form, _ = rf.validate(OK)
    rf.apply(conv, form)
    assert conv.registered is True
    assert conv.registration_step == ""
    assert conv.lead.fio_child == "Маша"
    assert conv.lead.birthday == "2016-03-15"


def test_apply_keeps_confirmed_phone_when_same_number():
    conv = Conversation(user_id="tg:1")
    conv.lead.set_phone("+79161234567", confirmed=True)
    form, _ = rf.validate(OK)
    rf.apply(conv, form)
    assert conv.lead.phone_confirmed is True
