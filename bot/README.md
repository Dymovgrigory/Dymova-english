# Фоксинбург — AI-консультант для MAX

AI-консультант и менеджер по продажам языковой школы «Фоксинбург» для мессенджера
**MAX**. Бот ведёт естественный диалог, подбирает курс, отрабатывает возражения,
записывает на бесплатную диагностику и отправляет заявку в **BigBen CRM**, а при
необходимости передаёт диалог администратору. В комплекте — мини-приложение
(витрина курсов / помощник по выбору / личный кабинет).

## Архитектура

```
MAX → /webhook → AI Core (decision loop)
                   ├─ Intent Recognition (intent.py)
                   ├─ Memory (memory.py)            — этап продажи, данные лида, история
                   ├─ Knowledge Search (knowledge/) — RAG-lite по data.yaml
                   ├─ Sales Engine (sales.py)       — системный промт + возражения
                   ├─ Course Selector (course_selector.py)
                   ├─ Lead Manager (lead_manager.py)→ BigBen CRM (bigben.py)
                   └─ Administrator Router (admin_router.py)
LLM (llm.py) — провайдер-агностик, OpenAI-совместимый (по умолчанию OpenRouter, free).
Mini App (miniapp/) — статика + /api/miniapp/*.
```

Бот работает и **без LLM-ключа** (отвечает по базе знаний и сценариям), и без
MAX/CRM-ключей (для локальной разработки и тестов).

## Запуск локально

```bash
cd bot
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить ключи (можно оставить пустыми для тестов)
uvicorn app.main:app --reload --port 8000
```

- Health: `GET http://localhost:8000/health`
- Мини-приложение: `http://localhost:8000/app/`
- Тесты: `pytest -q`

## Прод-деплой 24/7

Для стабильного запуска используйте Docker Compose:

```bash
cd bot
cp .env.example .env   # заполните ключи
mkdir -p data
docker compose up -d --build
```

- приложение поднимается без `--reload`;
- SQLite хранится в `./data/bot.db` и переживает перезапуски;
- healthcheck дергает `GET /health`;
- webhook регистрируется после старта:
  ```bash
  curl -X POST https://ВАШ_ХОСТ/admin/set-webhook \
    -H 'Content-Type: application/json' \
    -d '{"url":"https://ВАШ_ХОСТ/webhook"}'
  ```

## Подключение к MAX

1. Получите токен бота: платформа MAX → Чат-боты → Расширенные настройки.
2. Разверните сервис на публичном HTTPS-адресе.
3. Зарегистрируйте webhook:
   ```bash
   curl -X POST https://ВАШ_ХОСТ/admin/set-webhook \
     -H 'Content-Type: application/json' \
     -d '{"url":"https://ВАШ_ХОСТ/webhook"}'
   ```

## Переменные окружения

См. `.env.example`. Ключевые: `MAX_BOT_TOKEN`, `LLM_API_KEY`, `BIGBEN_API_URL`,
`BIGBEN_API_KEY`, `BIGBEN_PIPELINE_ID`, `BIGBEN_PIPELINE_STATUS_ID`,
`ADMIN_MAX_IDS`, `MINIAPP_BASE_URL`.

## База знаний

Все факты о школе (филиалы, курсы, цены, преподаватели, FAQ, акции, соцсети)
хранятся в `app/knowledge/data.yaml`. Бот отвечает только на основе этих данных и
не выдумывает цены/факты. Чтобы обновить информацию — отредактируйте YAML.
