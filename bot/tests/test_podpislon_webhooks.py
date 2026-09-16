"""Приёмник вебхуков Подпислона: подтверждение события и загрузка договора."""
import pytest

from app.platform import podpislon_webhooks as hooks


class FakeCrm:
    def __init__(self, students=None, files=None):
        self.students = students if students is not None else []
        self.files = files or []
        self.updated = []
        self.uploaded = []

    async def find_students_by_phone(self, phone):
        return list(self.students)

    async def update_student(self, student_id, fields):
        self.updated.append((student_id, fields))
        return {}

    async def list_student_files(self, student_id):
        return list(self.files)

    async def upload_student_file(self, student_id, filename, content):
        self.uploaded.append((student_id, filename, content))
        return {"success": True}


class FakePodpislon:
    def __init__(self, doc=None, contact=None):
        self._doc = doc
        self._contact = contact or {}
        self.downloaded = []

    async def get_document(self, file_id):
        return self._doc

    async def get_contact(self, contact_id):
        return self._contact

    async def download_pdf(self, file_id):
        self.downloaded.append(file_id)
        return b"%PDF-signed"

    # чистые функции берём у настоящего модуля
    @staticmethod
    def contact_id_of(doc):
        from app.platform.podpislon import contact_id_of
        return contact_id_of(doc)

    @staticmethod
    def is_signed(doc):
        from app.platform.podpislon import is_signed
        return is_signed(doc)

    @staticmethod
    def to_crm_fields(contact):
        from app.platform.podpislon import to_crm_fields
        return to_crm_fields(contact)


def contact():
    from app.platform.podpislon import CUSTOM_FIELDS
    return {
        "id": 456, "last_name": "Кузнецова", "name": "Мария", "surname": "Ивановна",
        "phone": "79258803333", "email": "m@example.ru",
        "passport": {"number": "40 64 543333", "address": "Долгопрудный"},
        "custom_fields": [
            {"code": CUSTOM_FIELDS["child_fio"], "value": "Кузнецов Никита"},
            {"code": CUSTOM_FIELDS["child_birthday"], "value": "11.08.2019"},
        ],
    }


def student(**kw):
    base = {"id": 42, "fio": "Кузнецов Никита", "parent_phone": "+7 925 880-33-33",
            "passport": "", "home_address": "", "email": "", "parentname": "",
            "birthday": "", "parent_birthday": "", "phone": "", "phone1": "",
            "main_phone": ""}
    base.update(kw)
    return base


@pytest.fixture
def wired(monkeypatch):
    def _wire(crm, pod):
        monkeypatch.setattr(hooks, "crm", crm)
        monkeypatch.setattr(hooks, "podpislon", pod)
    return _wire


class TestContractFilename:
    def test_uses_child_fio_and_year(self):
        assert hooks.contract_filename("Кузнецов Никита") == "Кузнецов Никита 26_27.pdf"

    def test_strips_characters_that_break_filenames(self):
        assert hooks.contract_filename("Иванов/Петров") == "Иванов Петров 26_27.pdf"

    def test_falls_back_when_name_is_empty(self):
        assert hooks.contract_filename("") == "Договор 26_27.pdf"


class TestHandleSigned:
    @pytest.mark.asyncio
    async def test_uploads_pdf_and_fills_empty_fields(self, wired):
        crm = FakeCrm(students=[student()])
        pod = FakePodpislon(doc={"id": 1, "status": "30", "contacts": [{"sid": "NDU2"}]},
                            contact=contact())
        wired(crm, pod)

        out = await hooks.handle_signed(1)

        assert out["matched"] and out["uploaded"]
        assert crm.uploaded == [(42, "Кузнецов Никита 26_27.pdf", b"%PDF-signed")]
        student_id, fields = crm.updated[0]
        assert student_id == 42
        assert fields["passport"] == "40 64 543333"
        assert fields["parentname"] == "Кузнецова Мария Ивановна"

    @pytest.mark.asyncio
    async def test_anketa_without_child_name_uses_parent_surname(self, wired):
        crm = FakeCrm(students=[student()])
        c = contact()
        c["custom_fields"] = []  # мама не заполнила ФИО ребёнка
        pod = FakePodpislon(doc={"id": 1, "status": "30", "contacts": [{"sid": "NDU2"}]},
                            contact=c)
        wired(crm, pod)

        out = await hooks.handle_signed(1)

        assert out["matched"] and out["uploaded"]
        assert crm.uploaded == [(42, "Кузнецов Никита 26_27.pdf", b"%PDF-signed")]

    @pytest.mark.asyncio
    async def test_document_that_is_not_signed_yet_is_skipped(self, wired):
        crm = FakeCrm(students=[student()])
        pod = FakePodpislon(doc={"id": 1, "status": "20", "contacts": [{"sid": "NDU2"}]},
                            contact=contact())
        wired(crm, pod)

        out = await hooks.handle_signed(1)

        assert out == {"verified": True, "signed": False}
        assert crm.uploaded == [] and crm.updated == []

    @pytest.mark.asyncio
    async def test_unverified_document_is_dropped(self, wired):
        crm = FakeCrm(students=[student()])
        wired(crm, FakePodpislon(doc=None))

        out = await hooks.handle_signed(999)

        assert out == {"verified": False}
        assert crm.uploaded == [] and crm.updated == []

    @pytest.mark.asyncio
    async def test_no_match_touches_nothing(self, wired):
        crm = FakeCrm(students=[student(fio="Другой Ребёнок")])
        pod = FakePodpislon(doc={"id": 1, "status": "30", "contacts": [{"sid": "NDU2"}]},
                            contact=contact())
        wired(crm, pod)

        out = await hooks.handle_signed(1)

        assert out["matched"] is False
        assert crm.uploaded == [] and crm.updated == []

    @pytest.mark.asyncio
    async def test_ambiguous_match_touches_nothing(self, wired):
        crm = FakeCrm(students=[student(id=1), student(id=2)])
        pod = FakePodpislon(doc={"id": 1, "status": "30", "contacts": [{"sid": "NDU2"}]},
                            contact=contact())
        wired(crm, pod)

        assert (await hooks.handle_signed(1))["matched"] is False
        assert crm.uploaded == []

    @pytest.mark.asyncio
    async def test_same_contract_is_not_uploaded_twice(self, wired):
        crm = FakeCrm(students=[student()],
                      files=[{"name": "Кузнецов Никита 26_27.pdf"}])
        pod = FakePodpislon(doc={"id": 1, "status": "30", "contacts": [{"sid": "NDU2"}]},
                            contact=contact())
        wired(crm, pod)

        out = await hooks.handle_signed(1)

        assert out["uploaded"] is False
        assert crm.uploaded == [] and pod.downloaded == []

    @pytest.mark.asyncio
    async def test_filled_field_is_never_overwritten(self, wired):
        crm = FakeCrm(students=[student(home_address="Адрес от администратора")])
        pod = FakePodpislon(doc={"id": 1, "status": "30", "contacts": [{"sid": "NDU2"}]},
                            contact=contact())
        wired(crm, pod)

        out = await hooks.handle_signed(1)

        assert "home_address" not in crm.updated[0][1]
        assert "home_address" in out["conflicts"]


