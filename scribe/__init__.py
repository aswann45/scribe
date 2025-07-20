"""
Top-level API for ``scribe``.

Aggregate re-exports that let downstream code pull the **most-common public
symbols** from a single namespace, instead of reaching into the deeper
sub-packages:

* Core runtime helpers
  ``TemplateFinder``, ``generate_docx``, ``make_context``
* Data-validation & rich-text DSL
  ``BaseDocContext``, ``RichTextStyle``, ``ConditionalRichText``
* Configuration models
  ``TemplateConfig``, ``TemplateOption``
* Utility helpers
  ``DataLoader``, ``build_model``

With this layout users can write::

    from scribe import TemplateFinder, DataLoader, generate_docx

rather than several longer import statements.

The public API surface is **pinned** by :pydata:`__all__`; anything not listed
there should be considered *internal* and subject to change without notice.  A
new symbol becomes part of the stable contract only after being added to this
list.
"""

from .core import TemplateFinder, generate_docx, make_context
from .models import (
    BaseDocContext,
    ConditionalRichText,
    RichTextStyle,
    TemplateConfig,
    TemplateOption,
)
from .util import DataLoader, build_model

__all__ = [
    "BaseDocContext",
    "ConditionalRichText",
    "DataLoader",
    "RichTextStyle",
    "TemplateConfig",
    "TemplateFinder",
    "TemplateOption",
    "build_model",
    "generate_docx",
    "make_context",
]
