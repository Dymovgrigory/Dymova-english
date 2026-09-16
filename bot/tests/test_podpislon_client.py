"""Разбор контакта Подпислона в поля карточки ученика."""
from app.platform.podpislon import CUSTOM_FIELDS, contact_id_of, to_crm_fields


def contact(**kw):
    base = {
        "id": 456,
        "last_name": "Иванова", "name": "Юлия", "surname": "Евгеньевна",
        "phone": "79258803333",
        "email": "julia@example.ru",
        "passport": {
            "number": "40 64 543333",
            "issued_by": "ГУ МВД России по Московской обл.",
            "issued_at": "2020-04-02T00:00:00+03:00",
            "issuer_code": "770-001",
            "address": "Долгопрудный, Лихачевское шоссе, 1 кв 1",
            "birth_date": "1978-01-18T00:00:00+03:00",
        },
        "custom_fields": [
            {"code": CUSTOM_FIELDS["child_fio"], "value": "Иванов Владислав"},
            {"code": CUSTOM_FIELDS["child_birthday"], "value": "11.08.2019"},
        ],
    }
    base.update(kw)
    return base


class TestToCrmFields:
    def test_child_comes_from_custom_fields(self):
        out = to_crm_fields(contact())
        assert out["fio"] == "Иванов Владислав"
        assert out["birthday"] == "11.08.2019"

    def test_parent_fio_is_assembled_in_russian_order(self):
        assert to_crm_fields(contact())["parentname"] == "Иванова Юлия Евгеньевна"

    def test_passport_collapses_into_one_line(self):
        out = to_crm_fields(contact())
        assert out["passport"] == (
            "40 64 543333, выдан ГУ МВД России по Московской обл., "
            "02.04.2020, код подразделения 770-001")

    def test_dates_are_converted_from_iso(self):
        assert to_crm_fields(contact())["parent_birthday"] == "18.01.1978"

    def test_address_comes_from_passport(self):
        out = to_crm_fields(contact())
        assert out["home_address"] == "Долгопрудный, Лихачевское шоссе, 1 кв 1"

    def test_email_falls_back_to_custom_field(self):
        c = contact(email="")
        c["custom_fields"].append(
            {"code": CUSTOM_FIELDS["email"], "value": "backup@example.ru"})
        assert to_crm_fields(c)["email"] == "backup@example.ru"

    def test_empty_passport_does_not_crash(self):
        out = to_crm_fields(contact(passport=None))
        assert out["passport"] == ""
        assert out["parent_birthday"] == ""
        assert out["fio"] == "Иванов Владислав"

    def test_partial_passport_skips_missing_parts(self):
        out = to_crm_fields(contact(passport={"number": "40 64 543333"}))
        assert out["passport"] == "40 64 543333"

    def test_missing_custom_field_gives_empty_string(self):
        assert to_crm_fields(contact(custom_fields=[]))["fio"] == ""


class TestContactIdOf:
    def test_reads_from_contacts_array(self):
        assert contact_id_of({"contacts": [{"id": 77}], "contact": {"id": 99}}) == 77

    def test_falls_back_to_legacy_contact_object(self):
        assert contact_id_of({"contacts": [], "contact": {"id": 99}}) == 99

    def test_none_when_document_has_no_contact(self):
        assert contact_id_of({"contacts": [], "contact": {}}) is None
