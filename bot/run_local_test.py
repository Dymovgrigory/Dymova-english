"""Локальный запуск для тестирования: приложение + статика виджета + тестовая страница."""
from pathlib import Path

import uvicorn
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.main import app

app.mount("/widget", StaticFiles(directory=str(Path(__file__).parent / "app" / "widget")), name="widget")


@app.get("/test-page")
async def test_page() -> HTMLResponse:
    return HTMLResponse(
        """<!doctype html><html lang=ru><head><meta charset=utf-8>
        <title>Foxinburg — тест виджета</title></head>
        <body style="font-family:sans-serif;background:#f4f0ff">
        <h1 style="padding:24px">Тестовая страница сайта Фоксинбург</h1>
        <script src="/widget/foxi.js"></script></body></html>"""
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
