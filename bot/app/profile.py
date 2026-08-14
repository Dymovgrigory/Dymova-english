"""Единая карточка клиента: всё, что бот о человеке знает.

ТЗ перечисляет поля профиля одним списком, но хранить их одним объектом
было бы ошибкой: имя и телефон живут в `Lead` (их забирает CRM), понимание
потребности — в `NeedProfile` (его ведёт протокол SMART), этап — в самом
диалоге. Второе хранилище тех же данных означало бы рассинхрон, а он в
разговоре виден сразу: бот здоровается с одним именем и записывает другое.

Поэтому здесь не хранилище, а **вид**: `UserProfile.of(conv)` собирает
карточку из канонических источников. Пишут по-прежнему в источники; читают —
здесь: системный промпт, передача администратору, будущий движок подбора.

Единственное, что профиль считает сам, — температура лида: она не факт, а
вывод из фактов, и хранить её значило бы протухнуть на первой же реплике.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.smart import STAGE_COLD, STAGE_READY, STAGE_WARMING, WHO_PARENT

# Температура лида. Названия — те же, что менеджеры используют вслух.
TEMP_COLD = "холодный"
TEMP_WARM = "тёплый"
TEMP_HOT = "горячий"


@dataclass
class UserProfile:
    """Снимок знаний о клиенте. Только чтение: источники правды — в диалоге."""

    # Кто перед нами
    name: str = ""
    child_name: str = ""
    child_age: str = ""
    child_grade: str = ""
    decision_maker: str = ""

    # Что с английским
    english_level: str = ""
    previous_learning: str = ""

    # Зачем
    goals: list[str] = field(default_factory=list)
    motivations: list[str] = field(default_factory=list)
    pain_points: list[str] = field(default_factory=list)

    # Условия
    preferred_format: str = ""
    schedule: str = ""
    budget: str = ""
    location: str = ""

    # Где мы в разговоре
    objections: list[str] = field(default_factory=list)
    urgency: str = ""
    lead_temperature: str = TEMP_COLD
    conversation_stage: str = STAGE_COLD
    recommended_program: str = ""

    @classmethod
    def of(cls, conv) -> "UserProfile":
        need = conv.need
        return cls(
            name=conv.lead.fio_parent or conv.client_name,
            child_name=conv.child_label(),
            child_age=need.child_age or conv.lead.age,
            child_grade=need.child_grade,
            decision_maker=need.decision_maker
            or (WHO_PARENT if conv.lead.fio_parent else ""),
            english_level=need.level,
            previous_learning=need.previous_experience,
            goals=list(need.goals),
            motivations=list(need.motivations),
            pain_points=list(need.pain_points),
            preferred_format=need.preferred_format or conv.selected_format,
            schedule=need.schedule,
            budget=need.budget,
            location=conv.selected_branch or conv.lead.branch or conv.lead.city,
            objections=list(need.objections) or _one(conv.last_objection),
            urgency=need.urgency,
            lead_temperature=temperature(conv),
            conversation_stage=need.stage(),
            recommended_program=conv.recommended_program
            or conv.selected_course
            or conv.lead.course,
        )

    def known(self) -> dict:
        """Только заполненные поля — для логов и передачи человеку."""
        return {
            key: value
            for key, value in self.__dict__.items()
            if value and key not in ("lead_temperature", "conversation_stage")
        }

    def as_card(self) -> str:
        """Карточка человеческим языком, по строке на факт."""
        rows = [
            ("Родитель", self.name),
            ("Ребёнок", self.child_name),
            ("Возраст", self.child_age),
            ("Класс", self.child_grade),
            ("Уровень", self.english_level),
            ("Учился раньше", self.previous_learning),
            ("Цели", ", ".join(self.goals)),
            ("Что мотивирует", ", ".join(self.motivations)),
            ("Сложности", ", ".join(self.pain_points)),
            ("Формат", self.preferred_format),
            ("Время", self.schedule),
            ("Бюджет", self.budget),
            ("Филиал", self.location),
            ("Сомнения", ", ".join(self.objections)),
            ("Срочность", self.urgency),
            ("Подобрано", self.recommended_program),
        ]
        lines = [f"{label}: {value}" for label, value in rows if value]
        lines.append(f"Температура: {self.lead_temperature}")
        return "\n".join(lines)


def lead_summary(conv) -> str:
    """Сводка для администратора, который продолжит разговор вместо бота.

    Человеку, который открывает переписку впервые, нужно за десять секунд
    понять: кто это, что ему нужно, что мешает и насколько он готов. Раньше
    администратор получал этап воронки и поля заявки — то есть всё, кроме
    ответов на эти вопросы.
    """
    card = UserProfile.of(conv)
    lines = ["ЗАЯВКА"]
    contacts = [
        value
        for value in (conv.lead.fio_parent, conv.lead.phone, conv.lead.email)
        if value
    ]
    if contacts:
        lines.append("Контакты: " + ", ".join(contacts))
    lines.append(card.as_card())
    if conv.stage:
        lines.append(f"Этап: {conv.stage}")
    if conv.lead.comment:
        lines.append(f"Комментарий: {conv.lead.comment}")
    return "\n".join(line for line in lines if line)


def temperature(conv) -> str:
    """Насколько человек близок к решению.

    Считается по поступкам, а не по вежливости: оставленный телефон и
    выбранный курс весят больше, чем длина переписки. Сомнение снижает
    температуру только у тёплого — у того, кто уже оставил заявку, вопрос
    «а не дорого ли» это уточнение, а не отказ.
    """
    need = conv.need
    if conv.lead_submitted or conv.lead.phone:
        return TEMP_HOT
    stage = need.stage()
    if stage == STAGE_READY and (conv.selected_course or conv.recommended_program):
        return TEMP_HOT
    if stage == STAGE_READY:
        return TEMP_WARM
    if stage == STAGE_WARMING:
        return TEMP_COLD if need.objections else TEMP_WARM
    return TEMP_COLD


def _one(value: str) -> list[str]:
    return [value] if value else []


__all__ = [
    "TEMP_COLD",
    "TEMP_HOT",
    "TEMP_WARM",
    "UserProfile",
    "lead_summary",
    "temperature",
]
