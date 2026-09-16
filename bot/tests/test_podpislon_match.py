"""Сопоставление контакта Подпислона с карточкой ученика в CRM.

Правило задано школой: совпасть должны И фамилия с именем ребёнка, И телефон.
Одно совпадение — работаем, ноль или несколько — не трогаем ничего.
"""
from app.platform.podpislon_sync import child_fields_for, match_student, missing_fields, same_first_name


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


class TestMatchByDocumentName:
    """Анкету заполнил другой родственник — ребёнок назван в имени договора.

    Живые случаи из сверки 2026-09-16.
    """

    def test_child_named_in_contract_title(self):
        c = contact(child_fio="", parent_last_name="Колпакова",
                    doc_name="Шестакова Милана 26-27 уч год.pdf")
        assert match_student(c, [student(fio="Шестакова Милана")])["id"] == 1

    def test_title_picks_one_of_two_children_on_phone(self):
        c = contact(child_fio="", parent_last_name="Карасева",
                    doc_name="Договор Карасев Владимир.pdf")
        students = [student(id=1, fio="Карасев Владимир"), student(id=2, fio="Карасева Анисия")]
        assert match_student(c, students)["id"] == 1

    def test_title_without_spaces(self):
        c = contact(child_fio="", parent_last_name="Смелая", doc_name="СмелыйРусланЛето.pdf")
        assert match_student(c, [student(fio="Смелый Руслан")])["id"] == 1

    def test_title_used_when_anketa_child_differs(self):
        c = contact(child_fio="Иванова Мария", doc_name="Иванов Владислав договор.pdf")
        assert match_student(c, [student(fio="Иванов Владислав")])["id"] == 1

    def test_title_naming_nobody_is_not_a_match(self):
        c = contact(child_fio="", parent_last_name="Прохорова",
                    doc_name="Прохоров Максим новый уч. год. 2026.pdf")
        students = [student(id=1, fio="Прохоров Миша"), student(id=2, fio="Прохорова Алиса")]
        assert match_student(c, students) is None

    def test_title_still_requires_the_phone(self):
        c = contact(child_fio="", doc_name="Шестакова Милана.pdf")
        assert match_student(c, [student(fio="Шестакова Милана", parent_phone="79990000000")]) is None


class TestNameOrder:
    def test_name_before_surname_in_crm(self):
        c = contact(child_fio="Бондарь Тимур Антонович")
        assert match_student(c, [student(fio="Тимур Бондарь")])["id"] == 1


class TestChildFieldsFor:
    def test_kept_when_card_is_that_child(self):
        fields = {"fio": "Иванов Владислав", "birthday": "2019-08-11", "passport": "40"}
        assert child_fields_for(fields, student(fio="Иванов Владислав Петрович")) == fields

    def test_dropped_when_card_found_by_title_or_parent(self):
        fields = {"fio": "Иванова Мария", "birthday": "2019-08-11", "passport": "40"}
        assert child_fields_for(fields, student(fio="Иванов Владислав")) == {
            "fio": "", "birthday": "", "passport": "40"}


class TestShortNames:
    """Полное и уменьшительное имя — один клиент (сверка 2026-09-16)."""

    def test_pairs(self):
        assert same_first_name("Миша", "Михаил")
        assert same_first_name("Таня", "Татьяна")
        assert same_first_name("Настя", "Анастасия")
        assert same_first_name("Саша", "Александра")
        assert same_first_name("Наталья", "Наталия")
        assert same_first_name("Софья", "Соня")
        assert same_first_name("Алёша", "Алексей")

    def test_different_names(self):
        assert not same_first_name("Аня", "Таня")
        assert not same_first_name("Миша", "Максим")

    def test_title_with_full_name_card_with_short(self):
        c = contact(child_fio="", parent_last_name="Прохорова",
                    doc_name="Прохоров Михаил новый уч. год. 2026.pdf")
        students = [student(id=1, fio="Прохоров Миша"), student(id=2, fio="Прохорова Алиса")]
        assert match_student(c, students)["id"] == 1

    def test_title_with_short_name_card_with_full(self):
        c = contact(child_fio="", parent_last_name="Кузнецова",
                    doc_name="Погорелова Таня договор.pdf")
        assert match_student(c, [student(fio="Погорелова Татьяна")])["id"] == 1

    def test_anketa_short_name(self):
        c = contact(child_fio="Иванов Влад")
        assert match_student(c, [student(fio="Иванов Владислав")])["id"] == 1

    def test_short_form_inside_other_word_is_not_a_match(self):
        # «аня» есть внутри «Таня» — это не Анна.
        c = contact(child_fio="", parent_last_name="Сидорова", doc_name="Петрова Таня.pdf")
        assert match_student(c, [student(fio="Петрова Анна")]) is None

    def test_fio_with_short_name_is_not_a_conflict(self):
        upd, conflicts = missing_fields(student(fio="Прохоров Миша"), {"fio": "Прохоров Михаил Олегович"})
        assert (upd, conflicts) == ({}, {})
