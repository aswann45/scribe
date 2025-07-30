"""Base context definitions used by the document-generation pipeline.

The principal class, :class:`BaseDocContext`, provides a *permissive* Pydantic
model that accepts **any** key/value pairs.  This loose contract lets each
DOCX template render with minimal boilerplate.  When a template needs stricter
validation, you can simply subclass :class:`BaseDocContext` and add concrete
fields; the rest of the system (loader → schema validation → generator) works
unchanged.

Examples
--------
Create a permissive context on-the-fly::

    ctx = BaseDocContext.model_validate({"foo": 1, "bar": "baz"})

Define a stricter variant for a specific template::

    class AnnualReportCtx(BaseDocContext):
        customer: str
        report_date: datetime.date
        revenue: Decimal
        model_config = ConfigDict(extra="forbid")

Any attempt to render an *AnnualReportCtx* with extra keys will then raise a
validation error long before the Jinja engine runs, surfacing problems early.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BaseDocContext(BaseModel):
    """Permissive Pydantic model for Jinja template contexts.

    Parameters
    ----------
    **data
        Arbitrary key-value pairs representing template placeholders and
        their corresponding values.

    Model behaviour
    ---------------
    * ``extra = "allow"`` — **all** unknown fields are accepted without
      validation; they are stored unchanged in the model's `__dict__`.
    * Type coercion still applies when you *do* declare fields in a
      subclass (e.g. strings → ``date``), so you can mix strict and loose
      placeholders seamlessly.

    Subclassing
    -----------
    Derive a concrete model when you need per-template validation::

        class CoverLetterCtx(BaseDocContext):
            recipient: str
            sender: str
            body: str
            model_config = ConfigDict(extra="forbid")

    Setting ``extra="forbid"`` on the subclass prevents typos or unexpected
    placeholders from silently passing through the pipeline.

    Notes
    -----
    * The class lives in **`scribe/models/context.py`** so that it can be
      imported by both runtime code and dynamically generated models
      (see :pymod:`scribe.util.schema_loader`).  Keeping it extremely
      lightweight avoids import-cycle pitfalls.
    """

    model_config = ConfigDict(extra="allow")  # accept any template vars
