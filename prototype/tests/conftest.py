"""Тесты импортируют генераторы страниц напрямую — им нужен prototype/ в sys.path."""
import os
import sys

PROTOTYPE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROTOTYPE_DIR not in sys.path:
    sys.path.insert(0, PROTOTYPE_DIR)
