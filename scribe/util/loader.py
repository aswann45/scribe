"""Data loading utilities.

A *single-responsibility* utility that ingests **structured** and **tabular**
files into Python objects that the rendering pipeline can consume.

Supported formats
-----------------
* **YAML**  (``.yaml`` | ``.yml``) → ``dict`` | ``list``
* **JSON**  (``.json``)             → ``dict`` | ``list``
* **CSV**   (``.csv``)              → ``list[dict]`` | ``pandas.DataFrame``
* **Excel** (``.xls`` | ``.xlsx``)  → ``list[dict]`` | ``pandas.DataFrame``

The caller decides—via the :pydata:`as_records` flag—whether tabular data
should be returned as a list-of-records (row dictionaries) or as a
:pyclass:`pandas.DataFrame` for advanced manipulation.

The loader never mutates the on-disk file.  Any parsing or validation errors
are wrapped in :pyclass:`scribe.core.exceptions.DataLoadError` so that the CLI
can present consistent messages and exit codes.
"""

from __future__ import annotations

import json
from collections.abc import Hashable
from pathlib import Path
from typing import Any, ClassVar, Literal, overload

import pandas as pd
import yaml
from pydantic import BaseModel, field_validator

from scribe.core.exceptions import DataLoadError

__all__ = ["DataLoader"]


class _LoaderConfig(BaseModel):
    """Runtime configuration for *tabular* file ingestion.

    This internal model exists solely to co-locate validation logic for the
    optional parameters accepted by :pymeth:`DataLoader.load`.  It is **not**
    part of the public API but keeps the main method lean and mypy-friendly.

    Attributes
    ----------
    as_records
        *True* → convert a :pyclass:`pandas.DataFrame` to
        ``list[dict]`` before returning.  Ignored for non-tabular files.
    sheet_name
        Excel-specific selector (index **or** sheet title).  ``None`` selects
        the *first* sheet.  Ignored for CSV.
    delimiter
        Single-character delimiter for CSV files.  Validation ensures the
        string length is exactly **1** to avoid ambiguous parsing behaviour.
    """

    as_records: bool = True  # True ➜ list[dict]; False ➜ pandas.DataFrame
    sheet_name: str | int | None = None  # Excel only; None = first sheet
    delimiter: str = ","

    @field_validator("sheet_name")
    def _sheet_name_ok(cls, v: Any) -> Any:
        if isinstance(v, int) and v < 0:
            raise ValueError("sheet_name index must be ≥ 0")
        return v

    @field_validator("delimiter")
    def _delimiter_one_char(cls, v: str) -> str:
        if len(v) != 1:
            raise ValueError("Delimiter must be a single character.")
        return v


