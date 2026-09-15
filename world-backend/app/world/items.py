"""Сборка заданий урока из каталога курса (ответы только на сервере)."""
from __future__ import annotations

import random
import re

from . import catalog, config, lesson_theory
from .foxi_poses import pose_for_item
from .word_library import teach_line

OPTIONS = 4


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _mcq(words: list[dict], count: int, rng: random.Random, *, prompt: str, options: str) -> list[dict]:
    picked = rng.sample(words, min(count, len(words)))
    questions = []
    for word in picked:
        distractors = [w[options] for w in words if w[options] != word[options]]
        take = min(OPTIONS - 1, len(distractors))
        opts = (rng.sample(distractors, take) if take else []) + [word[options]]
        rng.shuffle(opts)
        questions.append({
            "kind": "mcq_en_ru" if options == "ru" else "mcq_ru_en",
            "en": word["en"], "ru": word["ru"], "ipa": word["ipa"],
            "example_en": word["example_en"], "example_ru": word["example_ru"],
            "prompt": word[prompt],
            "options": opts,
            "correct_index": opts.index(word[options]),
            "correct_text": word[options],
        })
    return questions


def _type_en(words: list[dict], count: int, rng: random.Random) -> list[dict]:
    picked = rng.sample(words, min(count, len(words)))
    return [{
        "kind": "type_en",
        "en": w["en"], "ru": w["ru"], "ipa": w["ipa"],
        "example_en": w["example_en"], "example_ru": w["example_ru"],
        "prompt": w["ru"],
        "correct_text": w["en"],
    } for w in picked]


def _listen(words: list[dict], count: int, rng: random.Random, *, hear_en: bool = False) -> list[dict]:
    if hear_en:
        picked = rng.sample(words, min(count, len(words)))
        pool = [w["en"] for w in words]
        questions = []
        for word in picked:
            distractors = [e for e in pool if e != word["en"]]
            take = min(OPTIONS - 1, len(distractors))
            opts = (rng.sample(distractors, take) if take else []) + [word["en"]]
            rng.shuffle(opts)
            questions.append({
                "kind": "listen",
                "en": word["en"],
                "ru": word["ru"],
                "ipa": word.get("ipa", ""),
                "example_en": word.get("example_en", ""),
                "example_ru": word.get("example_ru", ""),
                "prompt": "Что сказал Foxy?",
                "speak": word["en"],
                "options": opts,
                "correct_index": opts.index(word["en"]),
                "correct_text": word["en"],
            })
        return questions
    items = _mcq(words, count, rng, prompt="en", options="ru")
    for it in items:
        it["kind"] = "listen"
        it["speak"] = it["en"]
        it["prompt"] = "Послушай слово"
    return items


def _mcq_phrase(words: list[dict], count: int, rng: random.Random) -> list[dict]:
    pool = list(dict.fromkeys((w.get("example_en") or w["en"]).strip() for w in words if (w.get("example_en") or w["en"]).strip()))
    picked = rng.sample(words, min(count, len(words)))
    questions = []
    for word in picked:
        correct = (word.get("example_en") or word["en"]).strip()
        distractors = [p for p in pool if p != correct]
        take = min(OPTIONS - 1, len(distractors))
        if take < 1:
            continue
        opts = rng.sample(distractors, take) + [correct]
        rng.shuffle(opts)
        questions.append({
            "kind": "mcq_en_ru",
            "en": word["en"],
            "ru": word["ru"],
            "ipa": word.get("ipa", ""),
            "image": word.get("image") or "",
            "example_en": word.get("example_en", ""),
            "example_ru": word.get("example_ru", ""),
            "prompt": word["en"],
            "options": opts,
            "correct_index": opts.index(correct),
            "correct_text": correct,
        })
    return questions


def _type_listen(words: list[dict], count: int, rng: random.Random) -> list[dict]:
    picked = rng.sample(words, min(count, len(words)))
    return [{
        "kind": "type_en",
        "en": w["en"],
        "ru": w["ru"],
        "ipa": w.get("ipa", ""),
        "example_en": w.get("example_en", ""),
        "example_ru": w.get("example_ru", ""),
        "prompt": "Напиши слово, которое сказал Foxy",
        "speak": w["en"],
        "correct_text": w["en"],
    } for w in picked]


