"""
Convenience re-exports that surface commonly-used helpers from sub-modules.

* :class:`~scribe.util.loader.DataLoader` - multi-format data reader
* :func:`~scribe.util.schema_loader.build_model` - dynamic context-model
  builder
* :func:`~scribe.util.logger.render_context` - context manager that enriches
  log records with ``template`` / ``output`` metadata
* :func:`~scribe.util.logger.setup` - one-shot logging configurator

Keeping these high-traffic symbols in a single import path lets caller code
write::

    from scribe.util import DataLoader, render_context, setup

instead of longer, deeply nested import statements.  The
:pydata:`__all__` list below defines the *public API surface* for
``from scribe.util import *``; adding a new helper here automatically exposes
it project-wide.
"""

from .loader import DataLoader
from .logger import render_context as logger_render_context
from .logger import setup as logger_setup
from .schema_loader import build_model

__all__: list[str] = [
    "DataLoader",
    "build_model",
    "logger_render_context",
    "logger_setup",
]
