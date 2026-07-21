# Telegram bot quick recovery

Симптом: сервис отвечает на `/health`, но Telegram-бот молчит.

1. Проверить env на сервере:
   ```bash
   docker compose exec bot env | grep -E 'TELEGRAM|ADMIN_TOKEN'
   docker compose logs --tail=300 bot | grep -i telegram
   ```
   Нужны `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_URL=https://<домен>/telegram/webhook`,
   `TELEGRAM_WEBHOOK_SECRET`. Для polling вместо webhook оставьте `TELEGRAM_WEBHOOK_URL` пустым.

2. Проверить Telegram webhook локально, не публикуя токен:
   ```bash
   curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo" | jq
   ```
   Не должно быть `last_error_message`; URL и secret должны совпадать с серверными.

3. Перерегистрировать webhook через сервис:
   ```bash
   curl -X POST https://<домен>/admin/telegram/set-webhook -H "X-Admin-Token: <ADMIN_TOKEN>"
   ```
   или напрямую в Telegram:
   ```bash
   curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
     -d "url=https://<домен>/telegram/webhook" \
     -d "secret_token=$TELEGRAM_WEBHOOK_SECRET" \
     -d 'allowed_updates=["message"]'
   ```

4. Если webhook не нужен: очистите `TELEGRAM_WEBHOOK_URL`, перезапустите сервис —
   на старте поднимется polling. Для polling webhook в Telegram должен быть удалён.
