"""DataLoader: round-trip & delimiter tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from scribe.core import DataLoadError
from scribe.util.loader import DataLoader


def _csv(path: Path, delimiter: str) -> None:
    path.write_text(f"a{delimiter}b\n1{delimiter}2\n3{delimiter}4\n")


@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(delim=st.sampled_from([",", "|", ";", "\t"]))
def test_csv_delimiters(tmp_path: Path, delim: str) -> None:
    """Any single-character delimiter round-trips to list[dict]."""
    csv = tmp_path / "file.csv"
    _csv(csv, delim)
    rows: list[dict[str, Any]] = DataLoader.load(csv, delimiter=delim)  # type: ignore[assignment]
    assert len(rows) == 2 and rows[0]["a"] == 1


def test_dataframe_return(tmp_path: Path) -> None:
    """as_records=False returns a DataFrame."""
    csv = tmp_path / "f.csv"
    _csv(csv, ",")
    df: pd.DataFrame = DataLoader.load(csv, as_records=False)
    assert df.shape == (2, 2)


def _write_yaml(path: Path) -> None:
    path.write_text("a: 1\nb: 2\n")  # minimal, valid YAML


def _write_json(path: Path) -> None:
    path.write_text(json.dumps({"a": 1, "b": 2}))  # minimal, valid JSON


def _write_csv(path: Path, delimiter: str = ",") -> None:
    path.write_text(f"x{delimiter}y\n1{delimiter}2\n")


def test_unsupported_extension(tmp_path: Path) -> None:
    """Loading a *.txt* file raises *ValueError* (line 65)."""
    bad = tmp_path / "foo.txt"
    bad.write_text("dummy")
    with pytest.raises(ValueError):
        DataLoader.load(bad)


def test_file_not_found(tmp_path: Path) -> None:
    """Loading a missing file raises *FileNotFoundError* (line 65)."""
    bad = tmp_path / "foo.txt"
    with pytest.raises(FileNotFoundError):
        DataLoader.load(bad)


def test_yaml_structured_branch(tmp_path: Path) -> None:
    """Valid YAML hits structured path and returns a dict (line 71)."""
    yml = tmp_path / "cfg.yaml"
    _write_yaml(yml)
    data = DataLoader.load(yml)
    assert isinstance(data, dict) and data["a"] == 1


def test_json_structured_branch(tmp_path: Path) -> None:
    """Valid YAML hits structured path and returns a dict (line 71)."""
    jsn = tmp_path / "cfg.json"
    _write_json(jsn)
    data = DataLoader.load(jsn)
    assert isinstance(data, dict) and data["a"] == 1


def test_invalid_delimiter_length(tmp_path: Path) -> None:
    """Delimiter longer than 1 char triggers _LoaderConfig validator (181)."""
    csv = tmp_path / "d.csv"
    _write_csv(csv)
    with pytest.raises(ValueError, match="single character"):
        DataLoader.load(csv, delimiter="||")  # invalid length


def test_negative_excel_sheet_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sheet index < 0 also fails the validator (184)."""
    xl = tmp_path / "tbl.xlsx"
    xl.touch()
    with pytest.raises(ValueError, match="must be ≥ 0"):
        DataLoader.load(xl, sheet_name=-1, delimiter=",")


def test_tabular_read_error_raises_dataloaderror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulate pandas read failure → ensure DataLoadError is raised."""
    csv = tmp_path / "boom.csv"
    _write_csv(csv)

    def boom(*_a: Any, **_kw: Any) -> None:
        raise pd.errors.ParserError("parse fail")

    monkeypatch.setattr(pd, "read_csv", boom)

    with pytest.raises(DataLoadError):
        DataLoader.load(csv)
