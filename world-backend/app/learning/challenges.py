"""Типы заданий: из атома контента собираем то, что видит ученик, и эталон ответа.

Фабрика возвращает `None`, если задание к атому неприменимо (нет картинки, слово
ещё нельзя прочитать, не хватает дистракторов) — builder берёт другой тип.
Эталон (`solution`) живёт только на сервере; клиенту уходит `Challenge.public()`.
"""
from __future__ import annotations

import random
import re
from dataclasses import asdict, dataclass

from . import checker, phonics
from .checker import Verdict
from .content import Grammar, GrammarItem, Grapheme, Phrase, Word
from .errors import BadAnswer

OPTIONS = 3
PAIRS_MIN, PAIRS_MAX = 3, 5
EXTRA_TILES = 2
LETTERS = "abcdefghijklmnopqrstuvwxyz"
_SPELLABLE = re.compile(r"[a-z]{2,10}")
_TILE_WORD = re.compile(r"[A-Za-z']+")


@dataclass
class Challenge:
    type: str
    atom_id: str
    prompt: dict
    solution: dict
    graded: bool = True

    def public(self, index: int) -> dict:
        return {"index": index, "type": self.type, "atom_id": self.atom_id, "graded": self.graded, **self.prompt}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Challenge":
        return cls(**data)


def _choice(correct: str, candidates: list, rng: random.Random, count: int = OPTIONS):
    """Правильный вариант + уникальные дистракторы. None, если дистракторов мало."""
    distractors = [c for c in dict.fromkeys(candidates) if c != correct]
    if len(distractors) < count - 1:
        return None
    rng.shuffle(distractors)
    options = [correct, *distractors[: count - 1]]
    rng.shuffle(options)
    return options, options.index(correct)


def _choice_solution(index: int, display: str) -> dict:
    return {"kind": "choice", "index": index, "display": display}


def phrase_tiles(en: str) -> list[str]:
    return _TILE_WORD.findall(en)


def _image_choice(word: Word | Phrase, pool: list, rng: random.Random):
    if not word.image:
        return None
    images = [item.image for item in pool if item.image and item.en.lower() != word.en.lower()]
    return _choice(word.image, images, rng)


# --- карточки знакомства (не оцениваются) -------------------------------------------------

def teach_word(word: Word) -> Challenge:
    prompt = {"en": word.en, "ru": word.ru, "image": word.image, "audio": word.en}
    return Challenge("teach_word", word.id, prompt, {"kind": "none"}, graded=False)


def teach_rule(grammar: Grammar) -> Challenge:
    prompt = {
        "title_ru": grammar.title_ru,
        "rule_ru": grammar.rule_ru,
        "examples": [example.model_dump() for example in grammar.examples],
    }
    return Challenge("teach_rule", grammar.id, prompt, {"kind": "none"}, graded=False)


def teach_grapheme(grapheme: Grapheme) -> Challenge:
    prompt = {"grapheme": grapheme.grapheme, "sound_word": grapheme.sound_word, "audio": grapheme.sound_word}
    return Challenge("teach_grapheme", grapheme.id, prompt, {"kind": "none"}, graded=False)


# --- слова ---------------------------------------------------------------------------------

def listen_pick_image(word: Word, pool: list[Word], rng: random.Random) -> Challenge | None:
    picked = _image_choice(word, pool, rng)
    if picked is None:
        return None
    images, index = picked
    prompt = {"instruction_ru": "Послушай и выбери картинку", "audio": word.en,
              "options": [{"image": image} for image in images]}
    return Challenge("listen_pick_image", word.id, prompt, _choice_solution(index, word.en))


def image_pick_word(word: Word, pool: list[Word], rng: random.Random) -> Challenge | None:
    if not word.image:
        return None
    picked = _choice(word.en, [w.en for w in pool], rng)
    if picked is None:
        return None
    labels, index = picked
    prompt = {"instruction_ru": "Как это по-английски?", "image": word.image, "options": labels}
    return Challenge("image_pick_word", word.id, prompt, _choice_solution(index, word.en))


def translate_pick(atom: Word | Phrase, pool_en: list[str], pool_ru: list[str], rng: random.Random,
                   direction: str) -> Challenge | None:
    if direction == "en_ru":
        text, correct, candidates = atom.en, atom.ru, pool_ru
    else:
        text, correct, candidates = atom.ru, atom.en, pool_en
    picked = _choice(correct, candidates, rng)
    if picked is None:
        return None
    labels, index = picked
    prompt = {"instruction_ru": "Выбери перевод", "text": text, "direction": direction,
              "audio": atom.en if direction == "en_ru" else None, "options": labels}
    return Challenge("translate_pick", atom.id, prompt, _choice_solution(index, correct))


