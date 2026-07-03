#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Точечно переписывает внутренние href внутри живых T123-блоков Tilda.

Рабочий способ чтения кода блока, найденный в редакторе:
  .record[recordid][data-record-cod="T123"] pre code.textContent

Именно этот DOM-источник даёт текущий HTML блока вместе с recordid, после чего
скрипт делает точечную замену и при --apply сохраняет код через /page/submit/
с comm=saverecord и onlythisfield=code.
"""
import argparse
import asyncio
import json
from dataclasses import dataclass

from playwright.async_api import async_playwright

PROJECTID = "2053071"
CDP = "http://localhost:29229"

PAGES = [
    ("151210576", "index-new"),
    ("151292376", "reading-new"),
    ("151292406", "grammar-new"),
    ("151292476", "preparation-new"),
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

REPLACEMENTS = [
    ('href="/reading-new"', 'href="/reading"'),
    ("href='/reading-new'", "href='/reading'"),
    ('href="/grammar-new"', 'href="/grammar"'),
    ("href='/grammar-new'", "href='/grammar'"),
    ('href="/preparation-new"', 'href="/preparation"'),
    ("href='/preparation-new'", "href='/preparation'"),
    ('href="/index-new"', 'href="/"'),
    ("href='/index-new'", "href='/'"),
    ('href="/vacant"', 'href="/vakansii"'),
    ("href='/vacant'", "href='/vakansii'"),
]

@dataclass
class BlockChange:
    recordid: str
    counts: dict[str, int]
    before_len: int
    after_len: int


def relink_code(code: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    updated = code
    for old, new in REPLACEMENTS:
        count = updated.count(old)
        counts[old] = count
        if count:
            updated = updated.replace(old, new)
    return updated, counts


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
                  return {
                      recordid: el.getAttribute('recordid'),
                      off: el.getAttribute('off') || '',
                      code: codeEl ? codeEl.textContent : '',
                  };
              })"""
    )


async def save_block(page, recordid: str, code: str) -> str:
    pageid = await page.evaluate("String(window.pageid)")
    txt = await page_submit(
        page,
        {
            "comm": "saverecord",
            "pageid": pageid,
            "recordid": recordid,
            "onlythisfield": "code",
            "code": code,
        },
    )
    return txt.strip()


async def process_page(page, pageid: str, alias: str, apply: bool) -> list[BlockChange]:
    url = f"https://tilda.ru/page/?pageid={pageid}&projectid={PROJECTID}&edit=y"
    print(f"\n==================== {alias} (pageid {pageid}) ====================")
    await page.goto(url, wait_until="domcontentloaded", timeout=90000)
    await page.wait_for_function(
        f"String(window.pageid) === {json.dumps(str(pageid))}", timeout=90000
    )
    await page.wait_for_timeout(4000)

    blocks = await get_t123_blocks(page)
    print(f"  T123 blocks found: {len(blocks)}")

    changed: list[BlockChange] = []
    for block in blocks:
        recordid = str(block["recordid"] or "")
        code = block["code"] or ""
        new_code, counts = relink_code(code)
        total = sum(counts.values())
        if total:
            changed.append(
                BlockChange(
                    recordid=recordid,
                    counts={k: v for k, v in counts.items() if v},
                    before_len=len(code),
                    after_len=len(new_code),
                )
            )
            details = ", ".join(f"{k} x{v}" for k, v in counts.items() if v)
            action = "would save" if not apply else "saving"
            print(f"  rec{recordid}: {details} -> {action}")
            if apply:
                res = await save_block(page, recordid, new_code)
                print(f"    save result: {res[:120]}")
        elif block.get("off") == "y":
            # off/minified blocks still count as T123, but here their code is not expanded in DOM
            print(f"  rec{recordid}: off=y, no readable code in DOM")

    if not changed:
        print("  no changes")
    return changed


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually save changed blocks")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"Mode: {mode}")
    print("Targets:", json.dumps(PAGES, ensure_ascii=False))

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()

        for pageid, alias in PAGES:
            await process_page(page, pageid, alias, args.apply)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
