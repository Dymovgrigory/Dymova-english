"""Полный путь: 1 класс (устная линия) + phonics."""
from .phonics_course import COURSE as PHONICS_COURSE, tokenize_en
from .starter_course import COURSE as STARTER_COURSE

COURSE = STARTER_COURSE + PHONICS_COURSE

__all__ = ["COURSE", "tokenize_en"]
