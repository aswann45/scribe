"""Global pytest fixtures shared across the test-suite."""

from __future__ import annotations

import pytest

from scribe.util.logger import setup as log_setup


@pytest.fixture(scope="session", autouse=True)
def _configure_logging() -> None:
    """Initialise colourised logs at DEBUG level for the test run."""
    log_setup(level="DEBUG", json_mode=False)
