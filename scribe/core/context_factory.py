"""Utility for **creating a template-specific render context**.

The function :func:`make_context` receives raw data (loaded from YAML/JSON/CSV
by :pymod:`scribe.util.loader`) and a template path.  It decides whether to:

1. **Pass it through unchanged** when *no* side-car schema file exists, keeping
   the pipeline permissive for ad-hoc templates, **or**
2. **Generate** a Pydantic model on the fly when a matching
   ``*.schema.yaml``/``*.schema.yml`` file is found (see
   :pymod:`scribe.util.schema_loader`).  The raw data is validated against the
   generated model, giving strong guarantees that placeholders exist and types
   are coercible (e.g. strings → ``datetime.date``).

This logic centralises schema handling in one place so that both the CLI and
library code can share the same behaviour.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from scribe.core.exceptions import ConfigError
from scribe.models.context import BaseDocContext
from scribe.util.schema_loader import build_model

_SCHEMA_SUFFIXES = (".schema.yaml", ".schema.yml")
"""Tuple[str, str]: Accepted suffixes for side-car schema files."""


def make_context(
    template_path: Path,
    raw_data: Mapping[str, Any] | BaseModel,
    strict: bool = False,
) -> BaseModel | Mapping[str, Any]:
    """
    Produce a *validated* render context for a given template.

    The behaviour depends on whether a **side-car schema** is present:

    + ``<template>.schema.yaml`` or ``.schema.yml`` **exists**
      → Build a dynamic model via :func:`scribe.util.schema_loader.build_model`
      and return the result of ``Model.model_validate(raw_data)``.
    + No schema file found
      →  Return *raw_data* unchanged (permissive mode).

    Parameters
    ----------
    template_path :
        Absolute path (or project-relative) to the ``.docx`` template.
    raw_data :
        The data payload loaded by the caller.  May be

        * a *mapping* (``dict`` or ``pydantic-compatible`` mapping) or
        * an already-constructed :class:`pydantic.BaseModel`.
    strict:
        Whether to allow extra fields on the generated model.

    Returns
    -------
    BaseModel | Mapping[str, Any]
        * A **Pydantic model instance** when schema validation occurs.
          The concrete class is dynamically generated and inherits from
          :class:`scribe.models.context.BaseDocContext`.
        * The **original mapping** when no schema is present or when
          *raw_data* is already a model.

    Raises
    ------
    ConfigError
        If a schema file exists *but* the data fails validation or an
        unexpected exception occurs during dynamic model creation.
    """
    if isinstance(raw_data, BaseModel):
        return raw_data

    for suf in _SCHEMA_SUFFIXES:
        schema = template_path.with_suffix(suf)
        if schema.exists():
            try:
                if strict is True:

                    class StrictModel(BaseModel):
                        model_config = ConfigDict(extra="forbid")

                    Model = build_model(schema, base=StrictModel)
                    print("strict model")
                else:
                    Model = build_model(schema, base=BaseDocContext)
                    print("relaxed model")
                print("model:", Model.model_fields)
                return Model.model_validate(raw_data)
            except ValidationError as exc:
                raise ConfigError(
                    f"Schema validation failed for {schema}"
                ) from exc

    # no schema — permissive
    return raw_data
