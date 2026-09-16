"""Сопоставление контакта Подпислона с карточкой ученика в CRM.

Правило задано школой: совпасть должны И фамилия с именем ребёнка, И телефон.
Одно совпадение — работаем, ноль или несколько — не трогаем ничего.
"""
from app.platform.podpislon_sync import match_student, missing_fields


def student(**kw):
    base = {
        "id": 1, "fio": "Иванов Владислав", "parent_phone": "+7 (925) 880-33-33",
        "phone": "", "phone1": "", "main_phone": "",
        "birthday": "", "parentname": "", "parent_birthday": "",
        "passport": "", "home_address": "", "email": "",
    }
    base.update(kw)
    return base


def contact(**kw):
    base = {
        "child_fio": "Иванов Владислав",
        "phone": "79258803333",
    }
    base.update(kw)
    return base


class TestMatchStudent:
    def test_matches_on_child_name_and_phone(self):
        assert match_student(contact(), [student()])["id"] == 1

    def test_phone_formats_are_normalised(self):
        students = [student(parent_phone="8 925 880 33 33")]
        assert match_student(contact(phone="+7-925-880-33-33"), students)["id"] == 1

    def test_phone_found_in_any_phone_field(self):
        students = [student(parent_phone="", phone1="79258803333")]
        assert match_student(contact(), students)["id"] == 1

    def test_name_case_and_yo_are_ignored(self):
        students = [student(fio="СЕМЁНОВА  АЛЁНА")]
        assert match_student(contact(child_fio="семенова алена"), students)["id"] == 1

    def test_patronymic_in_crm_does_not_block_match(self):
        students = [student(fio="Иванов Владислав Петрович")]
        assert match_student(contact(), students)["id"] == 1

    def test_right_phone_wrong_child_is_not_a_match(self):
        # Второй ребёнок в той же семье: телефон общий, имя другое.
        students = [student(fio="Иванова Мария")]
        assert match_student(contact(), students) is None

    def test_right_child_wrong_phone_is_not_a_match(self):
        students = [student(parent_phone="79990000000")]
        assert match_student(contact(), students) is None

    def test_two_candidates_are_rejected_as_ambiguous(self):
        students = [student(id=1), student(id=2)]
        assert match_student(contact(), students) is None

    def test_no_students_at_all(self):
        assert match_student(contact(), []) is None

    def test_contact_without_child_name_and_parent_surname_is_not_matched(self):
        assert match_student(contact(child_fio=""), [student()]) is None


class TestMatchWithoutChildName:
    """Анкета без ФИО ребёнка: одна карточка на телефон + фамилия родителя.

    Случай Ворожеевой (2026-09-16): мама не заполнила ФИО ребёнка.
    """

    def test_single_card_with_parent_surname(self):
        students = [student(fio="Ворожеева Есения")]
        c = contact(child_fio="", parent_last_name="Ворожеева")
        assert match_student(c, students)["id"] == 1

    def test_mother_and_son_surname_forms(self):
        c = contact(child_fio="", parent_last_name="Ворожеева")
        assert match_student(c, [student(fio="Ворожеев Иван")])["id"] == 1
        c = contact(child_fio="", parent_last_name="Пузырёва")
        assert match_student(c, [student(fio="Пузырев Степан")])["id"] == 1
        c = contact(child_fio="", parent_last_name="Троицкая")
        assert match_student(c, [student(fio="Троицкий Олег")])["id"] == 1

    def test_father_and_daughter_surname_forms(self):
        c = contact(child_fio="", parent_last_name="Иванов")
        assert match_student(c, [student(fio="Иванова Мария")])["id"] == 1

    def test_different_surname_is_not_a_match(self):
        c = contact(child_fio="", parent_last_name="Петрова")
        assert match_student(c, [student(fio="Ворожеева Есения")]) is None

    def test_two_children_on_one_phone_are_ambiguous(self):
        c = contact(child_fio="", parent_last_name="Иванова")
        students = [student(id=1, fio="Иванов Владислав"), student(id=2, fio="Иванова Мария")]
        assert match_student(c, students) is None

    def test_wrong_phone_is_not_a_match(self):
        c = contact(child_fio="", parent_last_name="Иванова")
        assert match_student(c, [student(parent_phone="79990000000")]) is None

    def test_contact_without_phone_is_never_matched(self):
        assert match_student(contact(phone=""), [student()]) is None