def match_pairs(words: list[Word], rng: random.Random, mode: str) -> Challenge | None:
    chosen = words[:PAIRS_MAX]
    if len(chosen) < PAIRS_MIN:
        return None
    if mode == "audio_image" and any(not w.image for w in chosen):
        mode = "en_ru"
    order = list(range(len(chosen)))
    rng.shuffle(order)
    left, right, pairs = [], [], []
    for i, word in enumerate(chosen):
        left_id, right_id = f"l{i}", f"r{order[i]}"
        pairs.append([left_id, right_id])
        if mode == "audio_image":
            left.append({"id": left_id, "audio": word.en})
            right.append({"id": right_id, "image": word.image})
        else:
            left.append({"id": left_id, "label": word.en})
            right.append({"id": right_id, "label": word.ru})
    rng.shuffle(left)
    rng.shuffle(right)
    prompt = {"instruction_ru": "Найди пары", "mode": mode, "left": left, "right": right}
    solution = {"kind": "pairs", "pairs": pairs, "display": ", ".join(f"{w.en} — {w.ru}" for w in chosen)}
    return Challenge("match_pairs", "", prompt, solution)


def spell_tiles(word: Word, rng: random.Random) -> Challenge | None:
    letters = list(word.en.lower())
    if not _SPELLABLE.fullmatch(word.en.lower()):
        return None
    extra = [letter for letter in LETTERS if letter not in letters]
    rng.shuffle(extra)
    tiles = letters + extra[:EXTRA_TILES]
    rng.shuffle(tiles)
    prompt = {"instruction_ru": "Собери слово из букв", "image": word.image, "audio": word.en,
              "ru": word.ru, "tiles": tiles}
    return Challenge("spell_tiles", word.id, prompt,
                     {"kind": "tiles", "joiner": "", "accepted": [word.en], "display": word.en})


def type_word(word: Word) -> Challenge:
    prompt = {"instruction_ru": "Напиши по-английски", "image": word.image, "audio": word.en, "ru": word.ru}
    return Challenge("type_word", word.id, prompt,
                     {"kind": "text", "accepted": [word.en, *word.accept_en], "display": word.en})


def speak(atom: Word | Phrase) -> Challenge:
    prompt = {"instruction_ru": "Скажи вслух", "text": atom.en, "audio": atom.en}
    return Challenge("speak", atom.id, prompt, {"kind": "speech", "target": atom.en, "display": atom.en})


# --- фразы и грамматика --------------------------------------------------------------------

def _phrase_builder(kind: str, phrase: Phrase, distractor_words: list[str], rng: random.Random) -> Challenge:
    words = phrase_tiles(phrase.en)
    used = {w.lower() for w in words}
    extra = [w for w in dict.fromkeys(distractor_words) if w.lower() not in used and " " not in w]
    rng.shuffle(extra)
    tiles = words + extra[:EXTRA_TILES]
    rng.shuffle(tiles)
    if kind == "build_phrase":
        prompt = {"instruction_ru": "Собери фразу", "ru": phrase.ru, "tiles": tiles}
    else:
        prompt = {"instruction_ru": "Послушай и собери фразу", "audio": phrase.en, "tiles": tiles}
    solution = {"kind": "tiles", "joiner": " ", "accepted": [phrase.en, *phrase.accept_en], "display": phrase.en}
    return Challenge(kind, phrase.id, prompt, solution)


def build_phrase(phrase: Phrase, distractor_words: list[str], rng: random.Random) -> Challenge:
    return _phrase_builder("build_phrase", phrase, distractor_words, rng)


def listen_build(phrase: Phrase, distractor_words: list[str], rng: random.Random) -> Challenge:
    return _phrase_builder("listen_build", phrase, distractor_words, rng)


def grammar_pick(item: GrammarItem, rng: random.Random) -> Challenge:
    order = list(range(len(item.options)))
    rng.shuffle(order)
    options = [item.options[i] for i in order]
    prompt = {"instruction_ru": "Выбери правильный вариант", "sentence": item.prompt_en, "ru": item.ru,
              "options": options}
    display = item.prompt_en.replace("___", item.options[item.answer])
    return Challenge("grammar_pick", item.id, prompt, _choice_solution(order.index(item.answer), display))


