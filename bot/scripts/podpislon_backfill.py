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
from app.platform.podpislon_webhooks import upload_contract  # noqa: E402

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


# Договоры сезона 26_27. Названия в Подпислоне свободные («26-27 уч год»,
# «Лобунцова Настя»), поэтому сезон определяем по дате создания документа:
# переносим всё, что создано с апреля 2026.
SEASON_STARTS = "2026-04-01"


async def fetch_documents_page(page: int) -> list:
    """Страница списка документов (по 20, новые сверху). 429 пережидаем."""
    for attempt in range(6):
        try:
            docs = await podpislon._request("POST", f"/?page={page}", json_body={})
            return docs if isinstance(docs, list) else []
        except podpislon.PodpislonError as exc:
            if "429" not in str(exc):
                raise
            await asyncio.sleep(1 + attempt)
    raise podpislon.PodpislonError("429: лимит не отпустил за 6 попыток")


async def signed_documents(fetch=fetch_documents_page, *,
                           pause: float = PAUSE) -> dict[int, dict]:
    """{contact_id: документ} по подписанным договорам сезона, новейший на контакт.

    Страницы кончаются не пустым ответом: API бесконечно повторяет последнюю.
    Поэтому останавливаемся, как только страница не принесла новых документов.
    """
    out: dict[int, dict] = {}
    seen: set[int] = set()
    page = 1
    while True:
        docs = await fetch(page)
        fresh = [d for d in docs if int(d.get("id") or 0) not in seen]
        if not fresh:
            break
        for doc in fresh:
            seen.add(int(doc.get("id") or 0))
            if (not podpislon.is_signed(doc)
                    or str(doc.get("date_create") or "") < SEASON_STARTS):
                continue
            contact_id = podpislon.contact_id_of(doc)
            if contact_id and contact_id not in out:
                out[contact_id] = doc
        page += 1
        await asyncio.sleep(pause)
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
    failed: list[str] = []

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
                try:
                    await crm.update_student(student["id"], updates)
                except crm.BigBenInternalError as exc:
                    failed.append(f"  {child}: карточка не сохранилась — {exc}")
        if conflicts:
            conflicted.append(f"  {child}: " + "; ".join(
                f"{k}: в CRM {old!r}, в анкете {new!r}"
                for k, (old, new) in conflicts.items()))

        doc = docs.get(contact.get("id"))
        if doc and not args.contacts_only:
            try:
                result = await upload_contract(student, doc, child, apply=args.apply)
            except (crm.BigBenInternalError, podpislon.PodpislonError) as exc:
                failed.append(f"  {child}: договор не загрузился — {exc}")
                continue
            await asyncio.sleep(PAUSE)
            if result["uploaded"]:
                uploaded += 1
                print(f"  {child}: загрузить {result['filename']}")

    print(f"\nИтого: дозаполнить карточек {filled}, загрузить договоров {uploaded}")
    if failed:
        print(f"\nОшибки — карточка пропущена, остальные обработаны ({len(failed)}):")
        print("\n".join(failed))
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
