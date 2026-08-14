"""SMART — протокол выявления потребности.

    S — Situation    кто обращается, возраст, уровень, опыт, ограничения
    M — Motivation   зачем на самом деле, что беспокоит, почему именно сейчас
    A — Aim          какой результат нужен
    R — Relevance    есть ли у школы решение под эту ситуацию
    T — Transition   только теперь можно предлагать

Смысл модуля — превратить «продавать или уточнять» из решения промпта в
проверяемое состояние. Раньше системный промпт требовал вести к записи в
каждом ответе, поэтому на «сколько стоит?» бот звал на диагностику, ничего
не зная о человеке. Теперь предложение разрешает `sales_allowed`, и оно
считается по фактам, а не по настроению модели.

Модуль намеренно не импортирует `app.memory`: `NeedProfile` хранится внутри
диалога, и обратная зависимость дала бы цикл. Всё, что нужно от диалога,
берётся по утиной типизации.
"""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field

from app.llm_gateway import ROLE_FAST, get_gateway
from app.pii import PiiVault

logger = logging.getLogger(__name__)

# --- кто перед нами ---
WHO_PARENT = "parent"
WHO_ADULT = "adult"
WHO_TEEN = "teen"

# --- уровень готовности к предложению ---
STAGE_COLD = "cold"          # ничего не знаем
STAGE_WARMING = "warming"    # знаем ситуацию, но не цель
STAGE_READY = "ready"        # ситуация + цель/боль — можно предлагать


@dataclass
class NeedProfile:
    """Что мы поняли о человеке. Пустая строка/список = «пока не знаем»."""

    # Situation
    who: str = ""
    child_age: str = ""
    child_grade: str = ""
    level: str = ""
    previous_experience: str = ""
    preferred_format: str = ""
    schedule: str = ""
    constraints: list[str] = field(default_factory=list)

    # Motivation
    motivations: list[str] = field(default_factory=list)
    pain_points: list[str] = field(default_factory=list)
    trigger: str = ""

    # Aim
    goals: list[str] = field(default_factory=list)

    # Relevance / служебное
    budget: str = ""
    decision_maker: str = ""
    urgency: str = ""
    objections: list[str] = field(default_factory=list)
    # Сколько уточняющих вопросов уже задано — защита от превращения
    # разговора в анкету.
    questions_asked: int = 0
    # Слоты, о которых уже спрашивали: повторно не переспрашиваем, даже если
    # человек ответил уклончиво. Второй раз тот же вопрос — верный признак
    # бота, который не слушает.
    asked_slots: list[str] = field(default_factory=list)

    # ---------- сериализация ----------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "NeedProfile":
        """Терпимо читает старые записи: незнакомые ключи игнорируются."""
        if not isinstance(data, dict):
            return cls()
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    # ---------- сведения о полноте ----------
    def knows_situation(self) -> bool:
        """Понимаем, для кого подбираем занятия."""
        return bool(self.child_age or self.who in (WHO_ADULT, WHO_TEEN))

    def knows_purpose(self) -> bool:
        """Понимаем, зачем человек пришёл — цель или боль."""
        return bool(self.goals or self.pain_points or self.motivations)

    def stage(self) -> str:
        if self.knows_situation() and self.knows_purpose():
            return STAGE_READY
        if self.knows_situation() or self.knows_purpose():
            return STAGE_WARMING
        return STAGE_COLD

    def missing(self) -> list[str]:
        """Чего не хватает, в порядке важности для рекомендации."""
        gaps: list[str] = []
        if not self.knows_situation():
            gaps.append("who")
        if not self.knows_purpose():
            gaps.append("purpose")
        if not self.level and not self.previous_experience:
            gaps.append("level")
        if not self.preferred_format:
            gaps.append("format")
        if not self.schedule:
            gaps.append("schedule")
        return gaps

    def merge(self, other: "NeedProfile") -> None:
        """Дополняет профиль новыми фактами, не затирая известные.

        Пустое значение из свежего разбора не должно стирать то, что человек
        сказал десять реплик назад: модель видит только последние сообщения
        и легко «забудет» ранний факт.
        """
        for name in self.__dataclass_fields__:
            if name in ("questions_asked", "asked_slots"):
                continue
            new = getattr(other, name)
            if not new:
                continue
            current = getattr(self, name)
            if isinstance(current, list):
                for item in new:
                    if item and item not in current:
                        current.append(item)
            else:
                setattr(self, name, new)


