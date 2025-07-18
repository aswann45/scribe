# tests/conftest.py
import logging

import pytest

from scribe.util.logger import setup as log_setup


@pytest.fixture(autouse=True, scope="session")
def _logging():
    log_setup(level="DEBUG", json_mode=False)
    logging.getLogger("scribe").debug("Test log setup")
