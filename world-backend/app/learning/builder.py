"""Сборка сессии урока: какой узел → какие задания и в каком порядке.

Сессия детерминирована по seed. Полоса книги (starter/junior) задаёт набор типов,
линия чтения — какие слова уже можно дать читать. В обычные уроки подмешиваются
атомы прошлых модулей, у которых наступил срок повторения.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from . import challenges as ch
from . import mastery, phonics
from .challenges import Challenge
from .content import Atom, Course, GrammarItem, Module, Node, Phrase, Word
from .errors import Conflict, NotFound

WORD_TYPES = {
    "starter": ("listen_pick_image", "image_pick_word", "read_word_pick_image", "translate_pick", "spell_tiles", "speak"),
    "junior": ("listen_pick_image", "image_pick_word", "translate_pick", "spell_tiles", "type_word", "speak"),
}
PHRASE_TYPES = {
    "starter": ("translate_pick", "build_phrase", "read_phrase_pick_image", "speak"),
    "junior": ("translate_pick", "build_phrase", "listen_build", "speak"),
}
STARTER_PHRASE_MAX_WORDS = 4
MAX_SPEAK = 2
MAX_SAME_TYPE_RUN = 3
DUE_MIX = 3
REVIEW_SIZE = 15
TEST_SIZE = 15
GRAMMAR_PICKS = 6
GRAMMAR_PHRASES = 3
PHONICS_READ_WORDS = 3
PHONICS_SPELL_WORDS = 2
PHONICS_READ_PHRASES = 2
PHRASES_IN_WORDS_LESSON = 2  # хвост урока слов: пары фраз модуля, чтобы урок был не только про слова
PRACTICE_SIZE = 12
PRACTICE_MIN = 5
TRIAL_SIZE = 5  # испытание дня: ровно 5 слов на время


@dataclass
class SessionPlan:
    node_id: str
    kind: str
    challenges: list[Challenge]


class _Context:
    """Всё, что нужно фабрикам заданий для атомов одного модуля."""

    def __init__(self, course: Course, module: Module, node_id: str, rng: random.Random, speak_budget: list[int]):
        self.course = course
        self.module = module
        self.band = module.band
        self.rng = rng
        self.speak_budget = speak_budget  # общий счётчик на всю сессию
        self.pool = course.word_pool(module.id)
        self.phrase_pool = course.phrase_pool(module.id)
        self.inventory = course.grapheme_inventory()
        self.known = set(course.known_graphemes(node_id))
        self.trick = course.trick_words(module.id)

    def graded(self, atom: Atom, exclude: set[str] | frozenset[str] = frozenset()) -> Challenge | None:
        if isinstance(atom, GrammarItem):
            return ch.grammar_pick(atom, self.rng)
        types = list(WORD_TYPES[self.band] if isinstance(atom, Word) else PHRASE_TYPES[self.band])
        self.rng.shuffle(types)
        for challenge_type in types:
            if challenge_type in exclude:
                continue
            challenge = self.make(challenge_type, atom)
            if challenge is not None:
                if challenge_type == "speak":
                    self.speak_budget[0] -= 1
                return challenge
        return None

    def make(self, challenge_type: str, atom: Word | Phrase) -> Challenge | None:
        rng = self.rng
        if challenge_type == "speak":
            return ch.speak(atom) if self.speak_budget[0] > 0 else None
        direction = rng.choice(("en_ru", "ru_en"))
        if isinstance(atom, Word):
            if challenge_type == "listen_pick_image":
                return ch.listen_pick_image(atom, self.pool, rng)
            if challenge_type == "image_pick_word":
                return ch.image_pick_word(atom, self.pool, rng)
            if challenge_type == "read_word_pick_image":
                return ch.read_word_pick_image(atom, self.pool, rng, self.known, self.inventory)
            if challenge_type == "translate_pick":
                return ch.translate_pick(atom, [w.en for w in self.pool], [w.ru for w in self.pool], rng, direction)
            if challenge_type == "spell_tiles":
                return ch.spell_tiles(atom, rng)
            if challenge_type == "type_word":
                return ch.type_word(atom)
            return None
        if challenge_type == "translate_pick":
            pool = self.phrase_pool
            return ch.translate_pick(atom, [p.en for p in pool], [p.ru for p in pool], rng, direction)
        if challenge_type in ("build_phrase", "listen_build"):
            if self.band == "starter" and len(ch.phrase_tiles(atom.en)) > STARTER_PHRASE_MAX_WORDS:
                return None
            factory = ch.build_phrase if challenge_type == "build_phrase" else ch.listen_build
            return factory(atom, [w.en for w in self.pool], rng)
        if challenge_type == "read_phrase_pick_image":
            return ch.read_phrase_pick_image(atom, self.phrase_pool, rng, self.known, self.inventory, self.trick)
        return None


def _module_atoms(module: Module) -> list[Atom]:
    return [*module.words, *module.phrases, *(item for g in module.grammar for item in g.items)]


def _words_session(ctx: _Context, node: Node) -> list[Challenge]:
    words = [ctx.course.atom(word_id)[1] for word_id in node.word_ids]
    per_word = 3 if len(words) <= 5 else 2
    first: list[Challenge] = []
    later: list[Challenge] = []
    for word in words:
        first.append(ch.teach_word(word))
        used: set[str] = set()
        for attempt in range(per_word):
            challenge = ctx.graded(word, exclude=used)
            if challenge is None:
                continue
            used.add(challenge.type)
            (first if attempt == 0 else later).append(challenge)
    ctx.rng.shuffle(later)
    items = first + later
    pairs = ch.match_pairs(words, ctx.rng, "audio_image" if ctx.band == "starter" else "en_ru")
    if pairs is not None:
        items.append(pairs)
    # Фразы модуля в хвосте урока: ребёнок сразу собирает из новых слов живую речь.
    phrases = list(ctx.module.phrases)
    ctx.rng.shuffle(phrases)
    for phrase in phrases[:PHRASES_IN_WORDS_LESSON]:
        challenge = ctx.graded(phrase)
        if challenge is not None:
            items.append(challenge)
    return items


def _phonics_session(ctx: _Context, node: Node) -> list[Challenge]:
    course, rng = ctx.course, ctx.rng
    graphemes = [course.grapheme(g) for g in node.grapheme_ids]
    grapheme_pool = [g for m in course.modules_up_to(ctx.module.id) for g in m.graphemes]
    items: list[Challenge] = []
    for grapheme in graphemes:
        items.append(ch.teach_grapheme(grapheme))
        for factory in (ch.letter_sound, ch.sound_letter):
            challenge = factory(grapheme, grapheme_pool, rng)
            if challenge is not None:
                items.append(challenge)
    decodable = [w for w in ctx.pool if not w.trick and phonics.readable(w.en, ctx.known, ctx.inventory)]
    rng.shuffle(decodable)
    for word in decodable[:PHONICS_READ_WORDS]:
        challenge = ch.blend_sounds(word, ctx.pool, rng, ctx.known, ctx.inventory)
        if challenge is not None:
            items.append(challenge)
    for word in decodable[PHONICS_READ_WORDS: 2 * PHONICS_READ_WORDS] or decodable[:PHONICS_READ_WORDS]:
        challenge = ch.read_word_pick_image(word, ctx.pool, rng, ctx.known, ctx.inventory)
        if challenge is not None:
            items.append(challenge)
    for word in decodable[:PHONICS_SPELL_WORDS]:
        challenge = ch.spell_tiles(word, rng)
        if challenge is not None:
            items.append(challenge)
    if course.book(ctx.module.book).grade >= 2:
        phrases = list(ctx.phrase_pool)
        rng.shuffle(phrases)
        added = 0
        for phrase in phrases:
            challenge = ch.read_phrase_pick_image(phrase, ctx.phrase_pool, rng, ctx.known, ctx.inventory, ctx.trick)
            if challenge is not None:
                items.append(challenge)
                added += 1
            if added == PHONICS_READ_PHRASES:
                break
    return items


def _grammar_session(ctx: _Context, node: Node) -> list[Challenge]:
    grammar = ctx.course.grammar(node.grammar_id or "")
    graded: list[Challenge] = [ch.grammar_pick(item, ctx.rng) for item in grammar.items[:GRAMMAR_PICKS]]
    phrases = [p for p in ctx.module.phrases if p.grammar_id == grammar.id][:GRAMMAR_PHRASES]
    for phrase in phrases:
        for challenge_type in ("build_phrase", "translate_pick"):
            challenge = ctx.make(challenge_type, phrase)
            if challenge is not None:
                graded.append(challenge)
    ctx.rng.shuffle(graded)
    return [ch.teach_rule(grammar), *graded]


def _mixed_session(ctx: _Context, atoms: list[Atom], size: int) -> list[Challenge]:
    """Оцениваемые задания по кругу атомов; каждый атом — разными типами."""
    items: list[Challenge] = []
    used: dict[str, set[str]] = {}
    for position in range(len(atoms) * 6):
        if len(items) == size or not atoms:
            break
        atom = atoms[position % len(atoms)]
        challenge = ctx.graded(atom, exclude=used.setdefault(atom.id, set()))
        if challenge is not None:
            used[atom.id].add(challenge.type)
            items.append(challenge)
    return items


def _review_atoms(ctx: _Context, player_id: int | None) -> list[Atom]:
    atoms = _module_atoms(ctx.module)
    ctx.rng.shuffle(atoms)
    if player_id is None:
        return atoms
    by_id = {a.id: a for a in atoms}
    return [by_id[atom_id] for atom_id in mastery.weakest(player_id, list(by_id), len(by_id))]


def _mix_due(course: Course, items: list[Challenge], player_id: int, module: Module, rng: random.Random,
             speak_budget: list[int]) -> list[Challenge]:
    own = {a.id for a in _module_atoms(module)}
    due = mastery.due_atoms(player_id, limit=DUE_MIX, exclude=own)
    for atom_id in due:
        try:
            atom_module, atom = course.atom(atom_id)
        except NotFound:  # контент мог измениться после записи силы
            continue
        ctx = _Context(course, atom_module, atom_module.nodes[-1].id, rng, speak_budget)
        challenge = ctx.graded(atom, exclude={"speak"})
        if challenge is not None:
            items.insert(rng.randint(len(items) // 2, len(items)), challenge)
    return items


def _valid(sequence: list[Challenge], remaining: list[Challenge]) -> bool:
    """Ограничения раскладки: teach раньше задания на атом, атом не подряд, тип не больше 3 подряд."""
    pending_teach = {c.atom_id for c in remaining if not c.graded}
    taught_later: set[str] = set()
    for position in range(len(sequence) - 1, -1, -1):
        item = sequence[position]
        if not item.graded:
            taught_later.add(item.atom_id)
        elif item.atom_id and (item.atom_id in taught_later or item.atom_id in pending_teach):
            return False
    for position, item in enumerate(sequence):
        if position:
            previous = sequence[position - 1]
            if item.graded and previous.graded and item.atom_id and item.atom_id == previous.atom_id:
                return False
        if position >= MAX_SAME_TYPE_RUN:
            window = sequence[position - MAX_SAME_TYPE_RUN: position + 1]
            if all(c.type == item.type for c in window):
                return False
    return True


def _spread(items: list[Challenge]) -> list[Challenge]:
    """Сохраняет задуманный порядок; нарушителя ставит в ближайшее допустимое место."""
    remaining = list(items)
    placed: list[Challenge] = []
    while remaining:
        for position, candidate in enumerate(remaining):
            rest = remaining[:position] + remaining[position + 1:]
            if _valid(placed + [candidate], rest):
                placed.append(remaining.pop(position))
                break
        else:
            candidate = remaining.pop(0)
            for slot in range(len(placed), -1, -1):
                trial = placed[:slot] + [candidate] + placed[slot:]
                if _valid(trial, remaining):
                    placed = trial
                    break
            else:
                placed.append(candidate)
    return placed


def build_session(course: Course, node_id: str, *, player_id: int | None, seed: int, allow_speak: bool) -> SessionPlan:
    module, node = course.node(node_id)
    if node.kind == "chest":
        raise Conflict("chest_has_no_session")
    rng = random.Random(seed)
    speak_budget = [MAX_SPEAK if allow_speak else 0]
    ctx = _Context(course, module, node_id, rng, speak_budget)
    if node.kind == "words":
        items = _words_session(ctx, node)
    elif node.kind == "phonics":
        items = _phonics_session(ctx, node)
    elif node.kind == "grammar":
        items = _grammar_session(ctx, node)
    elif node.kind == "review":
        items = _mixed_session(ctx, _review_atoms(ctx, player_id), REVIEW_SIZE)
    else:
        atoms = _module_atoms(module)
        rng.shuffle(atoms)
        items = _mixed_session(ctx, atoms, TEST_SIZE)
    if node.kind != "module_test" and player_id is not None:
        items = _mix_due(course, items, player_id, module, rng, speak_budget)
    return SessionPlan(node_id, node.kind, _spread(items))


def build_practice(course: Course, player_id: int, *, seed: int, allow_speak: bool) -> SessionPlan:
    return _build_drill(course, player_id, seed=seed, allow_speak=allow_speak,
                        size=PRACTICE_SIZE, min_size=PRACTICE_MIN, words_only=False, node="practice")


def build_trial(course: Course, player_id: int, *, seed: int) -> SessionPlan:
    """Испытание дня: 5 слов на время. Только слова — фразы и грамматика не подходят под лимит."""
    return _build_drill(course, player_id, seed=seed, allow_speak=False,
                        size=TRIAL_SIZE, min_size=TRIAL_SIZE, words_only=True, node="trial")


def _build_drill(course: Course, player_id: int, *, seed: int, allow_speak: bool,
                 size: int, min_size: int, words_only: bool, node: str) -> SessionPlan:
    rng = random.Random(seed)
    word_ids = {w.id for m in course.modules for w in m.words} if words_only else None
    atom_ids = mastery.due_atoms(player_id, limit=size * 4)
    atom_ids += [a for a in mastery.weakest_seen(player_id, size * 4) if a not in atom_ids]
    if word_ids is not None:
        atom_ids = [a for a in atom_ids if a in word_ids]
    speak_budget = [MAX_SPEAK if allow_speak else 0]
    items: list[Challenge] = []
    for atom_id in atom_ids[:size]:
        try:
            module, atom = course.atom(atom_id)
        except NotFound:
            continue
        ctx = _Context(course, module, module.nodes[-1].id, rng, speak_budget)
        challenge = ctx.graded(atom)
        if challenge is not None:
            items.append(challenge)
    if len(items) < min_size:
        raise Conflict("nothing_to_practice")
    rng.shuffle(items)
    return SessionPlan(node, node, _spread(items))
