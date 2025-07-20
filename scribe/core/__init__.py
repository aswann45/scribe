"""
Public façade that stitches together services required for generation pipeline.

The sub-packages earlier in the import graph are intentionally lightweight
(loader, schema validation, rich-text generator, template discovery).  This
``core`` namespace groups their **highest-level entry points** so external
code—CLI commands, notebooks, or future REST handlers—can import everything
they need from **one place**::

    from scribe.core import (
        get_settings,  # Cached AppSettings
        make_context,  # Validate raw payloads via side-car schemas
        generate_docx,  # Run the full render pipeline
        TemplateFinder,  # Scan template roots on disk
        TemplateNotFoundError,  # Typed exception helpers
        DataLoadError,
        RenderError,
    )

Re-exported API
---------------
See the explicit :pydata:`__all__` list below for the canonical, stable
symbols exposed by this top-level package.  Anything **not** present there
should be considered internal and subject to change without notice.
"""

from .context_factory import make_context
from .exceptions import (
    ConfigError,
    DataLoadError,
    RenderError,
    ScribeError,
    TemplateNotFoundError,
)
from .generator import generate_docx
from .settings import AppSettings, get_settings
from .template_finder import TemplateFinder

__all__ = [
    "AppSettings",
    "ConfigError",
    "DataLoadError",
    "RenderError",
    "ScribeError",
    "TemplateFinder",
    "TemplateNotFoundError",
    "generate_docx",
    "get_settings",
    "make_context",
]
