"""Приёмник вебхуков Подпислона: POST /api/webhooks/podpislon.

Поток: form-urlencoded → отвечаем 200 сразу → обработка в фоне, чтобы
Подпислон не ретраил из-за нашей медлительности.

О подлинности события. В теле приходит поле SIGNATURE, но алгоритм его
расчёта сервис не публикует, поэтому проверить его нечем. Вместо этого мы
событию не доверяем вовсе: FILE_ID и CLIENT_ID перепроверяются запросом в
Подпислон под нашим ключом, и дальше работаем только с тем, что вернул сам
сервис. Подделать событие про чужой документ так нельзя — оно не
подтвердится. Если Подпислон опишет алгоритм, проверку подписи стоит
добавить дополнительно.

События (см. podpislon-api.yaml):
  DOCUMENT_SIGNED               — FILE_ID: договор подписан;
  CLIENT_DATA_REQUEST_SUBMITTED — CLIENT_ID: клиент заполнил анкету;
  DOCUMENT_OPENED               — просмотр, нам не интересен.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.platform import bigben_internal as crm
from app.platform import podpislon, podpislon_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["podpislon-webhooks"])

_HANDLED_EVENTS = {"DOCUMENT_SIGNED", "CLIENT_DATA_REQUEST_SUBMITTED"}

# Уже обработанные события — Подпислон повторяет доставку при сбоях.
_seen: set[str] = set()
_SEEN_LIMIT = 5000


def _dedup(key: str) -> bool:
    """True, если это событие уже обрабатывали."""
    if key in _seen:
        return True
    if len(_seen) >= _SEEN_LIMIT:
        _seen.clear()
    _seen.add(key)
    return False


def contract_filename(student_fio: str, year: str = "26_27") -> str:
    """«Кузнецов Никита 26_27.pdf» — как школа называет договоры вручную."""
    clean = " ".join(str(student_fio or "").split()) or "Договор"
    for ch in '/\\:*?"<>|':
        clean = clean.replace(ch, " ")
    return f"{' '.join(clean.split())} {year}.pdf"


async def _resolve(contact_id: int) -> tuple[dict, dict, dict | None]:
    """Контакт Подпислона, его поля для CRM и найденная карточка ученика."""
    contact = await podpislon.get_contact(contact_id)
    fields = podpislon.to_crm_fields(contact)
    candidates = await crm.find_students_by_phone(fields["parent_phone"])
    student = podpislon_sync.match_student(
        {"child_fio": fields["fio"], "phone": fields["parent_phone"],
         "parent_last_name": fields["parent_last_name"]},
        candidates)
    return contact, fields, student


async def _fill_card(student: dict, fields: dict) -> dict:
    """Дозаполняет пустые поля карточки. Возвращает что обновили и что разошлось."""
    updates, conflicts = podpislon_sync.missing_fields(student, fields)
    if updates:
        await crm.update_student(student["id"], updates)
        logger.info("podpislon: карточка %s дозаполнена: %s",
                    student["id"], ", ".join(updates))
    if conflicts:
        logger.warning("podpislon: расхождения по карточке %s: %s",
                       student["id"], conflicts)
    return {"updates": updates, "conflicts": conflicts}


async def handle_client_data(client_id: int) -> dict:
    """Клиент заполнил анкету — переносим данные в карточку, не дожидаясь подписи."""
    _, fields, student = await _resolve(client_id)
    if not student:
        logger.warning("podpislon: карточка не найдена по анкете "
                       "(ребёнок %r, телефон %r) — нужен разбор вручную",
                       fields["fio"], fields["parent_phone"])
        return {"matched": False}
    return {"matched": True, "student_id": student["id"],
            **await _fill_card(student, fields)}


async def handle_signed(file_id: int) -> dict:
    """Договор подписан — кладём PDF в карточку и дозаполняем её."""
    doc = await podpislon.get_document(file_id)
    if not doc:
        logger.warning("podpislon: документ %s не подтверждён — событие отброшено",
                       file_id)
        return {"verified": False}

    if not podpislon.is_signed(doc):
        logger.warning("podpislon: документ %s в статусе %r, а не «Подписан» — пропускаем",
                       file_id, doc.get("status_text") or doc.get("status"))
        return {"verified": True, "signed": False}

    contact_id = podpislon.contact_id_of(doc)
    if not contact_id:
        logger.warning("podpislon: у документа %s нет контакта", file_id)
        return {"verified": True, "matched": False}

    _, fields, student = await _resolve(contact_id)
    if not student:
        logger.warning("podpislon: карточка не найдена по договору %s "
                       "(ребёнок %r, телефон %r) — нужен разбор вручную",
                       file_id, fields["fio"], fields["parent_phone"])
        return {"verified": True, "matched": False}

    result = {"verified": True, "matched": True, "student_id": student["id"],
              **await _fill_card(student, fields)}

    filename = contract_filename(fields["fio"] or student.get("fio"))
    existing = {str(f.get("name") or "") for f in
                await crm.list_student_files(student["id"])}
    if filename in existing:
        logger.info("podpislon: %s уже есть в карточке %s — пропускаем",
                    filename, student["id"])
        return {**result, "uploaded": False}

    pdf = await podpislon.download_pdf(file_id)
    await crm.upload_student_file(student["id"], filename, pdf)
    logger.info("podpislon: %s загружен в карточку %s (%d байт)",
                filename, student["id"], len(pdf))
    return {**result, "uploaded": True, "filename": filename}


async def _process(event: str, payload: dict) -> None:
    try:
        if event == "DOCUMENT_SIGNED":
            await handle_signed(int(payload["FILE_ID"]))
        elif event == "CLIENT_DATA_REQUEST_SUBMITTED":
            await handle_client_data(int(payload["CLIENT_ID"]))
    except Exception:
        logger.exception("podpislon: обработка %s провалилась: %s", event, payload)


@router.post("/podpislon")
async def podpislon_webhook(request: Request) -> JSONResponse:
    form = await request.form()
    payload = {k: str(v) for k, v in form.items()}
    event = payload.get("EVENT", "")

    if not podpislon.configured():
        logger.warning("podpislon: вебхук %s пришёл, но PODPISLON_API_KEY не задан",
                       event)
        return JSONResponse({"ok": True, "skipped": "not configured"})

    if event not in _HANDLED_EVENTS:
        # DOCUMENT_OPENED и будущие события подтверждаем, но не обрабатываем:
        # иначе Подпислон будет считать обработчик нерабочим и слать повторы.
        return JSONResponse({"ok": True, "ignored": event})

    key = f"{event}:{payload.get('FILE_ID') or payload.get('CLIENT_ID')}"
    if _dedup(key):
        return JSONResponse({"ok": True, "duplicate": key})

    asyncio.create_task(_process(event, payload))
    return JSONResponse({"ok": True, "accepted": event})