def _match_phrase(words: list[dict], count: int, rng: random.Random) -> dict:
    usable = [
        w for w in words
        if (w.get("example_en") or "").strip() and _norm(w["example_en"]) != _norm(w["en"])
    ]
    source = usable if len(usable) >= 3 else words
    picked = rng.sample(source, min(count, len(source)))
    left = [w["en"] for w in picked]
    right = [(w.get("example_en") or w["en"]).strip() for w in picked]
    rng.shuffle(left)
    rng.shuffle(right)
    return {
        "kind": "match",
        "left": left,
        "right": right,
        "pairs": [{"en": w["en"], "ru": (w.get("example_en") or w["en"]).strip()} for w in picked],
    }


def _match(words: list[dict], count: int, rng: random.Random) -> dict:
    picked = rng.sample(words, min(count, len(words)))
    left = [w["en"] for w in picked]
    right = [w["ru"] for w in picked]
    rng.shuffle(left)
    rng.shuffle(right)
    return {
        "kind": "match",
        "left": left, "right": right,
        "pairs": [{"en": w["en"], "ru": w["ru"]} for w in picked],
    }


def _tap(phrases: list[dict], count: int, rng: random.Random) -> list[dict]:
    usable = [p for p in phrases if len(p["tokens"]) >= 2]
    picked = rng.sample(usable, min(count, len(usable)))
    items = []
    for p in picked:
        tokens = list(p["tokens"])
        bank = list(tokens)
        rng.shuffle(bank)
        items.append({
            "kind": "tap_build",
            "prompt": p["ru"],
            "bank": bank,
            "tokens_correct": tokens,
            "en": p["en"],
            "ru": p["ru"],
            "example_en": p["en"],
            "example_ru": p["ru"],
        })
    return items


def _join(tokens: list[str]) -> str:
    out = ""
    for token in tokens:
        if token in ".,!?;:'" or token.startswith("'"):
            out += token
        else:
            out += (" " if out else "") + token
    return out.strip()


def _fill(phrases: list[dict], words: list[dict], count: int, rng: random.Random) -> list[dict]:
    usable = [p for p in phrases if any(t.isalpha() for t in p["tokens"])]
    picked = rng.sample(usable, min(count, len(usable)))
    pool = [w["en"] for w in words]
    items = []
    for p in picked:
        candidates = [t for t in p["tokens"] if t.isalpha() and len(t) > 1]
        blank = rng.choice(candidates or [t for t in p["tokens"] if t.isalpha()] or ["a"])
        shown = _join(["____" if t == blank else t for t in p["tokens"]])
        distractors = [w for w in pool if _norm(w) != _norm(blank)]
        take = min(OPTIONS - 1, len(distractors))
        opts = (rng.sample(distractors, take) if take else []) + [blank]
        rng.shuffle(opts)
        items.append({
            "kind": "fill_blank",
            "prompt": shown,
            "hint_ru": p["ru"],
            "options": opts,
            "correct_index": opts.index(blank),
            "correct_text": blank,
            "en": p["en"],
            "ru": p["ru"],
            "example_en": p["en"],
            "example_ru": p["ru"],
        })
    return items


FOXI = {
    "explain": "Сначала правило простыми словами. Потом короткое задание.",
    "mcq_en_ru": "Выбери фразу. Смотри картинку, слушай слово.",
    "mcq_ru_en": "Как это сказать по-английски?",
    "type_en": "Напиши английскими буквами. Рядом есть транскрипция.",
    "listen": "Послушай и выбери, что услышал. Можно нажать «Слушать» ещё раз.",
    "match": "Соедини слово и живую фразу.",
    "tap_build": "Собери фразу по порядку — так, как говорят в классе.",
    "fill_blank": "Какого слова не хватает во фразе?",
}

