"""Ошибки движка обучения v2. API переводит `status` в HTTP-код."""
from __future__ import annotations


class LearningError(Exception):
    status = 400


class NotFound(LearningError):
    status = 404


class Conflict(LearningError):
    status = 409


class Gone(LearningError):
    status = 410


class BadAnswer(LearningError):
    status = 422


class ProfileRequired(Conflict):
    def __init__(self) -> None:
        super().__init__("profile_required")
