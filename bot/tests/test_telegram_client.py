

def test_connect_timeout_is_short_so_dead_attempts_fail_fast():
    """Мёртвая попытка соединения не должна держать сообщение по 30–40 с."""
    from app import telegram_client

    timeout = telegram_client._client_kwargs(30)["timeout"]
    assert timeout.connect == telegram_client.CONNECT_TIMEOUT_SEC <= 5
    assert timeout.read == 30