FOXI_STAGE = {
    "warmup": "Я Foxy. Сегодня учим звуки, не алфавит. Читай по-русски.",
    "theory": "Сначала правило. Потом звук. Картинка помогает понять смысл.",
    "words": "Новое слово: фото, звук, перевод. Нажми «Слушать» и повтори.",
    "listen": "Только ухо. Можно слушать ещё раз.",
    "practice": "Теперь ты. Если ошибся — я покажу верный ответ, сердца минус одно.",
    "wrap": "Ты прошёл все этапы урока. Завтра следующий звук.",
}

FOXI_STAGE_ORAL = {
    "warmup": "Я Foxy, твой учитель. Сегодня говорим. Повторяй за мной вслух.",
    "theory": "Слушай объяснение, как на занятии. Потом скажи вместе со мной.",
    "words": "Карточка: картинка и фраза. Слушай, смотри, говори — перевод не зубри.",
    "listen": "Только ухо. Выбери английское слово, которое сказал Foxy.",
    "practice": "Задания как у доски. Не спеши. Я рядом.",
    "wrap": "Урок окончен. Скажи маме одну фразу с занятия — это домашнее.",
}


def _cards(raw: list, *, stage: str) -> list[dict]:
    cards = []
    for g in raw:
        cards.append({
            "kind": "explain",
            "stage": stage,
            "title_ru": g["title_ru"],
            "body_ru": g["body_ru"],
            "visual_id": g.get("visual_id", ""),
            "example_en": g.get("example_en", ""),
            "example_ru": g.get("example_ru", ""),
            "steps": list(g.get("steps") or []),
            "gpc": g.get("gpc", ""),
            "sound": g.get("sound", ""),
            "speak_sound": g.get("speak_sound", ""),
            "speak": g.get("speak", ""),
            "audio": g.get("audio", ""),
            "image": g.get("image", ""),
            "foxi_line": g.get("foxi_line") or g.get("foxi_ru") or "",
        })
    return cards


def _theory_head(unit: dict, unit_id: str, lesson_n: int, checkpoint: bool) -> list[dict]:
    lesson = catalog.get_lesson(unit_id, lesson_n)
    if lesson and lesson.get("cards") and not checkpoint:
        out: list[dict] = []
        for i, card in enumerate(lesson["cards"]):
            out.extend(_cards([card], stage="warmup" if i == 0 else "theory"))
        return out
    raw = lesson_theory.head(unit_id, lesson_n, checkpoint)
    out = []
    for i, card in enumerate(raw):
        out.extend(_cards([card], stage="warmup" if i == 0 else "theory"))
    if checkpoint:
        out.extend(_cards(unit.get("grammar") or [], stage="theory"))
    return out


def _word_cards(words: list[dict]) -> list[dict]:
    cards = []
    seen = set()
    for w in words:
        if w["en"] in seen:
            continue
        seen.add(w["en"])
        cards.append({
            "kind": "word_card",
            "stage": "words",
            "en": w["en"],
            "ru": w["ru"],
            "ipa": w.get("ipa", ""),
            "image": w.get("image") or "",
            "teach_ru": w.get("teach_ru") or teach_line(w["en"], w.get("ru", "")),
            "speak": w["en"],
            "example_en": w.get("example_en", w["en"]),
            "example_ru": w.get("example_ru", w["ru"]),
        })
    return cards


def _phrase_cards(phrases: list[dict]) -> list[dict]:
    cards = []
    seen: set[str] = set()
    for p in phrases:
        en = (p.get("en") or "").strip()
        if not en or en.lower() in seen:
            continue
        seen.add(en.lower())
        cards.append({
            "kind": "phrase_card",
            "stage": "words",
            "en": en,
            "ru": p.get("ru") or "",
            "speak": en,
            "foxi_line": "Теперь целая фраза. Слушай и скажи как я.",
        })
        if len(cards) >= 3:
            break
    return cards


