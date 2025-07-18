"""Centralised exception hierarchy for *scribe*."""

from __future__ import annotations


class ScribeError(Exception):
    """Base class for all custom errors."""


# ── Config / settings ────────────────────────────────────────────────────────
class ConfigError(ScribeError):
    """Invalid or missing configuration detected."""


# ── Data loading ─────────────────────────────────────────────────────────────
class DataLoadError(ScribeError):
    """Failure while reading a source data file."""


# ── Template discovery / selection ───────────────────────────────────────────
class TemplateNotFoundError(ScribeError):
    """Requested template name cannot be resolved."""


# ── Rendering / generation ───────────────────────────────────────────────────
class RenderError(ScribeError):
    """Any error that occurs during template rendering or saving."""