class TestHandleClientData:
    @pytest.mark.asyncio
    async def test_fills_card_without_touching_files(self, wired):
        crm = FakeCrm(students=[student()])
        wired(crm, FakePodpislon(contact=contact()))

        out = await hooks.handle_client_data(456)

        assert out["matched"] and crm.updated and crm.uploaded == []

    @pytest.mark.asyncio
    async def test_no_match_is_reported_not_guessed(self, wired):
        crm = FakeCrm(students=[])
        wired(crm, FakePodpislon(contact=contact()))

        assert await hooks.handle_client_data(456) == {"matched": False}
        assert crm.updated == []


class TestDedup:
    def test_second_identical_event_is_a_duplicate(self):
        hooks._seen.clear()
        assert hooks._dedup("DOCUMENT_SIGNED:1") is False
        assert hooks._dedup("DOCUMENT_SIGNED:1") is True

    def test_different_events_are_independent(self):
        hooks._seen.clear()
        assert hooks._dedup("DOCUMENT_SIGNED:1") is False
        assert hooks._dedup("DOCUMENT_SIGNED:2") is False


class TestAlreadyUploaded:
    """Договор уже в карточке — второй раз не кладём.

    Администраторы грузят договоры и руками — под названием из Подпислона
    (Ворожеева, 2026-09-16: «Ежемесячный ракета 26_27.pdf»).
    """

    def test_our_filename(self):
        files = [{"name": "Кузнецов Никита 26_27.pdf", "size": 1}]
        assert hooks.already_uploaded(files, filename="Кузнецов Никита 26_27.pdf",
                                      doc_name="Договор.pdf", pdf_size=999)

    def test_uploaded_by_hand_under_podpislon_name(self):
        files = [{"name": "Ежемесячный ракета 26_27.pdf", "size": 5}]
        assert hooks.already_uploaded(files, filename="Ворожеева Есения 26_27.pdf",
                                      doc_name="Ежемесячный ракета 26_27.pdf", pdf_size=999)

    def test_same_pdf_under_any_name(self):
        files = [{"name": "скан.pdf", "size": "136697"}]
        assert hooks.already_uploaded(files, filename="Ворожеева Есения 26_27.pdf",
                                      doc_name="Договор.pdf", pdf_size=136697)

    def test_last_season_contract_does_not_count(self):
        files = [{"name": "Договор Ворожеева Есения.pdf", "size": 236427}]
        assert not hooks.already_uploaded(files, filename="Ворожеева Есения 26_27.pdf",
                                          doc_name="Ежемесячный ракета 26_27.pdf",
                                          pdf_size=136697)


class TestHandleSignedDedup:
    @pytest.mark.asyncio
    async def test_skips_contract_uploaded_by_hand(self, wired):
        crm = FakeCrm(students=[student()],
                      files=[{"name": "Договор ракета.pdf", "size": 0}])
        pod = FakePodpislon(doc={"id": 1, "status": "30", "name": "Договор ракета.pdf",
                                 "contacts": [{"sid": "NDU2"}]},
                            contact=contact())
        wired(crm, pod)

        out = await hooks.handle_signed(1)

        assert out["uploaded"] is False
        assert crm.uploaded == []
