"""Пороги и уровни веток званий — чистая математика, без базы."""
from __future__ import annotations

import pytest

from app.castle import tracks


def test_five_tracks_with_five_levels_each():
    assert set(tracks.TRACKS) == {"lexicon", "yard", "nest", "glory", "stickers"}
    for track in tracks.TRACKS.values():
        assert len(track.thresholds) == 5
        assert len(track.level_titles) == 5
        assert list(track.thresholds) == sorted(track.thresholds)


@pytest.mark.parametrize(
    "value,expected",
    [(0, 0), (9, 0), (10, 1), (49, 1), (50, 2), (150, 3), (300, 4), (600, 5), (10_000, 5)],
)
def test_level_for_words(value, expected):
    assert tracks.level_for("lexicon", value) == expected


def test_level_reward_grows():
    assert [tracks.level_reward(level) for level in (1, 2, 3, 4, 5)] == [25, 50, 100, 200, 400]


def test_track_view_shows_next_goal():
    view = tracks.track_view("nest", 8)
    assert view["level"] == 2
    assert view["title_ru"] == tracks.TRACKS["nest"].level_titles[1]
    assert view["value"] == 8
    assert view["next_threshold"] == 21


def test_track_view_at_max_has_no_next_goal():
    view = tracks.track_view("stickers", 22)
    assert view["level"] == 5
    assert view["next_threshold"] is None
