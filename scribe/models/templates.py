"""Models to render data to Docx templates using RichText.

Typed building-blocks that describe **how each DOCX template should be
rendered**.  The models here capture three ideas:

1. :class:`RichTextStyle` - low-level font/colour attributes that map onto
   *docxtpl*'s ``RichText`` API.
2. :class:`RichTextPredicate` + :class:`ConditionalRichText` - a declarative
   *if-this-value-then-that-style* DSL that lets non-developers apply styles
   based on the *content* of a placeholder.
3. :class:`TemplateConfig` - top-level metadata (file path, output-naming
   rules, global options) consumed by the generator.

These models are referenced by **YAML config files** and by dynamic schema
loading, so keeping them in one module avoids circular imports.
"""

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TUnderline = Literal[
    "single",
    "double",
    "thick",
    "dotted",
    "dash",
    "dotDash",
    "dotDotDash",
    "wave",
]


class RichTextStyle(BaseModel):
    """
    Declarative styling options for a single placeholder.

    Parameters
    ----------
    bold, italic, subscript, superscript, strike : bool, optional
        Toggle Word's corresponding character formatting.
    underline : TUnderline | None, optional
        One of Word's named underline styles (``"single"``, ``"double"``,
        ``"thick"``, ``"dotted"``, etc.).  ``None`` ⇒ no underline.
    color, higlight : str | None, optional
        Six-digit **hex RGB** string *without* the ``"#"`` prefix,
        e.g. ``"FF0000"`` for red.  ``color`` sets font colour;
        ``higlight`` sets background highlight.
    size : int | None, optional
        Font size in **half-points** (``22`` → 11 pt).  ``None`` keeps the
        template's default size.
    font : str | None, optional
        Font family name as recognised by Word (e.g., ``"Calibri"``).
    style : str | None, optional
        Name of a predefined *Word* character style to apply.

    Notes
    -----
    * Extra attributes are **forbidden** to prevent silent typos
      (``model_config.extra = "forbid"``).
    * When multiple style attributes conflict, Word's precedence rules apply.
    """

    bold: bool = False
    italic: bool = False
    underline: TUnderline | None = Field(
        default=None,
        description="Underline style, e.g. 'single' or 'double'",
    )
    color: str | None = Field(
        default=None,
        description="Hex RGB without '#', e.g. 'FF0000' for red",
        pattern=r"^[0-9A-Fa-f]{6}$",
    )
    higlight: str | None = Field(
        default=None,
        description="Hex RGB without '#', e.g. 'FF0000' for red",
        pattern=r"^[0-9A-Fa-f]{6}$",
    )
    size: int | None = Field(
        default=None,
        description="Font size in half-points (22 ➜ 11 pt).",
        ge=1,
    )
    subscript: bool = False
    superscript: bool = False
    font: str | None = Field(default=None, description="Font name")
    strike: bool = False
    style: str | None = Field(
        default=None,
        description="Pre-defined Word style.",
    )

    model_config = ConfigDict(extra="forbid")


class RichTextPredicate(BaseModel):
    """
    Safe boolean logic for conditional formatting.

    Matching semantics
    ------------------
    * String tests are **case-insensitive**.
    * Only the **first** satisfied condition in a
      :class:`ConditionalRichText` list triggers a style.

    Parameters
    ----------
    equals, contains, regex : str | None
        Equality / substring / *re* search against the placeholder's
        *string* representation.
    gt, gte, lt, lte : float | None
        Numeric comparisons.  The placeholder value is coerced to
        ``float``; failures fall through to *no-match*.
    """

    equals: str | None = None
    contains: str | None = None
    regex: str | None = None
    gt: float | None = None
    gte: float | None = None
    lt: float | None = None
    lte: float | None = None

    @model_validator(mode="after")
    def _not_empty(cls, v: Any) -> Any:
        if not any(i is not None for i in v.__dict__.values()):
            raise ValueError("At least one operator is required")
        return v

    def matches(self, value: Any) -> bool:
        """Return *True* when **value** satisfies the predicate."""
        try:
            if (
                self.equals is not None
                and str(value).lower() == self.equals.lower()
            ):
                return True
            if (
                self.contains is not None
                and self.contains.lower() in str(value).lower()
            ):
                return True
            if self.regex is not None and re.search(self.regex, str(value)):
                return True

            num = float(value)  # may raise
            if self.gt is not None and num > self.gt:
                return True
            if self.gte is not None and num >= self.gte:
                return True
            if self.lt is not None and num < self.lt:
                return True
            if self.lte is not None and num <= self.lte:
                return True

        except (ValueError, TypeError):
            pass
        return False


class ConditionalRichText(BaseModel):
    """
    Pair a predicate with a style.

    Attributes
    ----------
    when : RichTextPredicate
        Condition that must return ``True`` for the style to apply.
    style : RichTextStyle
        The formatting to use when *when* matches.
    """

    when: RichTextPredicate
    style: RichTextStyle


class TemplateOption(BaseModel):
    """
    Per-template rendering flags.

    Parameters
    ----------
    date_format : str | None, optional
        ``strftime`` pattern used by helper filters inside Jinja templates.
    uppercase_names : bool, default ``False``
        Convenience switch for legacy templates that expect
        ``client_name`` in uppercase.
    richtext : dict[str, RichTextStyle | list[ConditionalRichText]]
        Mapping *placeholder → style definition(s)*.  Keys **must** match
        the Jinja variable names used in the DOCX template.

    Notes
    -----
    Extra keys are allowed so future options can be added without a
    breaking schema change.
    """

    # Example flags - add your own as needed
    date_format: str | None = None
    uppercase_names: bool = False
    richtext: dict[str, RichTextStyle | list[ConditionalRichText]] = Field(
        default_factory=dict,
        description=(
            "Map of placeholder names → RichTextStyle or list of "
            "ConditionalRichText. "
            "Keys must match variables used inside the Jinja template."
        ),
    )

    model_config = ConfigDict(extra="allow")  # allow future flags


class TemplateConfig(BaseModel):
    """
    Canonical metadata for a single template file.

    Parameters
    ----------
    name : str
        Logical identifier used by the CLI (e.g., ``"annual_report"``).
    path : pathlib.Path
        Absolute or project-relative path to the ``.docx`` template.
    output_naming : str
        Python *f-string* evaluated against the **render context**
        (e.g., ``"{client_name}_{report_date:%Y%m%d}.docx"``).
    options : TemplateOption, optional
        Rendering tweaks (see :class:`TemplateOption`).  Defaults to an
        **all-false / empty** instance when omitted.

    Example
    -------
    >>> TemplateConfig(
    ...     name="cover_letter",
    ...     path=Path("templates/cover_letter.docx"),
    ...     output_naming="{recipient}_cover_letter.docx",
    ... )
    """

    name: str
    path: Path
    output_naming: str = Field(
        ...,
        description=(
            "Python format string (f-string-style) evaluated against the "
            "render context - e.g. '{client_name}_report.docx'"
        ),
    )
    options: TemplateOption = TemplateOption()  # sensible defaults
