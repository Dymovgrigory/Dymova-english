from app.lk.learning.catalog import catalog, available_units, unit


def test_catalog_contains_cambridge_bands_and_skill_mix():
    bands = {item.level for item in catalog()}

    assert {"pre-a1", "a1", "a2", "b1"}.issubset(bands)
    assert {"vocabulary", "grammar", "reading", "listening"}.issubset(
        {skill for item in catalog() for skill in item.skills}
    )


def test_units_are_stable_and_filterable_by_level_and_topic():
    selected = available_units(level="pre-a1", topic="family")

    assert selected
    assert all(item.level == "pre-a1" and item.topic == "family" for item in selected)
    assert unit(selected[0].id) == selected[0]
