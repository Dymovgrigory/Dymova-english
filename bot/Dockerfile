FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Предпочитать IPv4 при резолве имён.
#
# На хосте (Yandex Cloud) нет маршрута в IPv6, а api.telegram.org отдаёт и
# A, и AAAA. glibc по умолчанию ставит IPv6 первым, httpx подключается
# ТОЛЬКО к первому адресу и не откатывается на IPv4 — получался
# "[Errno 101] Network is unreachable" на каждый getUpdates. Из-за этого
# Telegram-бот молчал с 27.07.2026, а простой маскировался тем, что
# трафик шёл через платный SOCKS-прокси (тот в свою очередь умер).
# С этой строкой Telegram API доступен с сервера напрямую, без прокси;
# заодно чинится тот же класс проблем для остальных внешних API.
#
# ВНЕ Docker (вариант с systemd, см. DEPLOY.md) то же самое нужно
# прописать в /etc/gai.conf хоста.
RUN printf 'precedence ::ffff:0:0/96  100\n' > /etc/gai.conf

WORKDIR /app

COPY requirements.txt pyproject.toml /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
