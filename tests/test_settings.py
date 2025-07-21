"""AppSettings env override precedence."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from scribe.core.settings import AppSettings


def test_env_var_override(tmp_path: Path, monkeypatch: Any) -> None:
    """SCRIBE_OUTPUT_DIR supersedes YAML default."""
    os.environ["SCRIBE_OUTPUT_DIR"] = str(tmp_path)
    settings = AppSettings()
    assert settings.output_dir == tmp_path
