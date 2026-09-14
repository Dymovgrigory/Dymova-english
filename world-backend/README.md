# Foxinburg World — API

Отдельная игровая платформа. Не школьный бот и не CRM.

## Запуск

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --port 8010 --reload
```

Health: [http://localhost:8010/health](http://localhost:8010/health)

Фронт (`../world`) ходит сюда: `NEXT_PUBLIC_WORLD_API=http://localhost:8010`.

## Тесты

Из каталога `world-backend/`:

```bash
pytest -q
```

Либо тем же интерпретатором, что бот: `../bot/.venv313/bin/python -m pytest -q`.
