"""Разовый перенос: обход списка документов Подпислона."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import podpislon_backfill as backfill  # noqa: E402


def doc(doc_id, contact, status="30", name="Договор.pdf", created="2026-09-10 12:00:00"):
    return {"id": doc_id, "status": status, "name": name, "date_create": created,
            "contacts": [{"link": f"https://podpislon.ru/sign/pack/{contact}/x"}]}


class FakePages:
    """Как живой API: после последней страницы бесконечно отдаёт её же."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = 0

    async def __call__(self, page):
        self.calls += 1
        return self.pages[min(page, len(self.pages)) - 1]


@pytest.mark.asyncio
async def test_stops_when_api_repeats_the_last_page():
    fetch = FakePages([[doc(3, 30), doc(2, 20)], [doc(1, 10)]])
    out = await backfill.signed_documents(fetch, pause=0)
    assert out == {30: 3, 20: 2, 10: 1}
    assert fetch.calls == 3


@pytest.mark.asyncio
async def test_takes_only_signed_contracts_of_this_season():
    # Названия свободные («26-27 уч год», «Лобунцова Настя») — сезон по дате.
    fetch = FakePages([[
        doc(5, 50, status="20"),
        doc(4, 40, name="Сазыкин 26_27.pdf", created="2025-07-21 20:15:17"),
        doc(3, 30, name="Лобунцова Настя.pdf"),
    ]])
    assert await backfill.signed_documents(fetch, pause=0) == {30: 3}


@pytest.mark.asyncio
async def test_newest_contract_wins_per_contact():
    fetch = FakePages([[doc(9, 10), doc(8, 10)]])
    assert await backfill.signed_documents(fetch, pause=0) == {10: 9}


@pytest.mark.asyncio
async def test_empty_account():
    assert await backfill.signed_documents(FakePages([[]]), pause=0) == {}
