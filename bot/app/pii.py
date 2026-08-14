"""Редакция персональных данных перед отправкой в LLM.

Бот собирает ФИО родителя, имя и дату рождения ребёнка и телефон — это
персональные данные, в том числе несовершеннолетних. Отправлять их во внешнюю
модель в открытом виде нельзя, но и обезличивать диалог до неузнаваемости
тоже: консультант обязан обращаться к человеку по имени.

Компромисс — подстановка. Реальное значение заменяется устойчивым
плейсхолдером (`{{CHILD_NAME}}`), модель работает с ним как с обычным словом
и свободно вставляет его в ответ, а перед отправкой пользователю плейсхолдер
разворачивается обратно. Модель никогда не видит настоящих данных, а человек
никогда не видит плейсхолдеров.

    vault = PiiVault()
    vault.hide("CHILD_NAME", "Маша")
    vault.redact("Маше 9 лет")                    # -> "{{CHILD_NAME}} 9 лет"
    vault.restore("Запишем {{CHILD_NAME:вин}}?")  # -> "Запишем Машу?"

Падеж модель помечает сама (`{{CHILD_NAME:дат}}`), иначе разворачивание
всегда в именительный давало бы «записываю Маша на диагностику» — робо-речь,
которой в живом диалоге быть не должно. Правила склонения — в `app.morph`.

При редакции ищется точное совпадение: подменять склонённые формы («Маше»,
«Машу») в тексте пользователя мы не пытаемся — это цена за отсутствие ложных
срабатываний на обычных словах.
"""
from __future__ import annotations

import re

from app.morph import CASES, NOMINATIVE, decline

# Телефон в свободном тексте прячем всегда, даже если он ещё не попал в лид:
# человек может продиктовать номер в любой реплике.
_PHONE_RE = re.compile(
    r"(?:\+7|8|7)?[\s\-.(]*\d{3}[\s\-.)]*\d{3}[\s\-.)]*\d{2}[\s\-.)]*\d{2}"
)
# Слишком короткое значение прятать опасно: подстрока из двух-трёх букв
# встретится в обычных словах и изуродует текст.
_MIN_SECRET_LEN = 3
_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_][A-Z0-9_]*)(?::([а-я]+))?\}\}")


class PiiVault:
    """Двусторонний словарь «плейсхолдер ↔ реальное значение» для одного диалога."""

    def __init__(self) -> None:
        self._to_real: dict[str, str] = {}
        self._to_placeholder: dict[str, str] = {}

    def hide(self, label: str, value: str) -> str:
        """Регистрирует значение под плейсхолдером `{{label}}`.

        Возвращает плейсхолдер; для пустого или слишком короткого значения —
        само значение (прятать нечего).
        """
        value = (value or "").strip()
        if len(value) < _MIN_SECRET_LEN:
            return value
        existing = self._to_placeholder.get(value)
        if existing:
            return existing
        placeholder = f"{{{{{label}}}}}"
        # Одно и то же имя у родителя и ребёнка — редкость, но плейсхолдер
        # должен остаться уникальным, иначе restore вернёт не то значение.
        if placeholder in self._to_real:
            suffix = 2
            while f"{{{{{label}_{suffix}}}}}" in self._to_real:
                suffix += 1
            placeholder = f"{{{{{label}_{suffix}}}}}"
        self._to_real[placeholder] = value
        self._to_placeholder[value] = placeholder
        return placeholder

    def redact(self, text: str) -> str:
        """Заменяет известные значения и любые телефоны на плейсхолдеры."""
        if not text:
            return text
        # Длинные значения первыми: иначе «Иванова Анна» подменится по куску
        # «Иванова», и остаток «Анна» уедет в модель открытым текстом.
        for value in sorted(self._to_placeholder, key=len, reverse=True):
            if value in text:
                text = text.replace(value, self._to_placeholder[value])
        return _PHONE_RE.sub(self._hide_phone, text)

    def restore(self, text: str) -> str:
        """Разворачивает плейсхолдеры обратно в реальные значения.

        Понимает и голый `{{LABEL}}`, и помеченный падежом `{{LABEL:вин}}`.
        Склоняются только имена: телефон и дата в падежах не нуждаются.
        """
        if not text:
            return text
        return _PLACEHOLDER_RE.sub(self._restore_one, text)

    def _restore_one(self, match: re.Match[str]) -> str:
        label, case = match.group(1), (match.group(2) or NOMINATIVE)
        value = self._to_real.get(f"{{{{{label}}}}}")
        if value is None:
            # Модель выдумала плейсхолдер, которого мы не регистрировали.
            # Оставляем как есть — пусть это будет видно, а не молча исчезнет.
            return match.group(0)
        if "NAME" not in label or case not in CASES:
            return value
        return decline(value, case)

    def _hide_phone(self, match: re.Match[str]) -> str:
        return self.hide("PHONE", match.group(0))

    def placeholders(self) -> list[str]:
        """Метки зарегистрированных значений, без фигурных скобок."""
        return [p.strip("{}") for p in self._to_real]

    def __bool__(self) -> bool:
        return bool(self._to_real)


