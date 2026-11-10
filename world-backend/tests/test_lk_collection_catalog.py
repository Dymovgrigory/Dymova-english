from collections import Counter

from app.lk.learning.collection_catalog import CARDS, catalog, unlocked


def test_collection_catalog_has_ten_collections_of_ten_cards():
    counts = Counter(card.collection_id for card in CARDS)

    assert len(CARDS) == 100
    assert len(counts) == 10
    assert set(counts.values()) == {10}
    assert len({card.id for card in CARDS}) == 100


def test_collection_cards_have_stable_assets_and_progressive_unlocks():
    assert all(card.asset.startswith("/collection/") and card.asset.endswith(".webp") for card in CARDS)
    assert unlocked(points=1) == ["foxinburg-legends-01"]
    assert unlocked(words=3) == ["first-steps-01", "first-steps-02", "first-steps-03"]
