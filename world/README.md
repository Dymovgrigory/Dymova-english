# Foxinburg World

Фронтенд игрового мира «Фоксинбург» — 3D-сцена на Next.js + React Three Fiber.
Бэкенд — отдельный процесс `world-backend/` (порт 8010), не школьный бот и не CRM.

## Запуск

Нужен запущенный игровой API:

```bash
cd ../world-backend && uvicorn main:app --port 8010
```

Затем здесь:

```bash
npm install
npm run dev
```

Откройте [http://localhost:3000](http://localhost:3000) (если порт занят — Next возьмёт 3002).

## Переменные окружения

См. `.env.example`. `NEXT_PUBLIC_WORLD_API` — адрес игрового API, по умолчанию
`http://localhost:8010`.

## Проверки

```bash
npx tsc --noEmit
npm test
npm run build
```