def _decorate(built: list[dict], oral: bool) -> list[dict]:
    """Реплики и позы Фокси — одинаково для урока, экзамена и повторения."""
    stage_lines = FOXI_STAGE_ORAL if oral else FOXI_STAGE
    for it in built:
        if it.get("foxi_line"):
            it["foxi_ru"] = it["foxi_line"]
        else:
            stage = it.get("stage")
            if stage in stage_lines:
                it["foxi_ru"] = stage_lines[stage]
            else:
                it["foxi_ru"] = FOXI.get(it["kind"], "Я с тобой. Давай дальше.")
        it["foxi_pose"] = pose_for_item(it)
    return built


def build_checkpoint_items(unit_id: str, seed: int | None = None) -> list[dict]:
    """Экзамен юнита: только задания по всем словам и фразам, без новой теории."""
    unit = catalog.get_unit(unit_id)
    words = list(unit["words"])
    phrases = list(unit["phrases"])
    oral = unit.get("book") == "starter-oral"
    rng = random.Random(seed if seed is not None else 1000)
    drills: list[dict] = []
    if oral:
        drills.extend(_mcq_phrase(words, 4, rng))
        drills.extend(_listen(words, 3, rng, hear_en=True))
        drills.extend(_type_listen(words, 2, rng))
        drills.append(_match_phrase(words, min(6, len(words)), rng))
        drills.extend(_tap(phrases, 3, rng))
        drills.extend(_fill(phrases, words, 2, rng))
    else:
        drills.extend(_mcq(words, 4, rng, prompt="en", options="ru"))
        drills.extend(_mcq(words, 3, rng, prompt="ru", options="en"))
        drills.extend(_type_en(words, 3, rng))
        drills.append(_match(words, min(6, len(words)), rng))
        drills.extend(_listen(words, 2, rng))
        drills.extend(_tap(phrases, 2, rng))
        drills.extend(_fill(phrases, words, 2, rng))
    rng.shuffle(drills)
    exam = drills[:config.CHECKPOINT_ITEMS]
    for it in exam:
        it["stage"] = "practice"
    return _decorate(exam, oral)


def _options_for(word: dict, pool: list[dict], key: str, rng: random.Random) -> list[str]:
    distractors = [w[key] for w in pool if w[key] != word[key]]
    take = min(OPTIONS - 1, len(distractors))
    opts = (rng.sample(distractors, take) if take else []) + [word[key]]
    rng.shuffle(opts)
    return opts


def _review_item(word: dict, pool: list[dict], rng: random.Random, mode: str) -> dict:
    base = {
        "en": word["en"], "ru": word["ru"], "ipa": word.get("ipa", ""),
        "example_en": word.get("example_en", ""), "example_ru": word.get("example_ru", ""),
    }
    if mode == "type_en":
        return {**base, "kind": "type_en", "prompt": word["ru"],
                "speak": word["en"], "correct_text": word["en"]}
    if mode == "mcq_ru_en":
        opts = _options_for(word, pool, "en", rng)
        return {**base, "kind": "mcq_ru_en", "prompt": word["ru"], "options": opts,
                "correct_index": opts.index(word["en"]), "correct_text": word["en"]}
    if mode == "mcq_en_ru":
        opts = _options_for(word, pool, "ru", rng)
        return {**base, "kind": "mcq_en_ru", "prompt": word["en"], "speak": word["en"],
                "image": word.get("image") or "", "options": opts,
                "correct_index": opts.index(word["ru"]), "correct_text": word["ru"]}
    opts = _options_for(word, pool, "en", rng)
    return {**base, "kind": "listen", "prompt": "Что сказал Foxy?", "speak": word["en"],
            "options": opts, "correct_index": opts.index(word["en"]),
            "correct_text": word["en"]}


# Слабое слово сначала узнаём на слух, крепкое — пишем сами.
REVIEW_LADDER = ("listen", "listen", "mcq_en_ru", "mcq_ru_en", "type_en", "type_en")


