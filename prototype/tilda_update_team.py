#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обновляет живой T123-блок команды (id="fxb-team") на страницах Tilda,
заменяя его код на актуальное содержимое prototype/tilda_team.html.

Чтение кода блока из редактора:
  .record[recordid][data-record-cod="T123"] pre code.textContent
Сохранение: POST /page/submit/ comm=saverecord onlythisfield=code.

Запуск:
  python3 tilda_update_team.py            # сухой прогон (найти блок)
  python3 tilda_update_team.py --apply     # сохранить новый код
"""
import argparse
import asyncio
import json
import os

from playwright.async_api import async_playwright

PROJECTID = "2053071"
CDP = "http://localhost:29229"
MARKER = 'id="fxb-team"'

HERE = os.path.dirname(os.path.abspath(__file__))
TEAM_FILE = os.path.join(HERE, "tilda_team.html")

PAGES = [
    ("151210576", "index (главная)"),
    ("151292376", "reading"),
    ("151292406", "grammar"),
    ("151292476", "preparation"),
    ("151228606", "doshkolniki"),
    ("151228676", "mladshie-shkolniki"),
    ("151228746", "podrostki"),
    ("151229566", "letnyaya-akademiya"),
    ("151229606", "online-zanyatiya"),
    ("151229676", "podderzhivayushchie-online"),
    ("151229756", "standartnye-offline"),
    ("151228006", "kontakty"),
    ("151324806", "novosti"),
    ("151324866", "vakansii"),
]


async def page_submit(page, fields):
    return await page.evaluate(
        """(fields) => new Promise((resolve) => {
            var fd = new FormData();
            for (var k in fields) fd.append(k, fields[k]);
            fetch('/page/submit/', {method:'POST', body:fd, credentials:'same-origin'})
              .then(r => r.text()).then(t => resolve(t)).catch(e => resolve('ERR:'+e.message));
        })""",
        fields,
    )


async def get_t123_blocks(page):
    return await page.evaluate(
        """() => Array.from(document.querySelectorAll('.record[recordid][data-record-cod="T123"]'))
              .map((el) => {
                  const codeEl = el.querySelector('pre code');
                  return { recordid: el.getAttribute('recordid'),
                           code: codeEl ? codeEl.textContent : '' };
              })"""
    )


async def save_block(page, recordid, code):
    pageid = await page.evaluate("String(window.pageid)")
    txt = await page_submit(page, {
        "comm": "saverecord", "pageid": pageid, "recordid": recordid,
        "onlythisfield": "code", "code": code,
    })
    return txt.strip()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    with open(TEAM_FILE, encoding="utf-8") as f:
        new_code = f.read()
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}; new team code len={len(new_code)}")

    found = []
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()

        for pageid, alias in PAGES:
            url = f"https://tilda.ru/page/?pageid={pageid}&projectid={PROJECTID}&edit=y"
            await page.goto(url, wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_function(
                f"String(window.pageid) === {json.dumps(str(pageid))}", timeout=90000)
            await page.wait_for_timeout(4000)
            blocks = await get_t123_blocks(page)
            for b in blocks:
                if MARKER in (b["code"] or ""):
                    rec = str(b["recordid"])
                    print(f"  FOUND fxb-team on {alias} (pageid {pageid}) rec{rec} "
                          f"(old len={len(b['code'])})")
                    found.append((pageid, alias, rec))
                    if args.apply:
                        res = await save_block(page, rec, new_code)
                        print(f"    save result: {res[:120]}")

    print(f"\nTotal blocks found: {len(found)}")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
