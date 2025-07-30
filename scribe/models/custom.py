"""
Reusable, strongly-typed value objects shared across multiple templates.

These models allow YAML *schema* files to reference complex types without
having to embed their full definitions inline.  Any type declared here can be
used inside a ``*.schema.yaml`` via either notation::

    List[Detail]  # short form  (implicit module)
    scribe.models.custom: Detail  # explicit module path

Both resolve to :class:`Detail` at runtime via
:pyfunc:`scribe.util.schema_loader._resolve_type`.

Notes
-----
* Keep the module extremely lightweight—**no** heavy dependencies—so it loads
  quickly when dynamic models are generated.
* Additional models should inherit from :class:`pydantic.BaseModel` and follow
  the same import conventions shown below.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class Detail(BaseModel):
    """
    A single key-value line item used in many financial-style templates.

    Parameters
    ----------
    item : str
        Human-readable label (e.g., ``"Revenue"``, ``"Growth"``, ``"Total"``
        etc.).
    value : Decimal
        The numeric or currency value associated with *item*.  Using
        :class:`~decimal.Decimal` preserves precision when the document
        performs inline calculations or formatting.

    Example
    -------
    >>> Detail(item="Revenue", value=Decimal("1250000.50"))
    """

    item: str
    value: Decimal