def build_review_items(due: list[dict], seed: int | None = None) -> list[dict]:
    """Задания на созревшие слова: формат зависит от того, насколько слово окрепло."""
    rng = random.Random(seed if seed is not None else 77)
    out: list[dict] = []
    for row in due:
        unit_id = row.get("unit_id") or ""
        try:
            unit = catalog.get_unit(unit_id)
        except KeyError:
            continue
        pool = unit["words"]
        word = next((w for w in pool if w["en"] == row.get("word_en")), None)
        if word is None or len(pool) < 2:
            continue
        strength = max(0, min(len(REVIEW_LADDER) - 1, int(row.get("strength") or 0)))
        item = _review_item(word, pool, rng, REVIEW_LADDER[strength])
        item["stage"] = "practice"
        item["home_unit"] = unit_id
        out.append(item)
    return _decorate(out, oral=False)


def build_lesson_items(unit_id: str, lesson_n: int, *, checkpoint: bool = False,
                       seed: int | None = None) -> list[dict]:
    if checkpoint:
        return build_checkpoint_items(unit_id, seed=seed)
    unit = catalog.get_unit(unit_id)
    lesson = catalog.get_lesson(unit_id, lesson_n)
    words = list((lesson or {}).get("words") or unit["words"])
    phrases = list((lesson or {}).get("phrases") or unit["phrases"])
    oral = unit.get("book") == "starter-oral" or (lesson or {}).get("mode") == "oral"
    base = seed if seed is not None else lesson_n * 17
    rng = random.Random(base)
    head = _theory_head(unit, unit_id, lesson_n, checkpoint)
    gallery = [] if checkpoint else _word_cards(words) + _phrase_cards(phrases)
    listen_n = 4 if oral else (3 if checkpoint else 2)
    listen = _listen(words, listen_n, rng, hear_en=oral)
    for it in listen:
        it["stage"] = "listen"
    drills: list[dict] = []
    if oral:
        drills.extend(_mcq_phrase(words, 4, rng))
        drills.extend(_type_listen(words, 2, rng))
        drills.append(_match_phrase(words, min(6, len(words)), rng))
        drills.extend(_tap(phrases, 4, rng))
        drills.extend(_fill(phrases, words, 3, rng))
        for it in drills:
            if it["kind"] == "tap_build":
                it["prompt"] = "Собери фразу Foxy"
                it["speak"] = it.get("en") or ""
            if it["kind"] == "fill_blank":
                it["hint_ru"] = ""
    else:
        drills.extend(_mcq(words, 3 if not checkpoint else 5, rng, prompt="en", options="ru"))
        drills.extend(_mcq(words, 3, rng, prompt="ru", options="en"))
        drills.extend(_type_en(words, 3, rng))
        drills.append(_match(words, min(6, len(words)), rng))
        drills.extend(_tap(phrases, 2, rng))
        drills.extend(_fill(phrases, words, 2, rng))
    for it in drills:
        it["stage"] = "practice"
    if not checkpoint:
        rng.shuffle(drills)
    wrap_card = {
        "title_ru": "Что мы сделали",
        "body_ru": (
            "Ты слушал учителя Фокси, повторял фразы и сделал задания. "
            "Скажи дома одну английскую фразу с урока. Завтра продолжим."
            if oral else lesson_theory.WRAP["body_ru"]
        ),
        "visual_id": "wrap",
        "example_en": "",
        "example_ru": "",
        "foxi_line": "Урок окончен. Я горжусь, что ты говорил вслух.",
    } if oral else lesson_theory.wrap()
    tail = _cards([wrap_card], stage="wrap")
    return _decorate(head + gallery + listen + drills + tail, oral)