class TestMissingFields:
    def test_fills_only_empty_fields(self):
        data = {"passport": "40 64 543333", "home_address": "г. Долгопрудный"}
        upd, conflicts = missing_fields(student(home_address="Старый адрес"), data)
        assert upd == {"passport": "40 64 543333"}
        assert conflicts == {"home_address": ("Старый адрес", "г. Долгопрудный")}

    def test_identical_value_is_neither_update_nor_conflict(self):
        data = {"home_address": "г. Долгопрудный"}
        upd, conflicts = missing_fields(student(home_address="г. Долгопрудный"), data)
        assert upd == {}
        assert conflicts == {}

    def test_blank_incoming_values_are_skipped(self):
        upd, conflicts = missing_fields(student(), {"passport": "", "email": None})
        assert upd == {}
        assert conflicts == {}

    def test_whitespace_only_crm_value_counts_as_empty(self):
        upd, _ = missing_fields(student(email="   "), {"email": "a@b.ru"})
        assert upd == {"email": "a@b.ru"}


class TestMissingFieldsEquivalence:
    """Одно и то же, записанное по-разному, — не расхождение."""

    def test_same_date_in_different_formats(self):
        upd, conflicts = missing_fields(
            student(birthday="2018-05-28"), {"birthday": "2018-05-28"})
        assert (upd, conflicts) == ({}, {})
        upd, conflicts = missing_fields(
            student(parent_birthday="1992-06-21"), {"parent_birthday": "21.06.1992"})
        assert (upd, conflicts) == ({}, {})

    def test_crm_zero_date_counts_as_empty(self):
        upd, conflicts = missing_fields(
            student(parent_birthday="0000-00-00"), {"parent_birthday": "1991-09-20"})
        assert upd == {"parent_birthday": "1991-09-20"}
        assert conflicts == {}

    def test_really_different_date_is_a_conflict(self):
        _, conflicts = missing_fields(
            student(birthday="2018-05-28"), {"birthday": "2018-05-29"})
        assert conflicts == {"birthday": ("2018-05-28", "2018-05-29")}

    def test_child_fio_without_patronymic_in_crm(self):
        upd, conflicts = missing_fields(
            student(fio="Пузырев Степан"), {"fio": "Пузырёв Степан Иванович"})
        assert (upd, conflicts) == ({}, {})

    def test_parent_first_name_only_in_crm(self):
        upd, conflicts = missing_fields(
            student(parentname="Алена"), {"parentname": "Пузырёва Алёна Сергеевна"})
        assert (upd, conflicts) == ({}, {})

    def test_different_parent_is_a_conflict(self):
        _, conflicts = missing_fields(
            student(parentname="Ольга"), {"parentname": "Луговой Андрей Петрович"})
        assert "parentname" in conflicts


class TestMissingFieldsPlaceholders:
    def test_dash_in_crm_counts_as_empty(self):
        upd, conflicts = missing_fields(
            student(passport="-", home_address=" — "),
            {"passport": "4611 537169", "home_address": "Долгопрудный"})
        assert upd == {"passport": "4611 537169", "home_address": "Долгопрудный"}
        assert conflicts == {}

    def test_same_phone_in_different_formats(self):
        upd, conflicts = missing_fields(
            student(parent_phone="9151415181"), {"parent_phone": "89151415181"})
        assert (upd, conflicts) == ({}, {})

    def test_mama_papa_notes_in_parentname(self):
        upd, conflicts = missing_fields(
            student(parentname="Мама Дарья Александровна"),
            {"parentname": "Волынец Дарья Александровна"})
        assert (upd, conflicts) == ({}, {})
