"""Fail-fast audit for the LMS learning and collection content."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.lk.learning.catalog import catalog
from app.lk.learning.collection_catalog import catalog as collection_catalog
from app.lk.learning.tasks import tasks_for


def audit(public_root: Path) -> list[str]:
    errors: list[str] = []
    units = catalog()
    if {unit.level for unit in units} != {"pre-a1", "a1", "a2", "b1"}:
        errors.append("catalog must cover Pre-A1, A1, A2 and B1")
    required_skills = {"vocabulary", "grammar", "reading", "listening", "writing", "speaking"}
    offered_skills = {skill for unit in units for skill in unit.skills}
    if not required_skills <= offered_skills:
        errors.append(f"missing catalog skills: {sorted(required_skills - offered_skills)}")
    for unit in units:
        tasks = tasks_for(unit.id)
        if len(tasks) < 4:
            errors.append(f"{unit.id}: fewer than 4 tasks")
        if not {task.kind for task in tasks} & {"grammar_choice", "read_choice", "read_true_false"}:
            errors.append(f"{unit.id}: no grammar/reading task")
    cards = collection_catalog()
    if len(cards) != 100 or len({card["collection_id"] for card in cards}) != 10:
        errors.append("collection must contain 10 collections and 100 cards")
    for card in cards:
        path = public_root / card["asset"].lstrip("/")
        if not path.is_file():
            errors.append(f"missing asset: {card['asset']}")
    return errors


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2] / "lk" / "public"
    problems = audit(root)
    if problems:
        print("LMS CONTENT AUDIT: FAIL")
        print("\n".join(f"- {problem}" for problem in problems))
        sys.exit(1)
    print("LMS CONTENT AUDIT: PASS (4 CEFR bands, 7 units, 100 collection cards, assets present)")
