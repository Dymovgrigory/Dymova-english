"""
Reorder the T123 blocks on /index-new (pageid 151210576) into the owner's fixed
standard order, and (optionally) create the new "Отзывы" block.

Tilda reorder API (discovered from the editor's own drag handler):
    POST /page/submit/
        comm=saverecordssort
        pageid=<pageid>
        sorts[0]=<recordid>&sorts[1]=<recordid>&...   # NOTE: array param, NOT a CSV "sort="

Run while an authenticated Tilda session is open in the CDP browser
(http://localhost:29229). After running, reload the page editor so it picks up the
new server-side order, then publish (editor "Опубликовать" or projects "Опубликовать все").

The fixed visible order (do not change without an explicit owner request):
  1 Шапка            2421794631   8  Фотобанк         2422576671
  2 Запись CTA       2422572641   9  Тарифы (3 карт.) 2422572531
  3 Преимущества     2422572521   10 Отзывы           2422719781
  4 Направления      2422570311   11 FAQ              2422572561
  5 Как начинается   2422576651   12 Сведения         2422572571
  6 Команда          2422572491   13 Контакты         2422572611
  7 Другие языки     2422572511   14 Подвал           2422572651
"""
import asyncio
from playwright.async_api import async_playwright

PAGEID = "151210576"
PROJECTID = "2053071"

DESIRED = [
    "2421794631", "2422572641", "2422572521", "2422570311", "2422576651",
    "2422572491", "2422572511", "2422576671", "2422572531", "2422719781",
    "2422572561", "2422572571", "2422572611", "2422572651",
]


async def submit(page, fields):
    return await page.evaluate(
        """(fields) => new Promise((resolve) => {
            var fd = new FormData();
            for (var k in fields) fd.append(k, fields[k]);
            fetch('/page/submit/', {method:'POST', body:fd, credentials:'same-origin'})
              .then(r => r.text()).then(t => resolve(t)).catch(e => resolve('ERR:'+e.message));
        })""", fields)


async def get_record_order(page):
    """Read the full current record order from the open page editor DOM."""
    return await page.evaluate(
        r"""() => Array.prototype.slice.call(document.querySelectorAll('[id^="rec"]'))
              .map(e => (e.id.match(/^rec(\d+)$/) || [])[1]).filter(Boolean)"""
    )


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:29229")
        page = browser.contexts[0].pages[0]
        if f"pageid={PAGEID}" not in page.url or "edit=y" not in page.url:
            await page.goto(
                f"https://tilda.ru/page/?pageid={PAGEID}&projectid={PROJECTID}&edit=y",
                wait_until="load")
            await asyncio.sleep(6)

        current = await get_record_order(page)
        desired_set = set(DESIRED)
        others = [r for r in current if r not in desired_set]
        final = DESIRED + others
        assert len(final) == len(set(final)), "duplicate record id in sort"
        print(f"Reorder: {len(DESIRED)} fixed T123 + {len(others)} native = {len(final)}")

        fields = {"comm": "saverecordssort", "pageid": PAGEID}
        for i, rid in enumerate(final):
            fields[f"sorts[{i}]"] = rid
        print("saverecordssort ->", (await submit(page, fields))[:120])
        print("Done. Reload the editor and publish to apply the new order.")


if __name__ == "__main__":
    asyncio.run(main())
