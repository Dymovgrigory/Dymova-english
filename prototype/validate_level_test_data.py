#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Structural validation for level_test_data.json. Run before every build."""
import json
import os
from collections import Counter

DIR = os.path.dirname(os.path.abspath(__file__))
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


def main():
    path = os.path.join(DIR, "level_test_data.json")
    data = json.load(open(path, encoding="utf-8"))

    assert len(data) == 24, f"expected 24 questions, got {len(data)}"

    counts = Counter(item["level"] for item in data)
    for level in LEVELS:
        assert counts[level] == 4, f"expected 4 questions for level {level}, got {counts[level]}"
    assert set(counts.keys()) == set(LEVELS), f"unexpected levels: {set(counts.keys()) - set(LEVELS)}"

    for i, item in enumerate(data):
        assert set(item.keys()) == {"level", "question", "options", "correct"}, \
            f"item {i} has unexpected keys: {item.keys()}"
        assert isinstance(item["question"], str) and item["question"].strip(), f"item {i} has empty question"
        assert isinstance(item["options"], list) and len(item["options"]) >= 2, \
            f"item {i} needs at least 2 options"
        assert isinstance(item["correct"], int) and 0 <= item["correct"] < len(item["options"]), \
            f"item {i} has invalid correct index {item['correct']}"

    print(f"OK: {len(data)} questions, levels {dict(counts)}")


if __name__ == "__main__":
    main()
