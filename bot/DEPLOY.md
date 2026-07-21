# Развёртывание бота Фоксинбург (MAX + Telegram) на сервере

Сервис — FastAPI-приложение (`app.main:app`). Нужен Linux-сервер с публичным
HTTPS-доменом. Базы данных не требуется: состояние диалогов и журнал «пробелов»
хранятся в файлах в каталоге `/data`.

## Что подготовить заранее

1. **Сервер** (например ВМ в Yandex Cloud): Ubuntu 22.04+, 1–2 vCPU, 1–2 ГБ RAM,
   публичный IP.
2. **Домен/поддомен**, например `bot.dymova-english.ru`, с **A-записью** на IP сервера.
3. **Открытые порты** 80 и 443 в группе безопасности (в Yandex Cloud — Security Group ВМ).
4. **Секреты:** токен MAX, токен Telegram из @BotFather, ключ BigBen, ключ LLM,
   секреты webhook, ID администраторов.

---

## Вариант A — Docker (рекомендуется)

```bash
# 1. Поставить Docker (Ubuntu)
curl -fsSL https://get.docker.com | sudo sh

# 2. Забрать код
git clone https://github.com/Dymovgrigory/Dymova-english.git
cd Dymova-english/bot

# 3. Заполнить секреты
cp .env.example .env
nano .env   # MAX_BOT_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_URL,
            # TELEGRAM_WEBHOOK_SECRET, BIGBEN_API_KEY, LLM_API_KEY,
            # MAX_WEBHOOK_SECRET, ADMIN_MAX_IDS=5897639,
            # TELEGRAM_ADMIN_IDS=12345678, MINIAPP_BASE_URL=https://<домен>/app/

# 4. Указать свой домен
nano deploy/Caddyfile   # заменить bot.dymova-english.ru на ваш домен

# 5. Запустить (бот + HTTPS поднимутся автоматически)
sudo docker compose up -d

# 6. Проверить
curl https://<домен>/health
curl https://<домен>/health/telegram
```

Обновление версии:
```bash
git pull && sudo docker compose up -d --build
```

---

## Вариант B — без Docker (systemd + Caddy)

```bash
# 1. Зависимости
sudo apt update && sudo apt install -y python3-venv caddy git
sudo useradd -r -m -d /opt/foxinburg foxinburg

# 2. Код + venv
sudo -u foxinburg git clone https://github.com/Dymovgrigory/Dymova-english.git /opt/foxinburg/Dymova-english
sudo ln -s /opt/foxinburg/Dymova-english/bot /opt/foxinburg/bot
cd /opt/foxinburg/bot
sudo -u foxinburg python3 -m venv .venv
sudo -u foxinburg .venv/bin/pip install -r requirements.txt

# 3. Секреты (chmod 600)
sudo cp .env.example /etc/foxinburg-bot.env
sudo nano /etc/foxinburg-bot.env   # те же значения + STATE_FILE=/opt/foxinburg/data/state.json,
                                   # INSIGHTS_FILE=/opt/foxinburg/data/insights.jsonl
sudo chmod 600 /etc/foxinburg-bot.env
sudo -u foxinburg mkdir -p /opt/foxinburg/data

# 4. systemd-сервис
sudo cp deploy/foxinburg-bot.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now foxinburg-bot

# 5. Caddy (HTTPS): вписать домен в /etc/caddy/Caddyfile (блок reverse_proxy localhost:8000)
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile   # затем поправить домен и раскомментировать localhost-блок
sudo systemctl restart caddy

# 6. Проверить
curl https://<домен>/health
curl https://<домен>/health/telegram
```

---

## Завершающий шаг — регистрация webhook в MAX (для обоих вариантов)

```bash
curl -X POST https://<домен>/admin/set-webhook \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: <ADMIN_TOKEN если задан>" \
  -d '{"url": "https://<домен>/webhook"}'
```

## Telegram: webhook или polling

После деплоя Telegram работает так:

- если в `.env` задан `TELEGRAM_WEBHOOK_URL=https://<домен>/telegram/webhook`,
  бот при старте сам вызывает `setWebhook` с `TELEGRAM_WEBHOOK_SECRET`;
- если `TELEGRAM_WEBHOOK_URL` пустой, бот удаляет webhook и запускает polling;
- принудительно перерегистрировать webhook можно вручную:
  ```bash
  curl -X POST https://<домен>/admin/telegram/set-webhook \
    -H "X-Admin-Token: <ADMIN_TOKEN>"
  ```

Проверка со стороны Telegram (локально, не публикуя токен):

```bash
curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo" | jq
```

Ожидаемо: `url=https://<домен>/telegram/webhook`, нет `last_error_message`,
`secret_token` совпадает с `TELEGRAM_WEBHOOK_SECRET`.

После этого:
- напишите боту в MAX и в Telegram — он должен ответить;
- проверьте запись на пробное → заявка появится в BigBen (воронка «Бот Макс»);
- ежедневный отчёт придёт администраторам в 21:00 (МСК), команда `/отчёт` доступна админам.

## Заметки по Yandex Cloud

- Открыть 80/443 в **Security Group** сетевого интерфейса ВМ.
- Доступ Groq/OpenRouter с ВМ обычно есть; проверить:
  `curl -s -o /dev/null -w "%{http_code}\n" https://openrouter.ai/api/v1/models`.
  Если недоступен — сменить провайдера LLM (`LLM_BASE_URL`/`LLM_MODEL`) или поднять исходящий прокси.
- Для домена можно использовать поддомен основного сайта (A-запись у регистратора домена `dymova-english.ru`).
