"""Shared fixtures for bot test suite."""
import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _disable_registration(monkeypatch):
    """Disable registration gate for all tests by default.

    Tests that specifically test registration should override this
    by re-enabling it via monkeypatch.
    """
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRED", False)
