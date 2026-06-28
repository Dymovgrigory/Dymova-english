#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Задать заголовок/описание/alias для копий-страниц через форму настроек Tilda."""
import asyncio
from playwright.async_api import async_playwright

PROJECTID = "2053071"
CDP = "http://localhost:29229"

# pageid -> (title, descr, alias)
PAGES = {
    "151292376": ("Курс по чтению — Фоксинбург",
                  "Летний курс по чтению на английском для младших школьников — школа Фоксинбург",
                  "reading-new"),
    "151292406": ("Курс по грамматике — Фоксинбург",
                  "Летний курс грамматики английского для 3–8 классов — школа Фоксинбург",
                  "grammar-new"),
    "151292476": ("Подготовка к школе — Фоксинбург",
                  "Подготовка к школе, занятия со школьниками и подготовка к ОГЭ/ЕГЭ/ВПР — Фоксинбург",
                  "preparation-new"),
}


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        page = browser.contexts[0].pages[0]
        page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await page.goto("https://tilda.ru/projects/?projectid=%s" % PROJECTID,
                        wait_until="load", timeout=90000)
        await asyncio.sleep(3)
        for pageid, (title, descr, alias) in PAGES.items():
            print("\n==== %s -> %s ====" % (pageid, alias))
            await page.evaluate("(id)=>td__showform__EditPageSettings(id)", pageid)
            await asyncio.sleep(2)
            await page.fill("form[name=formpageedit] input[name=title]", title)
            await page.fill("form[name=formpageedit] input[name=descr]", descr)
            await page.fill("form[name=formpageedit] input[name=alias]", alias)
            await asyncio.sleep(0.4)
            vals = await page.evaluate("""()=>{
                var f=document.forms['formpageedit'];
                return f? [f.title.value, f.descr.value, f.alias.value] : null;
            }""")
            print("  filled:", vals)
            await page.click("form[name=formpageedit] input[type=submit]")
            await asyncio.sleep(2.5)
        print("\nГотово.")


if __name__ == "__main__":
    asyncio.run(main())
