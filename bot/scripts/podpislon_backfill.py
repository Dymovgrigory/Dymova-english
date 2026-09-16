#!/usr/bin/env python3
"""Разовый перенос анкет и подписанных договоров из Подпислона в карточки CRM.

По умолчанию НИЧЕГО не пишет — печатает отчёт. Запись включается флагом
`--apply`.

    python scripts/podpislon_backfill.py                  # отчёт
    python scripts/podpislon_backfill.py --contacts-only  # без договоров
    python scripts/podpislon_backfill.py --apply          # записать

Матч карточки — как в вебхуке: должны совпасть и ФИО ребёнка, и телефон.
Что не сматчилось или сматчилось неоднозначно, попадает в конец отчёта
списком для ручного разбора.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.platform import bigben_internal as crm  # noqa: E402
from app.platform import podpislon, podpislon_sync  # noqa: E402
from app.platform.podpislon_webhooks import contract_filename  # noqa: E402

# Подпислон ограничивает 4 запросами в секунду на ключ.
PAUSE = 0.3


async def fetch_contacts(limit: int | None) -> list[dict]:
    """Все контакты компании с паспортом и кастомными полями."""
    out: list[dict] = []
    offset = 0
    while True:
        page = await podpislon._request(
            "GET", f"/v2/contacts?limit=100&offset={offset}"
                   "&expand=passport,custom_fields")
        items = page.get("items") if isinstance(page, dict) else page
        if not items:
            break
        out.extend(items)
        if limit and len(out) >= limit:
            return out[:limit]
        offset += len(items)
        if isinstance(page, dict) and offset >= (page.get("total") or 0):
            break
        await asyncio.sleep(PAUSE)
    return out


async def signed_documents() -> dict[int, int]:
    """{contact_id: file_id} по подписанным договорам, новейший на контакт."""
    out: dict[int, int] = {}
    page = 1
    while True:
        docs = await podpislon._request("POST", f"/?page={page}", json_body={})
        if not isinstance(docs, list) or not docs:
            break
        for doc in docs:
            if not podpislon.is_signed(doc):
                continue
            contact_id = podpislon.contact_id_of(doc)
            if contact_id and contact_id not in out:
                out[contact_id] = int(doc["id"])
        page += 1
        await asyncio.sleep(PAUSE)
    return out


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="записать изменения (по умолчанию только отчёт)")
    parser.add_argument("--contacts-only", action="store_true",
                        help="только дозаполнение полей, без загрузки договоров")
    parser.add_argument("--limit", type=int, default=0,
                        help="обработать не больше N контактов")
    args = parser.parse_args()

    if not podpislon.configured():
        print("PODPISLON_API_KEY не задан")
        return 1
    if not crm.configured():
        print("BIGBEN_INTERNAL_TOKEN не задан")
        return 1

    mode = "ЗАПИСЬ" if args.apply else "просмотр (ничего не меняется)"
    print(f"Режим: {mode}\n")

    contacts = await fetch_contacts(args.limit or None)
    print(f"Контактов в Подпислоне: {len(contacts)}")

    docs = {} if args.contacts_only else await signed_documents()
    if not args.contacts_only:
        print(f"Подписанных договоров: {len(docs)}")
    print()

    filled = uploaded = 0
    unmatched: list[str] = []
    conflicted: list[str] = []

    for contact in contacts:
        fields = podpislon.to_crm_fields(contact)
        child, phone = fields["fio"], fields["parent_phone"]
        candidates = await crm.find_students_by_phone(phone)
        student = podpislon_sync.match_student(
            {"child_fio": child, "phone": phone,
             "parent_last_name": fields["parent_last_name"]}, candidates)
        await asyncio.sleep(PAUSE)

        if not student:
            why = "нет карточки" if not candidates else "неоднозначно"
            unmatched.append(f"  {child or '(без ФИО)'} / {phone or '(без тел.)'} — {why}")
            continue

        child = child or str(student.get("fio") or "")
        updates, conflicts = podpislon_sync.missing_fields(student, fields)
        if updates:
            filled += 1
            print(f"  {child}: дозаполнить {', '.join(updates)}")
            if args.apply:
                await crm.update_student(student["id"], updates)
        if conflicts:
            conflicted.append(f"  {child}: " + "; ".join(
                f"{k}: в CRM {old!r}, в анкете {new!r}"
                for k, (old, new) in conflicts.items()))

        file_id = docs.get(contact.get("id"))
        if file_id and not args.contacts_only:
            filename = contract_filename(child or student.get("fio"))
            existing = {str(f.get("name") or "")
                        for f in await crm.list_student_files(student["id"])}
            if filename not in existing:
                uploaded += 1
                print(f"  {child}: загрузить {filename}")
                if args.apply:
                    pdf = await podpislon.download_pdf(file_id)
                    await crm.upload_student_file(student["id"], filename, pdf)
                    await asyncio.sleep(PAUSE)

    print(f"\nИтого: дозаполнить карточек {filled}, загрузить договоров {uploaded}")
    if conflicted:
        print(f"\nРасхождения — не трогали, проверьте руками ({len(conflicted)}):")
        print("\n".join(conflicted))
    if unmatched:
        print(f"\nНе сопоставлено ({len(unmatched)}):")
        print("\n".join(unmatched))
    if not args.apply:
        print("\nЭто был просмотр. Записать: добавьте --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
