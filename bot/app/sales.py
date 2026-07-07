"""Sales Engine: системный промт консультанта и работа с возражениями.

Бот ведёт себя как опытный менеджер по продажам Фоксинбурга: не просто отвечает
на вопрос, а выявляет потребность и мягко ведёт к записи на бесплатную
диагностику / пробный урок.
"""
from __future__ import annotations

from app.knowledge.kb import KnowledgeBase
from app.memory import Conversation

SYSTEM_PROMPT = """\
Ты — старший консультант и менеджер по продажам языковой школы «Фоксинбург» \
(Foxy Fox) в Долгопрудном. Ты прекрасно знаешь школу: курсы, цены, расписание, \
филиалы, преподавателей, методику, акции. Общайся как живой опытный сотрудник, \
а не как бот.

Правила общения:
- Пиши тепло, дружелюбно и по-человечески, на «вы», короткими абзацами. \
Уместно используй эмодзи (1–2 на сообщение), но без перебора.
- Отвечай ТОЛЬКО на основе предоставленного контекста базы знаний. Если данных \
нет — честно скажи и предложи уточнить у администратора, не выдумывай факты, \
цены и номера.
- Ты не просто отвечаешь на вопрос — ты ведёшь продажу: задаёшь уточняющие \
вопросы (возраст ребёнка, формат онлайн/офлайн, удобный филиал) и подводишь к \
следующему шагу — бесплатной диагностике или пробному уроку.
- Не вываливай всю информацию сразу. Сначала пойми потребность, затем дай \
точный и краткий ответ.
- Никогда не обещай того, чего нет в базе знаний. Не указывай неверные цены.
- Если клиент готов записаться — переходи к сбору данных для заявки.

Школа: мини-группы до 7 человек, дети от 2 до 18 лет и взрослые, английский, \
немецкий и китайский. Слоган: «Английский не для школы, а для жизни!».
"""


def build_system_prompt(kb: KnowledgeBase, conv: Conversation, kb_context: str) -> str:
    parts = [SYSTEM_PROMPT]
    if kb.branches:
        branch_lines = []
        for branch in kb.branches:
            name = branch.get("name", "").strip()
            address = branch.get("address", "").strip()
            if name or address:
                branch_lines.append(f"- {name}: {address}".strip())
        if branch_lines:
            parts.append("\nФИЛИАЛЫ:\n" + "\n".join(branch_lines))
    if kb_context:
        parts.append("\nКОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ (используй только эти факты):\n" + kb_context)
    card = conv.client_card()
    if card:
        parts.append("\nКАРТОЧКА КЛИЕНТА:\n" + card)
    state_bits = []
    if conv.lead.fio_parent:
        state_bits.append(f"собеседник — РОДИТЕЛЬ; имя родителя (собеседник): {conv.lead.fio_parent}")
        state_bits.append("упоминай ребёнка по имени, но обращайся к родителю")
    if conv.lead.age:
        state_bits.append(f"возраст ребёнка: {conv.lead.age}")
    if conv.selected_format:
        state_bits.append(f"формат: {conv.selected_format}")
    if conv.selected_branch:
        state_bits.append(f"филиал: {conv.selected_branch}")
    if state_bits:
        parts.append("\nЧто уже известно о клиенте: " + ", ".join(state_bits) + ".")
    return "\n".join(parts)


def handle_objection(kb: KnowledgeBase, key: str) -> str:
    text = kb.objection(key)
    if text:
        return text
    return (
        "Понимаю ваши сомнения. Давайте начнём с бесплатной диагностики — "
        "это ни к чему не обязывает, а вы увидите уровень ребёнка и нашу "
        "методику. Подобрать удобное время? 😊"
    )


def sales_nudge(conv: Conversation) -> str:
    """Короткий призыв к следующему шагу в зависимости от того, что уже известно."""
    if not conv.lead.age:
        return "Подскажите, пожалуйста, сколько лет ребёнку — подберу подходящую программу."
    if not conv.selected_format:
        return "Вам удобнее офлайн (Лихачевский / Ракетостроителей) или онлайн?"
    return "Хотите, я запишу вас на бесплатную диагностику? Это быстро и бесплатно 😊"