def summary(profile: NeedProfile) -> str:
    """Человекочитаемая выжимка для системного промпта и карточки менеджера."""
    rows: list[tuple[str, object]] = [
        ("кто обращается", {WHO_PARENT: "родитель", WHO_ADULT: "взрослый ученик",
                            WHO_TEEN: "подросток"}.get(profile.who, "")),
        ("возраст ученика", profile.child_age),
        ("класс", profile.child_grade),
        ("уровень", profile.level),
        ("предыдущий опыт", profile.previous_experience),
        ("цели", ", ".join(profile.goals)),
        ("что беспокоит", ", ".join(profile.pain_points)),
        ("мотивация", ", ".join(profile.motivations)),
        ("почему сейчас", profile.trigger),
        ("формат", profile.preferred_format),
        ("расписание", profile.schedule),
        ("ограничения", ", ".join(profile.constraints)),
        ("возражения", ", ".join(profile.objections)),
        ("срочность", profile.urgency),
    ]
    lines = [f"- {label}: {value}" for label, value in rows if value]
    return "\n".join(lines)


# ============================ извлечение ============================

_SCHEMA = {
    "type": "object",
    "properties": {
        "who": {"type": "string", "enum": [WHO_PARENT, WHO_ADULT, WHO_TEEN, ""]},
        "child_age": {"type": "string"},
        "child_grade": {"type": "string"},
        "level": {"type": "string"},
        "previous_experience": {"type": "string"},
        "preferred_format": {"type": "string"},
        "schedule": {"type": "string"},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "motivations": {"type": "array", "items": {"type": "string"}},
        "pain_points": {"type": "array", "items": {"type": "string"}},
        "trigger": {"type": "string"},
        "goals": {"type": "array", "items": {"type": "string"}},
        "budget": {"type": "string"},
        "urgency": {"type": "string"},
        "objections": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["who", "child_age", "goals", "pain_points"],
}

_EXTRACT_PROMPT = """\
Ты анализируешь переписку клиента с языковой школой и заполняешь карточку \
потребности. Верни только то, что человек действительно сказал или что \
однозначно следует из его слов.

Правила:
- Ничего не додумывай. Не уверен — оставь поле пустым.
- goals — желаемый результат («начать говорить», «подтянуть школьную \
программу», «подготовиться к ОГЭ», «убрать страх ошибки»).
- pain_points — что не так сейчас («не хочет заниматься», «боится говорить», \
«плохие оценки», «не понимает грамматику», «плохой прошлый опыт»).
- motivations — почему это важно для человека.
- trigger — почему вопрос возник именно сейчас.
- Скрытая потребность важнее буквальных слов: «ребёнок не хочет заниматься» \
— это pain_point «нет мотивации», а не запрос курса.
- Значения пиши короткими русскими фразами в нижнем регистре.
"""


async def extract(history: list[dict], vault: PiiVault | None = None) -> NeedProfile:
    """Разбирает переписку в профиль потребности.

    Никогда не бросает и не блокирует диалог: если модель недоступна или
    ответила мусором, возвращается пустой профиль, и работают только
    детерминированные подсказки (`enrich_from_text`).
    """
    if not history:
        return NeedProfile()
    gateway = get_gateway()
    if not gateway.enabled:
        return NeedProfile()

    transcript = "\n".join(
        f"{'Клиент' if m.get('role') == 'user' else 'Бот'}: {m.get('content', '')}"
        for m in history[-12:]
    )
    messages = [
        {"role": "system", "content": _EXTRACT_PROMPT},
        {"role": "user", "content": f"ПЕРЕПИСКА:\n{transcript}"},
    ]
    data = await gateway.structured(
        ROLE_FAST, messages, _SCHEMA, name="need_profile", vault=vault
    )
    if not data:
        return NeedProfile()
    return NeedProfile.from_dict(_clean(data))


def _clean(data: dict) -> dict:
    """Приводит ответ модели к ожидаемым типам.

    Модели регулярно отдают строку там, где в схеме массив, и наоборот —
    ронять из-за этого весь разбор незачем.
    """
    cleaned: dict = {}
    for key, value in data.items():
        if key not in NeedProfile.__dataclass_fields__:
            continue
        expected_list = key in (
            "constraints", "motivations", "pain_points", "goals", "objections"
        )
        if expected_list:
            if isinstance(value, str):
                value = [value] if value.strip() else []
            elif not isinstance(value, list):
                continue
            cleaned[key] = [str(v).strip() for v in value if str(v).strip()]
        else:
            if isinstance(value, (list, dict)):
                continue
            cleaned[key] = str(value).strip() if value is not None else ""
    return cleaned


# --- детерминированные подсказки: работают и без LLM ---

_AGE_RE = re.compile(r"(\d{1,2})\s*(?:лет|год[а]?|годик)")
_GRADE_RE = re.compile(r"(\d{1,2})\s*(?:-?[ыи]й\s*)?класс")
_ADULT_RE = re.compile(r"для себя|я сам|мне \d{2}|взросл\w*|для меня", re.IGNORECASE)
_PARENT_RE = re.compile(r"\bсын\w*|\bдоч\w*|ребён\w*|ребен\w*|мальчик\w*|девочк\w*", re.IGNORECASE)

_PAIN_MARKERS = (
    (r"не хочет|не хочу|не нравится|скучно|заставля", "нет мотивации"),
    (r"бо[ия]тся говорить|стесня|страх|боюсь|зажим", "страх говорить"),
    (r"плохие оценки|двойк|тройк|отстаёт|отстает|не успевает", "проблемы с оценками"),
    (r"не понимает|не понимаю|сложно|тяжело даётся|тяжело дается", "материал не даётся"),
    (r"прошл\w* школ|была репетитор|не подошл|разочаров", "плохой прошлый опыт"),
)
_GOAL_MARKERS = (
    # «начал говорить», «начать говорить», «заговорил» — одна и та же цель.
    (r"заговорил\w*|заговорить|нача\w+\s+говорить|разговорн|общатьс", "начать говорить"),
    (r"школьн\w* программ|подтянуть|успеваем", "подтянуть школьную программу"),
    (r"\bегэ\b|\bогэ\b|экзамен|поступ", "подготовка к экзамену"),
    (r"с нуля|начать учить|первый раз", "старт с нуля"),
    (r"переезд|за границ|виза|работ\w* за", "язык для жизни за границей"),
)


# Слова, по которым видно, что человек рассказывает о своей ситуации, а не
# задаёт справочный вопрос. Нужны, чтобы не гонять модель на «сколько стоит?».
_SIGNAL_RE = re.compile(
    r"\bсын\w*|\bдоч\w*|ребён\w*|ребен\w*|мальчик\w*|девочк\w*|класс\w*|"
    r"\bлет\b|\bгод\w*|хоч\w*|нужн\w*|не\s*могу|не\s*может|бо[ия]тс|"
    r"стесня|учил\w*|занима\w*|уровен\w*|с\s*нуля|экзамен|\bегэ\b|\bогэ\b|"
    r"проблем\w*|оценк\w*|для\s*себя|переезд",
    re.IGNORECASE,
)
# Длинное сообщение почти всегда содержит контекст, даже без опорных слов.
_INFORMATIVE_LENGTH = 60


def looks_informative(text: str) -> bool:
    """Стоит ли тратить запрос к модели на разбор этой реплики.

    Справочный вопрос («сколько стоит?», «а где вы находитесь?») о потребности
    не сообщает ничего, и разбор его моделью — это лишние деньги и, главное,
    лишняя задержка перед ответом. Дешёвый детерминированный разбор
    (`enrich_from_text`) при этом выполняется всегда.
    """
    clean = (text or "").strip()
    if len(clean) >= _INFORMATIVE_LENGTH:
        return True
    return bool(_SIGNAL_RE.search(clean))


def enrich_from_text(profile: NeedProfile, text: str) -> None:
    """Достаёт из реплики то, что видно без модели.

    Нужно на двух путях: когда LLM выключена и когда её разбор ничего не
    нашёл. Дублирование с LLM безвредно — `merge` не создаёт дубликатов.
    """
    low = (text or "").lower()
    if not low:
        return

    if not profile.child_age:
        match = _AGE_RE.search(low)
        if match and 1 <= int(match.group(1)) <= 99:
            profile.child_age = match.group(1)
    if not profile.child_grade:
        match = _GRADE_RE.search(low)
        if match:
            profile.child_grade = match.group(1)
    if not profile.who:
        if _PARENT_RE.search(low):
            profile.who = WHO_PARENT
        elif _ADULT_RE.search(low):
            profile.who = WHO_ADULT
    if not profile.preferred_format:
        if "онлайн" in low:
            profile.preferred_format = "онлайн"
        elif "офлайн" in low or "оффлайн" in low or "очно" in low:
            profile.preferred_format = "офлайн"

    for pattern, label in _PAIN_MARKERS:
        if re.search(pattern, low) and label not in profile.pain_points:
            profile.pain_points.append(label)
    for pattern, label in _GOAL_MARKERS:
        if re.search(pattern, low) and label not in profile.goals:
            profile.goals.append(label)


# ============================ гейт продажи ============================

# Даже полностью понятая потребность не даёт права давить в каждой реплике.
MAX_DISCOVERY_QUESTIONS = 4


def sales_allowed(profile: NeedProfile) -> bool:
    """Можно ли переходить к предложению.

    Разрешаем, когда понятны ситуация И цель/боль. Отдельно — предохранитель:
    если человек уже ответил на несколько вопросов, продолжать расспросы
    нельзя, это превращается в анкету. Тогда предлагаем то, что есть.
    """
    if profile.stage() == STAGE_READY:
        return True
    return profile.questions_asked >= MAX_DISCOVERY_QUESTIONS


# Формулировки на каждый пробел. Вариантов несколько, чтобы повторный заход
# в тот же слот не звучал копией предыдущей реплики.
_QUESTIONS: dict[str, tuple[str, ...]] = {
    "who": (
        "Подскажите, для кого подбираете занятия — и сколько лет ученику?",
        "А занятия для ребёнка или для себя? Если для ребёнка, сколько ему лет?",
    ),
    "purpose": (
        "А какая сейчас основная задача — подтянуть школьную программу, "
        "начать увереннее говорить или что-то другое?",
        "Расскажите, что подтолкнуло искать занятия — что сейчас беспокоит больше всего?",
    ),
    "level": (
        "Английский уже учили или начинаете с нуля?",
        "А как сейчас с английским — есть база или начинаем с самого начала?",
    ),
    "format": (
        "Вам удобнее заниматься очно в Долгопрудном или онлайн?",
        "Как удобнее — приезжать в филиал или заниматься из дома?",
    ),
    "schedule": (
        "В какое время обычно удобно заниматься — днём, после школы или ближе к вечеру?",
        "Подскажите, какие дни и время вам подходят — подберу группу под расписание.",
    ),
}

# Первый вопрос можно задать парой: возраст и опыт — естественная связка,
# которую человек и сам произносит одним предложением.
_PAIRED_OPENER = (
    "А сколько лет ребёнку? И если знаете, примерно какой сейчас уровень английского?"
)


def next_question(profile: NeedProfile, paired_opener: bool = True) -> str | None:
    """Один следующий вопрос — или None, если спрашивать больше нечего.

    Ровно один: список из пяти вопросов подряд выглядит как CRM-форма, а не
    как разговор (см. «правило одного хорошего вопроса» в ТЗ).
    """
    if profile.questions_asked >= MAX_DISCOVERY_QUESTIONS:
        return None
    for slot in profile.missing():
        if slot in profile.asked_slots:
            continue
        if slot == "who" and paired_opener and not profile.questions_asked:
            return _PAIRED_OPENER
        variants = _QUESTIONS.get(slot)
        if not variants:
            continue
        return variants[profile.questions_asked % len(variants)]
    return None


# Ответ на названную проблему. Каталог программ в ответ на «ребёнок не хочет
# заниматься» — ровно то, за что бота считают бездушным: человек рассказал о
# трудности, а ему прислали прайс. Сначала признаём проблему и выясняем причину.
_PAIN_REPLIES: dict[str, tuple[str, str]] = {
    "нет мотивации": (
        "Понимаю, это частая история.",
        "А как вам кажется, дело скорее в самом английском или в том, что не "
        "подходит формат занятий?",
    ),
    "страх говорить": (
        "Это знакомая ситуация, и она решаема.",
        "А страх появляется на уроке при всех или вообще, когда нужно "
        "что-то сказать вслух?",
    ),
    "проблемы с оценками": (
        "Понимаю, за оценки всегда тревожно.",
        "Подскажите, сложности больше с грамматикой и письменными работами "
        "или с устными ответами?",
    ),
    "материал не даётся": (
        "Понимаю.",
        "А что именно даётся тяжелее всего — грамматика, слова или "
        "понимание на слух?",
    ),
    "плохой прошлый опыт": (
        "Жаль, что так вышло.",
        "Расскажите, что тогда не устроило — так я пойму, чего точно не "
        "стоит повторять.",
    ),
}


def pain_in_text(text: str) -> str | None:
    """Проблема, названная в этой реплике, — если она названа."""
    low = (text or "").lower()
    for pattern, label in _PAIN_MARKERS:
        if re.search(pattern, low):
            return label
    return None


def pain_reply(pain: str) -> tuple[str, str]:
    """Пара «признание проблемы, уточняющий вопрос»."""
    return _PAIN_REPLIES.get(
        pain,
        ("Понимаю.", "Расскажите чуть подробнее, в чём именно сейчас сложность?"),
    )


def mark_asked(profile: NeedProfile, question: str | None) -> None:
    """Отмечает заданный вопрос, чтобы не спросить то же самое дважды."""
    if not question:
        return
    profile.questions_asked += 1
    if question == _PAIRED_OPENER:
        profile.asked_slots.extend(["who", "level"])
        return
    for slot, variants in _QUESTIONS.items():
        if question in variants:
            if slot not in profile.asked_slots:
                profile.asked_slots.append(slot)
            return


__all__ = [
    "MAX_DISCOVERY_QUESTIONS",
    "NeedProfile",
    "STAGE_COLD",
    "STAGE_READY",
    "STAGE_WARMING",
    "WHO_ADULT",
    "WHO_PARENT",
    "WHO_TEEN",
    "enrich_from_text",
    "extract",
    "mark_asked",
    "next_question",
    "sales_allowed",
    "summary",
]