class DataLoader:
    """Versatile loader for YAML, JSON, CSV, and Excel sources.

    The class is *stateless*—all user-visible behaviour is exposed via the
    :pymeth:`load` class-method.  Each call is independent and safe for
    concurrent use.

    Examples
    --------
    >>> from pathlib import Path
    >>> # YAML → dict
    >>> ctx = DataLoader.load(Path("data/example.yaml"))
    >>> # CSV → list[dict]
    >>> rows = DataLoader.load(Path("data/bulk.csv"))
    >>> # CSV → DataFrame (for Pandas power-users)
    >>> df = DataLoader.load(Path("data/bulk.csv"), as_records=False)
    >>> # Excel second sheet, pipe-delimited CSV
    >>> df2 = DataLoader.load(Path("tbl.xlsx"), sheet_name=1)
    >>> psv_rows = DataLoader.load(Path("tbl.psv"), delimiter="|")
    """

    _TABULAR: ClassVar = {".csv", ".xls", ".xlsx"}
    _STRUCTURED: ClassVar = {".yaml", ".yml", ".json"}
    _ALL_EXTS = _TABULAR | _STRUCTURED

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    @overload
    @classmethod
    def load(
        cls,
        path: Path,
        *,
        as_records: Literal[True] = True,
        sheet_name: str | int | None = None,
        delimiter: str = ",",
    ) -> dict[str, Any] | list[dict[str, Any]]: ...

    @overload
    @classmethod
    def load(
        cls,
        path: Path,
        *,
        as_records: Literal[False] = False,
        sheet_name: str | int | None = None,
        delimiter: str = ",",
    ) -> pd.DataFrame: ...

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        as_records: bool = True,
        sheet_name: str | int | None = None,
        delimiter: str = ",",
    ) -> Any:
        """Load *path* into a Python object.

        The return-type depends on both the **file extension** and the
        :pydata:`as_records` flag (for tabular files).

        Parameters
        ----------
        path
            Absolute or relative path on disk.  The loader does **not** accept
            file-like objects because format inference relies on the suffix.
        as_records
            *Tabular files only.*  When *True* (default), the returned value is
            a ``list[dict]``—ideal for Jinja template iteration.  When *False*,
            the loader returns a fully-typed :pyclass:`pandas.DataFrame`.
        sheet_name
            Excel-specific selector.  Accepts either *zero-based* integer index
            or *sheet title* string.  Ignored for all non-Excel inputs.
        delimiter
            Single character used to split CSV fields (default ``","``).  The
            value is validated via :pyclass:`_LoaderConfig`.

        Returns
        -------
        dict | list | pandas.DataFrame
            Parsed representation of the source file, shaped according to the
            combination of *extension* and :pydata:`as_records`.

        Raises
        ------
        FileNotFoundError
            When *path* does not exist on the filesystem.
        ValueError
            For unsupported extensions, or when validation detects an invalid
            configuration (e.g. multi-character delimiter).
        DataLoadError
            Wraps any lower-level exceptions raised by *pandas*, *yaml*, or
            *json* parsing routines to provide a project-specific error class.
        """
        cfg = _LoaderConfig(
            as_records=as_records, sheet_name=sheet_name, delimiter=delimiter
        )

        if not path.exists():
            raise FileNotFoundError(path)

        ext = path.suffix.lower()
        if ext not in cls._ALL_EXTS:
            raise ValueError(f"Unsupported file type: {ext}")

        if ext in cls._STRUCTURED:
            return cls._load_structured(path)
        return cls._load_tabular(path, cfg)

    # ------------------------------------------------------------------ #
    # — Private helpers —
    # ------------------------------------------------------------------ #
    @staticmethod
    def _load_structured(path: Path) -> dict[str, Any] | list[Any]:
        """Parse **structured** text (YAML / JSON) into Python objects.

        Parameters
        ----------
        path
            Source file ending in ``.yaml``, ``.yml``, or ``.json``.

        Returns
        -------
        dict | list
            Native Python representation.  The loader does not impose any
            shape constraints—the top-level node may be a mapping or a list.

        Raises
        ------
        DataLoadError
            Raised when underlying YAML/JSON libraries throw a parsing error
            or the file cannot be opened.
        """
        try:
            if path.suffix.lower() in {".yaml", ".yml"}:
                with path.open("r") as fh:
                    return yaml.safe_load(fh)  # type: ignore[no-any-return]
            with path.open("r") as fh:
                return json.load(fh)  # type: ignore[no-any-return]
        except Exception as exc:  # pragma: no cover
            raise DataLoadError(f"Failed reading {path}") from exc

    @staticmethod
    def _load_tabular(
        path: Path, cfg: _LoaderConfig
    ) -> list[dict[Hashable, Any]] | pd.DataFrame:
        """Read **tabular** data (CSV / Excel) and post-process.

        The heavy lifting is delegated to :pypkg:`pandas` readers.  Afterwards
        the dataframe is either returned as-is or converted into a
        ``list[dict]`` depending on :pydata:`cfg.as_records`.

        Parameters
        ----------
        path
            Path ending in ``.csv``, ``.xls``, or ``.xlsx``.
        cfg
            Validated runtime options produced by :class:`_LoaderConfig`.

        Returns
        -------
        list[dict[str, Any]] | pandas.DataFrame
            • ``list[dict]`` when ``cfg.as_records`` is *True*  (default)
            • :class:`pandas.DataFrame` when ``cfg.as_records`` is *False*

        Raises
        ------
        DataLoadError
            Wraps errors from :pyfunc:`pandas.read_csv` /
            :pyfunc:`pandas.read_excel`, such as parsing failures or missing
            sheets.
        """
        try:
            if path.suffix.lower() == ".csv":
                df = pd.read_csv(path, delimiter=cfg.delimiter)
            else:  # Excel (.xls / .xlsx)
                df = pd.read_excel(path, sheet_name=cfg.sheet_name or 0)
        except Exception as exc:  # pragma: no cover
            raise DataLoadError(f"Failed reading {path}") from exc

        return df.to_dict(orient="records") if cfg.as_records else df
