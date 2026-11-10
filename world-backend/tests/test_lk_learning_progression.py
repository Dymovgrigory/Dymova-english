from app.lk.learning.progression import add_points, rank_for, summary
from app.world.db import reset_for_tests


def test_rank_starts_as_guest():
    assert rank_for(0)["title"] == "Гость Фоксинбурга"


def test_points_and_rank_are_idempotent(tmp_path):
    reset_for_tests(str(tmp_path / "points.sqlite"))

    add_points("crm:1", "lesson-1", "pre-a1.family", 50)
    add_points("crm:1", "lesson-1", "pre-a1.family", 50)

    result = summary("crm:1")
    assert result["points"] == 50
    assert result["title"] == "Ученик"