# --- чтение (полоса starter) ---------------------------------------------------------------

def letter_sound(grapheme: Grapheme, graphemes: list[Grapheme], rng: random.Random) -> Challenge | None:
    word = grapheme.sound_word.lower()
    candidates = [g.grapheme for g in graphemes if g.grapheme not in word]
    picked = _choice(grapheme.grapheme, candidates, rng)
    if picked is None:
        return None
    labels, index = picked
    prompt = {"instruction_ru": "Послушай слово. Какую букву ты слышишь?", "audio": grapheme.sound_word,
              "options": labels}
    return Challenge("letter_sound", grapheme.id, prompt, _choice_solution(index, grapheme.grapheme))


def sound_letter(grapheme: Grapheme, graphemes: list[Grapheme], rng: random.Random) -> Challenge | None:
    candidates = [g.sound_word for g in graphemes if grapheme.grapheme not in g.sound_word.lower()]
    picked = _choice(grapheme.sound_word, candidates, rng)
    if picked is None:
        return None
    words, index = picked
    prompt = {"instruction_ru": "В каком слове есть этот звук?", "grapheme": grapheme.grapheme,
              "options": [{"audio": w} for w in words]}
    return Challenge("sound_letter", grapheme.id, prompt, _choice_solution(index, grapheme.sound_word))


def blend_sounds(word: Word, pool: list[Word], rng: random.Random, known: set[str],
                 inventory: list[str]) -> Challenge | None:
    segments = phonics.readable(word.en, known, inventory)
    if segments is None:
        return None
    images = _image_choice(word, pool, rng)
    if images is not None:
        options: list = [{"image": image} for image in images[0]]
        index = images[1]
    else:
        picked = _choice(word.en, [w.en for w in pool if phonics.readable(w.en, known, inventory)], rng)
        if picked is None:
            return None
        options, index = picked
    prompt = {"instruction_ru": "Прочитай по звукам и найди слово", "segments": segments,
              "reveal_audio": word.en, "options": options}
    return Challenge("blend_sounds", word.id, prompt, _choice_solution(index, word.en))


def read_word_pick_image(word: Word, pool: list[Word], rng: random.Random, known: set[str],
                         inventory: list[str]) -> Challenge | None:
    if phonics.readable(word.en, known, inventory) is None:
        return None
    picked = _image_choice(word, pool, rng)
    if picked is None:
        return None
    images, index = picked
    prompt = {"instruction_ru": "Прочитай слово и выбери картинку", "text": word.en, "reveal_audio": word.en,
              "options": [{"image": image} for image in images]}
    return Challenge("read_word_pick_image", word.id, prompt, _choice_solution(index, word.en))


def read_phrase_pick_image(phrase: Phrase, phrases: list[Phrase], rng: random.Random, known: set[str],
                           inventory: list[str], trick_words: set[str]) -> Challenge | None:
    for token in phrase_tiles(phrase.en):
        if token.lower() not in trick_words and phonics.readable(token, known, inventory) is None:
            return None
    picked = _image_choice(phrase, phrases, rng)
    if picked is None:
        return None
    images, index = picked
    prompt = {"instruction_ru": "Прочитай фразу и выбери картинку", "text": phrase.en,
              "reveal_audio": phrase.en, "options": [{"image": image} for image in images]}
    return Challenge("read_phrase_pick_image", phrase.id, prompt, _choice_solution(index, phrase.en))


# --- проверка ------------------------------------------------------------------------------

def grade(challenge: Challenge, answer: dict) -> Verdict:
    solution = challenge.solution
    kind = solution["kind"]
    try:
        if kind == "choice":
            return checker.check_choice(int(answer["index"]), solution["index"])
        if kind == "text":
            return checker.check_text(str(answer["text"]), solution["accepted"], allow_typo=True)
        if kind == "tiles":
            joined = solution["joiner"].join(str(tile) for tile in answer["tiles"])
            return checker.check_text(joined, solution["accepted"], allow_typo=False)
        if kind == "pairs":
            return checker.check_pairs([list(p) for p in answer["pairs"]], solution["pairs"])
        if kind == "speech":
            return checker.check_speech(str(answer["transcript"]), solution["target"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BadAnswer(f"malformed answer for {challenge.type}") from exc
    raise BadAnswer(f"{challenge.type} is not graded")
