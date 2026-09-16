"""Контент тренажёра Spotlight: схемы, загрузка, индекс курса и инварианты.

Один JSON на модуль учебника: `<dir>/<book>/<module>.json`, метаданные книг —
`<dir>/books.json`. Невалидный контент не загружается (fail fast).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Union

from pydantic import BaseModel, Field, ValidationError, model_validator

from .checker import tokens
from .errors import NotFound

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "content" / "spotlight"

Band = Literal["starter", "junior"]
NodeKind = Literal["words", "phonics", "grammar", "chest", "review", "module_test"]

# Служебные слова, которые можно использовать во фразах без отдельного урока.
FUNCTION_WORDS = frozenset(
    """a an the i am is are you he she it we they my your his her its our their
    this that these those and or but in on at to of for with from up down yes no not
    what where who how when why can have has got do does me him us them there here
    let us will""".split()
)


class Book(BaseModel):
    id: str
    title: str
    grade: int
    cefr: str
    band: Band


class Word(BaseModel):
    id: str
    en: str
    ru: str
    accept_en: list[str] = []
    accept_ru: list[str] = []
    kind: Literal["noun", "verb", "adj", "other"] = "noun"
    image: str | None = None
    trick: bool = False


class Phrase(BaseModel):
    id: str
    en: str
    ru: str
    accept_en: list[str] = []
    accept_ru: list[str] = []
    word_ids: list[str] = Field(min_length=1)
    grammar_id: str | None = None
    image: str | None = None


class GrammarExample(BaseModel):
    en: str
    ru: str


class GrammarItem(BaseModel):
    id: str
    prompt_en: str
    options: list[str] = Field(min_length=2, max_length=4)
    answer: int
    ru: str

    @model_validator(mode="after")
    def _answer_fits(self) -> "GrammarItem":
        if "___" not in self.prompt_en:
            raise ValueError(f"{self.id}: prompt_en needs ___")
        if not 0 <= self.answer < len(self.options):
            raise ValueError(f"{self.id}: answer out of range")
        return self


class Grammar(BaseModel):
    id: str
    title_ru: str
    rule_ru: str
    examples: list[GrammarExample] = Field(min_length=1, max_length=3)
    items: list[GrammarItem] = Field(min_length=4)


class Grapheme(BaseModel):
    id: str
    grapheme: str = Field(pattern=r"^[a-z]{1,3}$")
    sound_word: str


class Node(BaseModel):
    id: str
    kind: NodeKind
    word_ids: list[str] = []
    grammar_id: str | None = None
    grapheme_ids: list[str] = []


class Module(BaseModel):
    id: str
    book: str
    order: int
    title_en: str
    title_ru: str
    band: Band
    words: list[Word]
    phrases: list[Phrase] = []
    grammar: list[Grammar] = []
    graphemes: list[Grapheme] = []
    nodes: list[Node] = Field(min_length=1)
    sources: list[str] = Field(min_length=1)


Atom = Union[Word, Phrase, GrammarItem]


class ContentError(ValueError):
    pass


class Course:
    def __init__(self, books: list[Book], modules: list[Module]) -> None:
        self.books = sorted(books, key=lambda b: b.grade)
        grades = {b.id: b.grade for b in self.books}
        self.modules = sorted(modules, key=lambda m: (grades.get(m.book, 99), m.order))
        self._books = {b.id: b for b in self.books}
        self._modules = {m.id: m for m in self.modules}
        self._atoms: dict[str, tuple[Module, Atom]] = {}
        self._nodes: dict[str, tuple[Module, Node]] = {}
        self._grammar: dict[str, Grammar] = {}
        self._graphemes: dict[str, Grapheme] = {}
        for module in self.modules:
            for word in module.words:
                self._atoms[word.id] = (module, word)
            for phrase in module.phrases:
                self._atoms[phrase.id] = (module, phrase)
            for grammar in module.grammar:
                self._grammar[grammar.id] = grammar
                for item in grammar.items:
                    self._atoms[item.id] = (module, item)
            for grapheme in module.graphemes:
                self._graphemes[grapheme.id] = grapheme
            for node in module.nodes:
                self._nodes[node.id] = (module, node)

    @staticmethod
    def _get(index: dict, key: str, label: str):
        try:
            return index[key]
        except KeyError:
            raise NotFound(f"{label} {key!r} not found") from None

    def book(self, book_id: str) -> Book:
        return self._get(self._books, book_id, "book")

    def module(self, module_id: str) -> Module:
        return self._get(self._modules, module_id, "module")

    def node(self, node_id: str) -> tuple[Module, Node]:
        return self._get(self._nodes, node_id, "node")

    def atom(self, atom_id: str) -> tuple[Module, Atom]:
        return self._get(self._atoms, atom_id, "atom")

    def grammar(self, grammar_id: str) -> Grammar:
        return self._get(self._grammar, grammar_id, "grammar")

    def grapheme(self, grapheme_id: str) -> Grapheme:
        return self._get(self._graphemes, grapheme_id, "grapheme")

    def modules_of(self, book_id: str) -> list[Module]:
        self.book(book_id)
        return [m for m in self.modules if m.book == book_id]

    def nodes_of(self, book_id: str) -> list[tuple[Module, Node]]:
        return [(m, n) for m in self.modules_of(book_id) for n in m.nodes]

    def modules_up_to(self, module_id: str) -> list[Module]:
        target = self.module(module_id)
        return self.modules[: self.modules.index(target) + 1]

    def _same_book_up_to(self, module_id: str) -> list[Module]:
        target = self.module(module_id)
        earlier = [m for m in self.modules_up_to(module_id) if m.book == target.book and m.id != module_id]
        return [target, *reversed(earlier)]

    def word_pool(self, module_id: str) -> list[Word]:
        """Слова для дистракторов: текущий модуль первым, затем прошлые модули той же книги."""
        return [w for m in self._same_book_up_to(module_id) for w in m.words]

    def phrase_pool(self, module_id: str) -> list[Phrase]:
        return [p for m in self._same_book_up_to(module_id) for p in m.phrases]

    def trick_words(self, module_id: str) -> set[str]:
        return {w.en.lower() for m in self.modules_up_to(module_id) for w in m.words if w.trick}

    def known_graphemes(self, node_id: str) -> list[str]:
        """Графемы, введённые phonics-узлами до этого узла включительно (по всему курсу)."""
        self.node(node_id)
        known: list[str] = []
        for module in self.modules:
            for node in module.nodes:
                if node.kind == "phonics":
                    known.extend(self.grapheme(g).grapheme for g in node.grapheme_ids)
                if node.id == node_id:
                    return list(dict.fromkeys(known))
        return list(dict.fromkeys(known))

    def grapheme_inventory(self) -> list[str]:
        return sorted({g.grapheme for m in self.modules for g in m.graphemes}, key=lambda g: (-len(g), g))


def validate(course: Course) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()

    def unique(item_id: str) -> None:
        if item_id in seen:
            errors.append(f"duplicate id {item_id}")
        seen.add(item_id)

    known_vocabulary: set[str] = set()
    book_ids = {b.id for b in course.books}
    for module in course.modules:
        unique(module.id)
        if module.book not in book_ids:
            errors.append(f"{module.id}: unknown book {module.book}")
            continue
        if course.book(module.book).band != module.band:
            errors.append(f"{module.id}: band differs from book")

        for word in module.words:
            unique(word.id)
        for phrase in module.phrases:
            unique(phrase.id)
        for grammar in module.grammar:
            unique(grammar.id)
            for item in grammar.items:
                unique(item.id)
        for grapheme in module.graphemes:
            unique(grapheme.id)
        for node in module.nodes:
            unique(node.id)

        word_ids = {w.id for w in module.words}
        grammar_ids = {g.id for g in module.grammar}
        grapheme_ids = {g.id for g in module.graphemes}
        words_in_nodes: set[str] = set()
        for node in module.nodes:
            for word_id in node.word_ids:
                if word_id not in word_ids:
                    errors.append(f"{node.id}: unknown word {word_id}")
            if node.kind == "words":
                if not node.word_ids:
                    errors.append(f"{node.id}: words node without word_ids")
                words_in_nodes.update(node.word_ids)
            if node.kind == "grammar":
                if node.grammar_id not in grammar_ids:
                    errors.append(f"{node.id}: unknown grammar {node.grammar_id}")
                elif sum(1 for p in module.phrases if p.grammar_id == node.grammar_id) < 2:
                    errors.append(f"{node.id}: grammar needs >=2 phrases")
            if node.kind == "phonics":
                if not node.grapheme_ids:
                    errors.append(f"{node.id}: phonics node without grapheme_ids")
                for grapheme_id in node.grapheme_ids:
                    if grapheme_id not in grapheme_ids:
                        errors.append(f"{node.id}: unknown grapheme {grapheme_id}")

        for word in module.words:
            if word.id not in words_in_nodes:
                errors.append(f"{word.id}: not in any words node")
        if module.nodes[-1].kind != "module_test" or sum(n.kind == "module_test" for n in module.nodes) != 1:
            errors.append(f"{module.id}: module_test must be the single last node")
        if module.band == "starter" and not any(n.kind == "phonics" for n in module.nodes):
            errors.append(f"{module.id}: starter module needs a phonics node")

        for word in module.words:
            known_vocabulary.update(tokens(word.en))
        for phrase in module.phrases:
            for word_id in phrase.word_ids:
                if word_id not in word_ids:
                    errors.append(f"{phrase.id}: unknown word {word_id}")
            if phrase.grammar_id and phrase.grammar_id not in grammar_ids:
                errors.append(f"{phrase.id}: unknown grammar {phrase.grammar_id}")
            for token in tokens(phrase.en):
                singular = token[:-1] if token.endswith("s") else token
                if token in FUNCTION_WORDS or token in known_vocabulary or singular in known_vocabulary:
                    continue
                errors.append(f"{phrase.id}: word '{token}' not taught yet")
    return errors


def load_course(directory: Path | str) -> Course:
    root = Path(directory)
    books_file = root / "books.json"
    if not books_file.exists():
        raise ContentError(f"{books_file} not found")
    try:
        books = [Book.model_validate(b) for b in json.loads(books_file.read_text(encoding="utf-8"))["books"]]
        modules = [
            Module.model_validate(json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(root.glob("*/*.json"))
        ]
    except (ValidationError, KeyError, json.JSONDecodeError) as exc:
        raise ContentError(str(exc)) from exc
    course = Course(books, modules)
    errors = validate(course)
    if errors:
        raise ContentError("\n".join(errors))
    return course


@lru_cache(maxsize=4)
def _cached(directory: str) -> Course:
    return load_course(directory)


def get_course() -> Course:
    return _cached(os.environ.get("LEARN_CONTENT_DIR", str(DEFAULT_DIR)))


def reset_cache() -> None:
    _cached.cache_clear()

