from datetime import date

from app.lk.learning_engine import (
    INTERVALS_DAYS,
    SkillState,
    apply_answer,
    choose_task_type,
    make_task,
)


def test_correct_answer_advances_only_the_tested_skill_and_uses_interval():
    state = SkillState()

    result = apply_answer(state, skill="listening", correct=True, today=date(2026, 11, 10))

    assert result.state.listening == 1
    assert result.state.recall == 0
    assert result.next_review == date(2026, 11, 11)
    assert result.retry is False
    assert INTERVALS_DAYS == (1, 1, 3, 7, 14, 30)


def test_wrong_answer_does_not_go_below_zero_and_requires_retry():
    state = SkillState(recall=3)

    result = apply_answer(state, skill="recall", correct=False, today=date(2026, 11, 10))

    assert result.state.recall == 2
    assert result.next_review == date(2026, 11, 10)
    assert result.retry is True


def test_task_type_follows_weakest_skill_before_new_content():
    state = SkillState(recognition=4, listening=1, recall=3, spelling=0, usage=2)

    assert choose_task_type(state, has_image=True, has_example=True) == "spell"


def test_task_has_no_duplicate_or_confusable_options():
    task = make_task(
        task_type="translation",
        word_id=7,
        prompt="кошка",
        correct="cat",
        options=["cat", "dog", "cat", "kitten", "apple"],
        confusable={"cat", "kitten"},
    )

    assert task.options == ("cat", "dog", "apple")
    assert task.correct_index == 0
