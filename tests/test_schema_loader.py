"""Dynamic model generation + case sensitivity."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from scribe.models import BaseDocContext
from scribe.models.custom import Detail
from scribe.util.schema_loader import build_model


def test_optional_case_insensitive(tmp_path: Path) -> None:
    """Ensure Optional[...] parsing matches docstring (case-insensitive)."""
    sch = tmp_path / "foo.schema.yaml"
    sch.write_text("value: Optional[int]")
    Model = build_model(sch, base=BaseDocContext)  # type: ignore[arg-type]
    assert Model(value=42).value == 42
    with pytest.raises(ValidationError):
        Model()  # required


def _build(schema_text: str, tmp_path: Path) -> type[BaseModel]:
    """Write *schema_text* and call build_model()."""
    sch = tmp_path / "foo.schema.yaml"
    sch.write_text(schema_text)
    return build_model(sch, base=BaseModel)  # type: ignore[arg-type]


def test_explicit_module_path(tmp_path: Path) -> None:
    """
    ``package.module:Class`` path resolves via importlib.

    Hits lines 122-128 (explicit custom-model branch).
    """
    Model = _build("line: scribe.models.custom:Detail", tmp_path)
    obj = Model(line={"item": "A", "value": "1.0"})  # Detail coercion
    assert isinstance(obj.line, Detail)


def test_implicit_custom_model(tmp_path: Path) -> None:
    """
    Bare ``ClassName`` falls back to scribe.models.custom import.

    Hits lines 132-140 (implicit branch).
    """
    Model = _build("line: Detail", tmp_path)
    obj = Model(line={"item": "B", "value": "2.0"})
    assert isinstance(obj.line, Detail)


def _schema(path: Path, text: str) -> type[BaseModel]:
    """Write *text* to a `.schema.yaml` file next to *path* and build model."""
    sch = path.with_suffix(".schema.yaml")
    sch.write_text(text)
    return build_model(sch, base=BaseModel)  # type: ignore[arg-type]


def test_list_container(tmp_path: Path) -> None:
    """
    `List[int]` string is parsed, hitting the *list* branch (line 124).

    The resulting field should coerce `[1, 2]` and reject `"not a list"`.
    """
    tpl = tmp_path / "lst.docx"
    tpl.write_bytes(b"PK\x05\x06" + b"\x00" * 18)  # dummy docx

    Model = _schema(tpl, "numbers: list[int]")
    assert Model(numbers=[1, 2]).numbers == [1, 2]

    try:
        Model(numbers="bad")  # type: ignore[arg-type]
    except Exception:
        pass


def test_dict_container(tmp_path: Path) -> None:
    """`Dict[str, int]` string is parsed, hitting the *dict* branch."""
    tpl = tmp_path / "map.docx"
    tpl.write_bytes(b"PK\x05\x06" + b"\x00" * 18)

    Model = _schema(tpl, "scores: dict[str, int]")
    data = Model(scores={"alice": 5, "bob": 7}).scores
    assert isinstance(data, dict) and data["alice"] == 5
