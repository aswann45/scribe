"""
Public re-export hub for the project's Pydantic *data models*.

Why this file exists
--------------------
Other packages (e.g., ``scribe.core`` and the CLI) frequently need several
model classes.  Importing each symbol from its defining sub-module quickly
becomes verbose:

>>> from scribe.models.context import BaseDocContext
>>> from scribe.models.templates import TemplateConfig, RichTextStyle

Instead, this ``__init__`` file re-exports the *most-common* classes so callers
can write concise, uniform imports:

>>> from scribe.models import BaseDocContext, TemplateConfig, RichTextStyle

Re-exported API
---------------
* :class:`BaseDocContext` - permissive parent for template contexts
* :class:`ConditionalRichText`, :class:`RichTextStyle` - rich-text DSL
* :class:`TemplateConfig`, :class:`TemplateOption` - per-template metadata

The list is enforced by ``__all__`` to prevent **accidental namespace
pollution** and to make ``from scribe.models import *`` predictable.

Notes
-----
* Adding a new model? Import it here **and** append its name to
  :pydata:`__all__` so downstream code can access it via the top-level
  ``scribe.models`` namespace.
"""

from .context import BaseDocContext
from .templates import (
    ConditionalRichText,
    RichTextStyle,
    TemplateConfig,
    TemplateOption,
)

__all__ = [
    "BaseDocContext",
    "ConditionalRichText",
    "RichTextStyle",
    "TemplateConfig",
    "TemplateOption",
]
