"""Schema loader utilities.

Utility helpers that **turn a template-side YAML schema into a real
Pydantic model** at runtime.  The feature lets non-developers add or modify
template-specific validation rules without touching Python code.

A ``*.schema.yaml`` lives next to a ``.docx`` template and maps each
placeholder name to a type string:

```yaml
client_name: str
report_date: date
total: Decimal
lines: List[custom:LineItem]  # custom model reference
'''

At render-time the loader:

parses the YAML via :pyfunc:load_schema;

converts every type string into an actual Python / typing object via
:pyfunc:_resolve_type; and

calls :pyfunc:build_model (a thin wrapper around
:pyfunc:pydantic.create_model) to yield a dynamically generated
subclass of the project's :pyclass:BaseDocContext.

The generated model is then used by :pymod:scribe.context_factory to
validate the raw payload and coerce primitive types (e.g. strings → date)
before reaching :pymod:scribe.generator.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, create_model

__all__: list[str] = [
    "build_model",
]

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
_PRIMITIVES: Mapping[str, Any] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "date": date,
    "datetime": datetime,
    "Decimal": Decimal,
}

_LIST_RE = re.compile(r"^list\[(.+)]$")
_DICT_RE = re.compile(r"^dict\[(.+), (.+)]$")  # simplified: only Dict[str, T]
_OPT_RE = re.compile(r"^optional\[(.+)]$")


def _resolve_type(type_str: str) -> Any:
    """
    Convert a YAML type string into an *actual* Python type.

    The supported grammar is intentionally small yet expressive:

    * **Primitive aliases** - ``str``, ``int``, ``float``, ``bool``,
      ``date``, ``datetime``, ``Decimal``.
    * **Container forms** - ``List[T]`` / ``Dict[str, T]`` /
      ``Optional[T]`` (case-insensitive; square brackets required).
    * **Custom models**

      * ``package.module:ClassName`` ⇒ imported via
        :pyfunc:`importlib.import_module`.
      * Bare ``ClassName`` ⇒ looked up in
        :pyfile:`scribe/models/custom.py` for convenience.

    Parameters
    ----------
    type_str
        A single type expression extracted from the YAML schema file.

    Returns
    -------
    Any
        The resolved Python type object suitable for use in
        :pyfunc:`pydantic.create_model`.

    Raises
    ------
    ImportError
        If a *custom* model path cannot be imported.
    AttributeError
        If the requested class cannot be found in the target module.

    Notes
    -----
    * Container matching is case-insensitive (``list[Str]`` equals
      ``List[str]``).
    * Nested containers are allowed, e.g. ``List[Dict[str, Decimal]]``.
    """
    type_str = type_str.strip()
    low = type_str.lower()

    # primitives
    if low in _PRIMITIVES:
        return _PRIMITIVES[low]

    # Optional
    m = _OPT_RE.match(low)
    if m:
        return Optional[_resolve_type(m.group(1))]  # noqa: UP007

    # list
    m = _LIST_RE.match(low)
    if m:
        return list[_resolve_type(m.group(1))]  # type: ignore[misc]

    # dict
    m = _DICT_RE.match(low)
    if m:
        return dict[str, _resolve_type(m.group(2))]  # type: ignore[misc]

    # Custom model path "package.module:Class"
    if ":" in type_str:
        mod_name, cls_name = type_str.split(":", 1)
        module = importlib.import_module(mod_name)
        return getattr(module, cls_name)

    # Fallback: assume same-package custom model "scribe.models.custom:Type"
    from scribe.models import custom  # local import to avoid circular deps

    return getattr(custom, type_str)


def load_schema(path: Path) -> dict[str, Any] | dict[str, tuple[str, Any]]:
    """
    Parse a ``*.schema.yaml`` into a *field → type* mapping.

    Parameters
    ----------
    path
        Path object pointing to the YAML schema file.

    Returns
    -------
    dict[str, Any]
        A dictionary where keys are placeholder names and values are the
        concrete Python types returned by :pyfunc:`_resolve_type`.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    yaml.YAMLError
        If the YAML content cannot be parsed.
    """
    with path.open("r") as fh:
        raw: dict[str, str] = yaml.safe_load(fh)
    return {name: _resolve_type(t_str) for name, t_str in raw.items()}


def build_model(
    schema_path: Path, *, base: type[BaseModel]
) -> type[BaseModel]:
    """
    Generate a Pydantic model from a template-side YAML schema.

    Parameters
    ----------
    schema_path
        Absolute path to the ``*.schema.yaml`` file.
    base
        Base class to inherit from - typically
        :pyclass:`scribe.models.contexts.BaseDocContext`.  Allows the
        generated model to share common config (e.g. ``extra="forbid"``).

    Returns
    -------
    type[BaseModel]
        A brand-new subclass named ``<template>Ctx`` where ``<template>``
        equals ``schema_path.stem``.

    Notes
    -----
    * The model is created *once per render invocation*; you may memoise
      results in higher-level callers if the micro-cost matters.
    * All fields are marked *required* (``...`` sentinel).  Default values
      can be expressed in YAML with the tuple form:
      ``field_name: [int, 0]`` but that is currently out of scope.
    """
    raw_fields: dict[str, Any] | dict[str, tuple[str, Any]] = load_schema(
        schema_path
    )  # {name: type}
    # convert to the (type, Ellipsis) tuple form expected by create_model
    fields: dict[str, Any] | dict[str, tuple[str, Any]] = {
        name: (typ, ...) for name, typ in raw_fields.items()
    }

    return create_model(
        schema_path.stem.replace(".schema", "") + "Ctx",  # ← model name
        __base__=base,  # ← keyword, not positional
        **fields,  # ← field definitions
    )
