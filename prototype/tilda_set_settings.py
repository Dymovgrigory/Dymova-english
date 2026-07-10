#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Задать заголовок/описание/alias для страниц через форму настроек Tilda.

После смены дизайна: новые страницы занимают канонические URL /reading / /grammar / /preparation,
а старые оригиналы переезжают на /reading-old / /grammar-old / /preparation-old.
"""
import asyncio
from playwright.async_api import async_playwright

PROJECTID = "2053071"
CDP = "http://localhost:29229"

# pageid -> (title, descr, alias)
PAGES = {
    # Новые страницы — канонические URL
    "151292376": ("Курс по чтению — Фоксинбург",
                  "Летний курс по чтению на английском для младших школьников — школа Фоксинбург",
                  "reading"),
    "151292406": ("Курс по грамматике — Фоксинбург",
                  "Летний курс грамматики английского для 3–8 классов — школа Фоксинбург",
                  "grammar"),
    "151292476": ("Подготовка к школе — Фоксинбург",
                  "Подготовка к школе, занятия со школьниками и подготовка к ОГЭ/ЕГЭ/ВПР — Фоксинбург",
                  "preparation"),
    # Старые оригиналы — временно доступны по -old
    "137726126": ("Курс по чтению (архив) — Фоксинбург",
                  "Архивная версия страницы чтения — школа Фоксинбург",
                  "reading-old"),
    "137739566": ("Курс по грамматике (архив) — Фоксинбург",
                  "Архивная версия страницы грамматики — школа Фоксинбург",
                  "grammar-old"),
    "130390566": ("Подготовка к школе (архив) — Фоксинбург",
                  "Архивная версия страницы подготовки к школе — школа Фоксинбург",
                  "preparation-old"),
    "152445956": ("Подготовка к ОГЭ по английскому в Долгопрудном — Фоксинбург",
                  "Подготовка к ОГЭ по английскому в Долгопрудном: все разделы экзамена, устная часть и разбор критериев. Пробные экзамены, мини-группы по уровню. Бесплатная диагностика.",
                  "oge-anglijskij"),
    "152446216": ("Подготовка к ЕГЭ по английскому в Долгопрудном — Фоксинбург",
                  "Подготовка к ЕГЭ по английскому в Долгопрудном: все разделы экзамена, эссе по критериям, устная часть. Пробные ЕГЭ и мини-группы по уровню. Бесплатная диагностика.",
                  "ege-anglijskij"),
    "152446236": ("Английский для взрослых в Долгопрудном, с нуля — Фоксинбург",
                  "Английский для взрослых в Долгопрудном: с нуля и для продолжающих. Разговорная практика, утренние и вечерние группы, онлайн-формат. Запишитесь на диагностику.",
                  "anglijskij-dlya-vzroslyh"),
    "152446286": ("Курсы немецкого языка в Долгопрудном — Фоксинбург",
                  "Немецкий язык в Долгопрудном для детей, школьников и взрослых: мини-группы, живое общение, обучение с нуля. Оффлайн и онлайн. Запишитесь на пробный урок.",
                  "nemeckij-yazyk"),
    "152446296": ("Курсы китайского языка в Долгопрудном — Фоксинбург",
                  "Китайский язык в Долгопрудном для детей, школьников и взрослых: иероглифика, тоны и разговорная практика в мини-группах. Обучение с нуля. Пробный урок.",
                  "kitajskij-yazyk"),
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
