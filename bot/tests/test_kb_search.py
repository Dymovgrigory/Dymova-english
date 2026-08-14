"""Качество поиска по базе знаний.

Промпт запрещает выдумывать факты, поэтому ответ ровно настолько хорош,
насколько точно найден документ. Раньше все совпавшие слова весили
одинаково, и запрос «Кто у вас педагоги?» находил «У вас есть носитель
языка?» — по слову «вас». Здесь проверяется, что редкое слово весит больше
частого, а совпадение в заголовке — больше совпадения в тексте.
"""
from __future__ import annotations

from app.knowledge.kb import Document, KnowledgeBase, _tokens, get_kb


def _titles(query: str, limit: int = 3) -> list[str]:
    return [doc.title for doc in get_kb().search(query, limit=limit)]


def test_pronouns_do_not_drive_the_search():
    """«Кто у вас педагоги?» — вопрос про команду, а не про слово «вас»."""
    docs = get_kb().search("Кто у вас педагоги?", limit=3)
    assert docs[0].category == "team"


def test_function_words_are_dropped():
    assert "вас" not in _tokens("Кто у вас педагоги?")
    assert "педагог" in _tokens("Кто у вас педагоги?")


def test_rare_word_outweighs_common_one():
    kb = KnowledgeBase()
    common = kb._weights().get("заняти", 0)
    rare = kb._weights().get("рассрочк", 0)
    assert rare > common > 0


def test_unknown_word_is_weighted_high():
    """Слово, которого нет в базе, — причина не найти ответ, а не мелочь."""
    kb = KnowledgeBase()
    weights = kb._weights()
    assert kb._weight_of("квантов", weights) >= max(weights.values())


def test_title_match_beats_body_match():
    kb = KnowledgeBase()
    kb.documents = []
    kb._idf = {}
    kb._add("faq", "Рассрочка и оплата частями", "Условия оплаты.")
    kb._add("faq", "Расписание занятий", "Есть рассрочка, спросите администратора.")
    top = kb.search("рассрочка", limit=2)[0]
    assert top.title == "Рассрочка и оплата частями"


def test_score_is_higher_for_a_full_match():
    kb = get_kb()
    exact = kb.search_scored("рассрочка", limit=1)[0][0]
    vague = kb.search_scored("расскажите что-нибудь про занятия", limit=1)[0][0]
    assert exact > vague


def test_empty_query_finds_nothing():
    assert get_kb().search_scored("   ") == []


def test_live_documents_reset_the_weights():
    """Синхронизация с сайта меняет корпус — веса обязаны пересчитаться."""
    kb = KnowledgeBase()
    kb._weights()
    doc = Document(category="live", title="Новая акция", text="Скидка 20% в сентябре")
    doc.tokens = set(_tokens("Новая акция Скидка 20% в сентябре"))
    doc.title_tokens = set(_tokens("Новая акция"))
    kb.set_live_documents([doc])
    assert "сентябр" in kb._weights()
