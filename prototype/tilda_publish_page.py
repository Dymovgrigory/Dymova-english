#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Публикация одной страницы Tilda через /page/publish/.
Запуск: python3 tilda_publish_page.py <pageid> [<pageid> ...]"""
import asyncio
import json
import sys

from playwright.async_api import async_playwright

PROJECTID = "2053071"
CDP = "http://localhost:29229"


async def main():
    pageids = sys.argv[1:] or ["151210576"]
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()
        # быть на домене tilda.ru для same-origin запроса
        if "tilda.ru" not in (page.url or ""):
            await page.goto(f"https://tilda.ru/page/?pageid={pageids[0]}&projectid={PROJECTID}&edit=y",
                            wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_timeout(3000)
        for pid in pageids:
            res = await page.evaluate(
                """(args) => new Promise((resolve) => {
                    var fd = new FormData();
                    fd.append('pageid', args.pid);
                    fd.append('projectid', args.proj);
                    fetch('/page/publish/', {method:'POST', body:fd, credentials:'same-origin'})
                      .then(r => r.text()).then(t => resolve(t)).catch(e => resolve('ERR:'+e.message));
                })""",
                {"pid": pid, "proj": PROJECTID},
            )
            print(f"{pid} -> {res.strip()[:300]}")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
