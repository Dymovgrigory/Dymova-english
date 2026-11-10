from app.lk.learning.core import Challenge, grade


def test_choice_challenge_is_graded_by_server():
    challenge = Challenge(
        id="g1", kind="grammar_choice", prompt="She ___ happy.",
        options=("is", "are", "am"), answer_index=0,
    )

    assert grade(challenge, {"index": 0}).correct is True
    assert grade(challenge, {"index": 1}).correct is False


def test_reading_true_false_and_text_answers_are_supported():
    true_false = Challenge(id="r1", kind="read_true_false", prompt="The cat is black.", answer_bool=True)
    text = Challenge(id="r2", kind="write", prompt="Type the word.", accepted=("school",))

    assert grade(true_false, {"value": True}).correct is True
    assert grade(text, {"text": "School"}).correct is True


def test_speaking_requires_target_word_in_transcript():
    challenge = Challenge(id="s1", kind="speak", prompt="Say cat", accepted=("cat",))

    assert grade(challenge, {"transcript": "cat"}).correct is True
    assert grade(challenge, {"transcript": "dog"}).correct is False
