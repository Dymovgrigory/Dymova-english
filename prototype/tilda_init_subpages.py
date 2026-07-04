#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Инициализация пустых Tilda-страниц: создать 3 блока T123 и залить шапку,
контент и подвал.

Использует те же хелперы, что и tilda_upload_subpages.py, но работает без
опубликованного HTML: ориентируется на текущие блоки в редакторе Tilda.
"""
import asyncio

from playwright.async_api import async_playwright

from tilda_upload_subpages import (
    CDP,
    PROJECTID,
    add_t123,
    read,
    save_code,
    sort_records,
)

PAGES = [
    ("152445956", "page_oge_anglijskij.html"),
    ("152446216", "page_ege_anglijskij.html"),
    ("152446236", "page_anglijskij_dlya_vzroslyh.html"),
    ("152446286", "page_nemeckij_yazyk.html"),
    ("152446296", "page_kitajskij_yazyk.html"),
]


async def editor_recids(page):
    return await page.evaluate("""() => {
        const ids = Array.from(document.querySelectorAll('.t-rec[id^="rec"]'))
          .map(el => el.id.replace(/^rec/, ''))
          .filter(Boolean);
        return [...new Set(ids)];
    }""")


async def ensure_three_records(page):
    recids = await editor_recids(page)
    if len(recids) >= 3:
        return recids[:3], recids

    while len(recids) < 3:
        afterid = recids[-1] if recids else ""
        rid = await add_t123(page, afterid)
        if not rid:
            raise RuntimeError("Не удалось создать T123-блок")
        recids.append(rid)
        await asyncio.sleep(1)

    return recids[:3], recids


async def process_page(page, pageid, content_file, shapka, footer):
    print(f"\n==== pageid {pageid} -> {content_file} ====")
    await page.goto(
        f"https://tilda.ru/page/?pageid={pageid}&projectid={PROJECTID}&edit=y",
        wait_until="load",
        timeout=90000,
    )
    await asyncio.sleep(3)
    wp = await page.evaluate("window.pageid")
    if str(wp) != str(pageid):
        raise RuntimeError(f"window.pageid ({wp}) != ожидаемого ({pageid})")

    target_ids, all_ids = await ensure_three_records(page)
    print("  existing records:", len(all_ids), "target:", target_ids)

    content = read(content_file)
    codes = [shapka, content, footer]
    for rid, code, name in zip(target_ids, codes, ("shapka", "content", "footer")):
        result = await save_code(page, rid, code)
        print(f"  save {name:<7} rec{rid} ({len(code)} chars) -> {result[:60]}")
        await asyncio.sleep(0.6)

    rest = [rid for rid in all_ids if rid not in target_ids]
    order = target_ids + rest
    result = await sort_records(page, order)
    print("  sort ->", result[:80])
    return {"pageid": pageid, "records": target_ids}


async def main():
    shapka = read("tilda_shapka.html")
    footer = read("tilda_footer.html")
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        page = browser.contexts[0].pages[0]
        page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        results = []
        for pageid, content_file in PAGES:
            results.append(await process_page(page, pageid, content_file, shapka, footer))
        print("\n===== ИТОГ =====")
        for row in results:
            print(row)


if __name__ == "__main__":
    asyncio.run(main())
