#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обмен адресами (alias) страниц Tilda проекта 2053071 + смена главной страницы.

Оригиналы переименовываются в <alias>-old, новые страницы занимают боевые
адреса. Главная страница проекта переключается на index-new (indexpageid).
ПУБЛИКАЦИЯ И СНЯТИЕ С ПУБЛИКАЦИИ — отдельными шагами, не здесь.

Изменения alias идут через форму настроек (td__showform__EditPageSettings +
сабмит), т.е. копятся в черновике до «Опубликовать все».

По умолчанию DRY-RUN (только читает текущие alias). С флагом --apply меняет.

Порядок важен: сперва оригиналы -> -old (освобождаем боевые адреса),
затем новые -> боевые адреса.
"""
import asyncio, sys
from playwright.async_api import async_playwright

PROJECTID = "2053071"
CDP = "http://localhost:29229"

# Шаг 1: оригиналы -> -old
ORIGINALS = [
    ("137726126", "reading-old"),
    ("137739566", "grammar-old"),
    ("130390566", "preparation-old"),
    ("146080046", "vacant-old"),
    ("32889798",  "index-old"),
]
# Шаг 2: новые -> боевые адреса (vakansii и index-new не переименовываем)
NEWPAGES = [
    ("151292376", "reading"),
    ("151292406", "grammar"),
    ("151292476", "preparation"),
]
# Шаг 3: главная страница проекта
INDEX_PAGEID = "151210576"  # index-new


async def get_alias(page, pageid):
    await page.evaluate("(id)=>td__showform__EditPageSettings(id)", pageid)
    await asyncio.sleep(1.8)
    return await page.evaluate(
        "()=>{var f=document.forms['formpageedit'];return f?f.alias.value:null;}")


async def set_alias(page, pageid, alias, apply):
    cur = await get_alias(page, pageid)
    if not apply:
        print("  %s: alias='%s' -> '%s' (dry-run)" % (pageid, cur, alias))
        return
    await page.fill("form[name=formpageedit] input[name=alias]", alias)
    await asyncio.sleep(0.3)
    await page.click("form[name=formpageedit] input[type=submit]")
    await asyncio.sleep(2.2)
    # verify
    now = await get_alias(page, pageid)
    ok = "OK" if now == alias else "MISMATCH (got '%s')" % now
    print("  %s: '%s' -> '%s'  %s" % (pageid, cur, alias, ok))
    # close form
    await page.keyboard.press("Escape")
    await asyncio.sleep(0.5)


async def set_homepage(page, pageid, apply):
    await page.goto("https://tilda.ru/projects/settings/?projectid=%s#tab=ss_menu_index" % PROJECTID,
                    wait_until="load", timeout=90000)
    await asyncio.sleep(3)
    cur = await page.evaluate(
        "()=>{var s=document.querySelector('select[name=indexpageid]');return s?s.value:null;}")
    if not apply:
        print("  homepage indexpageid='%s' -> '%s' (dry-run)" % (cur, pageid))
        return
    await page.select_option("select[name=indexpageid]", pageid)
    await asyncio.sleep(0.5)
    # save project settings
    await page.click("button[type=submit]")
    await asyncio.sleep(3)
    await page.goto("https://tilda.ru/projects/settings/?projectid=%s#tab=ss_menu_index" % PROJECTID,
                    wait_until="load", timeout=90000)
    await asyncio.sleep(2.5)
    now = await page.evaluate(
        "()=>{var s=document.querySelector('select[name=indexpageid]');return s?s.value:null;}")
    ok = "OK" if now == pageid else "MISMATCH (got '%s')" % now
    print("  homepage indexpageid: '%s' -> '%s'  %s" % (cur, pageid, ok))


async def main():
    apply = "--apply" in sys.argv
    print("Mode:", "APPLY" if apply else "DRY-RUN")
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        page = browser.contexts[0].pages[0]
        page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await page.goto("https://tilda.ru/projects/?projectid=%s" % PROJECTID,
                        wait_until="load", timeout=90000)
        await asyncio.sleep(3)

        print("\n--- Шаг 1: оригиналы -> -old ---")
        for pid, alias in ORIGINALS:
            await set_alias(page, pid, alias, apply)

        print("\n--- Шаг 2: новые -> боевые адреса ---")
        for pid, alias in NEWPAGES:
            await set_alias(page, pid, alias, apply)

        print("\n--- Шаг 3: главная страница -> index-new ---")
        await set_homepage(page, INDEX_PAGEID, apply)

        print("\nГотово (%s)." % ("apply" if apply else "dry-run"))


if __name__ == "__main__":
    asyncio.run(main())