def public_item(index: int, item: dict) -> dict:
    kind = item["kind"]
    base = {"index": index, "kind": kind, "foxi_ru": item.get("foxi_ru", ""), "foxi_pose": item.get("foxi_pose", "wave")}
    if kind == "explain":
        return {
            **base,
            "stage": item.get("stage", "theory"),
            "title_ru": item["title_ru"],
            "body_ru": item["body_ru"],
            "visual_id": item.get("visual_id", ""),
            "example_en": item.get("example_en", ""),
            "example_ru": item.get("example_ru", ""),
            "steps": item.get("steps") or [],
            "gpc": item.get("gpc", ""),
            "sound": item.get("sound", ""),
            "speak_sound": item.get("speak_sound", ""),
            "speak": item.get("speak", ""),
            "audio": item.get("audio", ""),
            "image": item.get("image", ""),
        }
    if kind == "word_card":
        return {
            **base,
            "stage": "words",
            "en": item["en"],
            "ru": item["ru"],
            "ipa": item.get("ipa", ""),
            "image": item.get("image", ""),
            "teach_ru": item.get("teach_ru", ""),
            "speak": item.get("speak") or item["en"],
            "example_en": item.get("example_en", ""),
            "example_ru": item.get("example_ru", ""),
        }
    if kind == "phrase_card":
        return {
            **base,
            "stage": "words",
            "en": item["en"],
            "ru": item.get("ru", ""),
            "speak": item.get("speak") or item["en"],
        }
    if kind in ("mcq_en_ru", "mcq_ru_en", "listen", "fill_blank"):
        out = {**base, "stage": item.get("stage", "practice"), "options": item["options"]}
        if item.get("image"):
            out["image"] = item["image"]
        if kind == "listen":
            out["prompt"] = item.get("prompt") or "Послушай слово"
            out["speak"] = item.get("speak") or item["en"]
            if item.get("ipa"):
                out["ipa"] = item["ipa"]
        else:
            out["prompt"] = item["prompt"]
            if item.get("ipa"):
                out["ipa"] = item["ipa"]
            if kind == "fill_blank":
                out["hint_ru"] = item.get("hint_ru", "")
            if kind == "mcq_en_ru" and item.get("en"):
                out["speak"] = item["en"]
        return out
    if kind in ("type_en",):
        return {
            **base,
            "stage": item.get("stage", "practice"),
            "prompt": item["prompt"],
            "ipa": item.get("ipa", ""),
            "speak": item.get("speak") or "",
        }
    if kind == "tap_build":
        return {
            **base,
            "stage": item.get("stage", "practice"),
            "prompt": item["prompt"],
            "bank": item["bank"],
            "speak": item.get("speak") or item.get("en") or "",
        }
    return {**base, "stage": item.get("stage", "practice"), "left": item["left"], "right": item["right"]}


def signature(item: dict) -> str:
    """Устойчивый отпечаток задания: одна ошибка ребёнка — одна запись в mistakes.

    Формулировки перемешиваются от урока к уроку, поэтому сравниваем не JSON,
    а смысл: тип задания + слово или фраза, на которых ребёнок споткнулся.
    """
    kind = (item.get("kind") or "").strip()
    if kind == "match":
        pairs = item.get("pairs") or []
        tail = ",".join(sorted(_norm(p.get("en") or "") for p in pairs))
    else:
        tail = _norm(item.get("en") or item.get("correct_text") or item.get("prompt") or "")
    return f"{kind}:{tail}"


def grade(item: dict, value: dict) -> bool:
    kind = item["kind"]
    if kind in ("explain", "word_card", "phrase_card"):
        return True
    if kind in ("mcq_en_ru", "mcq_ru_en", "listen", "fill_blank"):
        return int(value.get("choice", -1)) == item["correct_index"]
    if kind == "type_en":
        return _norm(str(value.get("text", ""))) == _norm(item["correct_text"])
    if kind == "match":
        expected = {p["en"]: p["ru"] for p in item["pairs"]}
        got = value.get("matches") or {}
        if set(got) != set(expected):
            return False
        return all(_norm(got[k]) == _norm(v) for k, v in expected.items())
    if kind == "tap_build":
        got = value.get("tokens") or []
        return list(got) == list(item["tokens_correct"])
    return False


def leak_correct(item: dict) -> dict:
    kind = item["kind"]
    if kind in ("mcq_en_ru", "mcq_ru_en", "listen", "fill_blank"):
        return {"correct_index": item["correct_index"], "correct_text": item.get("correct_text", "")}
    if kind == "type_en":
        return {"correct_text": item["correct_text"]}
    if kind == "match":
        return {"pairs": item["pairs"]}
    if kind == "tap_build":
        return {"tokens_correct": item["tokens_correct"]}
    return {}
