"""Type aliases and other non-pydantic types.

Centralised *type aliases* and lightweight enums that are shared across
multiple sub-packages. Placing them here prevents circular-import headaches
in modules such as `generator`, `template_finder`, and `logger`.

Only **small, dependency-free** constructs belong in this file. Anything that
requires Pydantic, pandas, or other heavier libraries should live closer to
the feature that needs it.
"""

from collections.abc import Mapping, Sequence
from enum import Enum

from scribe.models import ConditionalRichText, RichTextStyle


class LogLevel(str, Enum):
    """
    Canonical log-level names recognised by the CLI.

    The string values intentionally match the constants used by
    :pymod:`logging` so they can be passed directly to
    :pymeth:`logging.Logger.setLevel`.

    Notes
    -----
    • The enum inherits from :class:`str` so members are JSON-serialisable
      without additional converters.
    • Keep the member list short; we only expose levels actually useful to
      end-users.
    """

    debug = "DEBUG"
    info = "INFO"
    warning = "WARNING"
    error = "ERROR"


TRichTextOptionMap = Mapping[
    str, RichTextStyle | Sequence[ConditionalRichText]
]
"""
Typing alias used by :pyfunc:`scribe.core.generator._style_for_value`.

Key-value mapping where:

* **Key** → the Jinja placeholder name inside the DOCX template.
* **Value** → either
  * a single :class:`~scribe.models.RichTextStyle` (unconditional), **or**
  * a list of :class:`~scribe.models.ConditionalRichText` objects
    evaluated top-to-bottom (first match wins).

Example
-------
>>> from scribe.models import RichTextStyle
>>> opts: TRichTextOptionMap = {
...     "status": RichTextStyle(bold=True, color="008000"),
...     "score": [
...         ConditionalRichText(
...             when=RichTextPredicate(lt=50),
...             style=RichTextStyle(color="008000"),
...         ),
...         ConditionalRichText(
...             when=RichTextPredicate(gte=50),
...             style=RichTextStyle(color="CC0000"),
...         ),
...     ],
... }
"""
