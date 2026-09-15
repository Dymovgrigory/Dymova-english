# Foxinburg World — API

Отдельная игровая платформа. Не школьный бот и не CRM.

## Запуск

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8010
```

Health: [http://127.0.0.1:8010/health](http://127.0.0.1:8010/health)

Фронт всегда на [http://127.0.0.1:3002](http://127.0.0.1:3002). Из корня репо: `make world-dev`.

`NEXT_PUBLIC_WORLD_API=http://127.0.0.1:8010`.

## Тесты

Из каталога `world-backend/`:

```bash
pytest -q
```

Либо тем же интерпретатором, что бот: `../bot/.venv313/bin/python -m pytest -q`.
