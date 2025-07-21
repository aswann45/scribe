"""Schema-driven context validation for ``make_context``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from scribe.core.context_factory import make_context
from scribe.core.exceptions import ConfigError
from scribe.models.context import BaseDocContext


def _write_schema(path: Path) -> None:
    """Create a minimal YAML schema next to *path*."""
    schema = path.with_suffix(".schema.yaml")
    schema.write_text("name: str\nage: int\n")


def _make_template(tmp_path: Path) -> Path:
    """Return a dummy docx file + schema."""
    template = tmp_path / "foo.docx"
    template.write_bytes(b"PK\x05\x06" + b"\x00" * 18)  # empty ZIP archive
    _write_schema(template)
    return template


def test_make_context_valid(tmp_path: Path) -> None:
    """Valid payload produces a *dynamic* subclass of BaseDocContext."""
    tpl = _make_template(tmp_path)
    ctx_obj = make_context(tpl, {"name": "Ada", "age": 42})
    assert isinstance(ctx_obj, BaseDocContext)
    # dynamic class name '<stem>Ctx'
    assert ctx_obj.__class__.__name__ == "fooCtx"


def test_make_context_returns_raw_data(tmp_path: Path) -> None:
    """Permissively return raw data when no schema is provided."""
    raw = {"name": "Ada", "age": 42}
    ctx = make_context(tmp_path, raw)
    assert ctx == raw


@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    extra_key=st.text(min_size=1).filter(lambda s: s not in {"name", "age"})
)
def test_make_context_invalid(extra_key: str, tmp_path: Path) -> None:
    """Any extra key triggers ConfigError (strict schema)."""
    tpl = _make_template(tmp_path)
    bad_payload: dict[str, Any] = {"name": "Ada", "age": 42, extra_key: 0}

    with pytest.raises(ConfigError):
        make_context(tpl, bad_payload, strict=True)