def vault_for(conv) -> PiiVault:
    """Собирает хранилище по данным диалога.

    Принимает любой объект с полями `lead` и `client_name` — привязка к
    конкретному классу здесь не нужна и мешала бы тестам.
    """
    vault = PiiVault()
    lead = getattr(conv, "lead", None)
    if lead is not None:
        vault.hide("PARENT_NAME", getattr(lead, "fio_parent", "") or "")
        vault.hide("CHILD_NAME", getattr(lead, "fio_child", "") or "")
        vault.hide("PHONE", getattr(lead, "phone", "") or "")
        vault.hide("BIRTHDAY", getattr(lead, "birthday", "") or "")
        vault.hide("EMAIL", getattr(lead, "email", "") or "")
    vault.hide("CLIENT_NAME", getattr(conv, "client_name", "") or "")
    return vault


def redact_messages(vault: PiiVault, messages: list[dict]) -> list[dict]:
    """Копия списка сообщений с заредактированным текстовым содержимым.

    Мультимодальные части (список блоков с картинками) проходят насквозь:
    подменять base64 изображения бессмысленно, а ронять их — вредно.
    """
    if not vault:
        return messages
    redacted: list[dict] = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, str):
            redacted.append({**message, "content": vault.redact(content)})
        else:
            redacted.append(message)
    return redacted


def placeholder_hint(vault: PiiVault) -> str:
    """Инструкция для модели: какие плейсхолдеры есть и как их склонять.

    Без неё модель либо не поймёт `{{CHILD_NAME}}` и перепишет его словами,
    либо вставит только в именительном падеже.
    """
    labels = [p for p in vault.placeholders() if "NAME" in p]
    if not labels:
        return ""
    listed = ", ".join(f"{{{{{label}}}}}" for label in labels)
    return (
        f"ИМЕНА В ДИАЛОГЕ ЗАМЕНЕНЫ ТОКЕНАМИ: {listed}. Это настоящие имена — "
        "используй их в ответе как обычные слова. Если нужен падеж, кроме "
        "именительного, поставь пометку через двоеточие: "
        "{{CHILD_NAME:род}}, {{CHILD_NAME:дат}}, {{CHILD_NAME:вин}}, "
        "{{CHILD_NAME:твор}}, {{CHILD_NAME:пред}}. Не расшифровывай токены "
        "и не пиши их описание словами. Используй ТОЛЬКО перечисленные "
        "токены: если имени в списке нет, пиши обычными словами («ребёнку», "
        "«сыну»), а не выдумывай новый токен."
    )


__all__ = ["PiiVault", "placeholder_hint", "redact_messages", "vault_for"]
