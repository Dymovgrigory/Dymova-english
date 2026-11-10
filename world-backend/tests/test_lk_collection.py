from app.lk.collection import STARTER_CARDS, unlocked_cards


def test_first_lesson_unlocks_starter_card_once():
    cards = unlocked_cards({"lessons": 1, "learned_words": 0, "perfect_lessons": 0, "streak_days": 0})

    assert STARTER_CARDS[0]["id"] in cards


def test_word_milestones_and_perfect_lesson_unlock_distinct_cards():
    cards = unlocked_cards({"lessons": 3, "learned_words": 25, "perfect_lessons": 1, "streak_days": 7})

    assert {"word-scout-25", "perfect-lesson", "week-streak"}.issubset(cards)
    assert len(cards) == len(set(cards))


def test_unmet_milestones_do_not_unlock_cards():
    cards = unlocked_cards({"lessons": 0, "learned_words": 4, "perfect_lessons": 0, "streak_days": 2})

    assert cards == []
