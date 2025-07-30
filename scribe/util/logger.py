"""scribe.util.logger.

A compact **stdout / stderr** logging helper that offers:

* **Two wire-formats**
  * *Developer* - human-readable, ANSI-colourised single line per record
  * *JSON* - structured one-line payload for ingestion by log systems
* **Context enrichment** - every log produced inside
  :pyclass:`render_context` automatically gains ``template`` and ``output``
  fields so multi-file batch runs are easy to debug.
* **Single entry-point** - :pyfunc:`setup` configures the *root* logger
  exactly once.  All other modules simply ``import logging`` and write.

The helper is purposely *dependency-free* beyond the Python standard library.

Examples
--------
>>> import logging
>>> from scribe.util.logger import setup, render_context
>>> setup(level="DEBUG")
>>> with render_context("invoice", "outputs/inv_0001.docx"):
...     logging.getLogger("scribe").info("Rendered successfully")

Environment variables
---------------------
``SCRIBE_LOG_JSON``
    When set to **non-empty**, :pyfunc:`setup` defaults to JSON format even if
    *json_mode* is not passed explicitly.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any, Final

__all__: list[str] = [
    "render_context",
    "setup",
]

_JSON_ENV: Final[str] = "SCRIBE_LOG_JSON"  # env override
_DEV_FMT: Final[str] = (
    "%(asctime)s | %(levelname)-8s | %(module)s:%(lineno)d | "
    "%(template)s%(output)s%(message)s"
)
_DEV_DATEFMT: Final[str] = "%H:%M:%S"


class _JSONFormatter(logging.Formatter):
    """Serialize :pyclass:`logging.LogRecord` as **one-line JSON**.

    Extra attributes ``template`` and ``output`` (injected by the record
    factory) are included when present, making downstream filtering painless.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Serialize *record* into a single-line JSON string.

        Parameters
        ----------
        record : logging.LogRecord
            The fully populated log record produced by the logging framework.

        Returns
        -------
        str
            An RFC-3339-timestamped JSON object containing the canonical keys
            ``ts``, ``lvl``, ``msg``, ``mod``, ``fn``, and ``line``.
            The optional enrichment keys ``template`` and ``output`` are
            included when present in *record* (they are injected by
            :pyclass:`render_context`).

        Notes
        -----
        * The payload is intentionally **flat** (no nested objects) so that
          downstream log shippers—e.g. CloudWatch or Datadog—can index fields
          without additional parsing rules.
        * Any non-JSON-serialisable values are converted to strings via
          ``json.dumps(..., default=str)`` to avoid runtime failures.
        """
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat()
            + "Z",
            "lvl": record.levelname,
            "msg": record.getMessage(),
            "mod": record.module,
            "fn": record.funcName,
            "line": record.lineno,
        }
        # Optional contextual fields
        if hasattr(record, "template"):
            payload["template"] = record.template
        if hasattr(record, "output"):
            payload["output"] = record.output
        return json.dumps(payload, default=str)


def _colour(level: int, text: str) -> str:
    """Return *text* wrapped in an ANSI colour code appropriate for *level*.

    Colour codes follow a simple mapping inspired by the *default* Python
    logging colours used by many frameworks.  If *stderr* is **not** attached
    to a TTY (e.g. when redirected to a file) colour codes are omitted.

    Parameters
    ----------
    level
        Numeric log-level as understood by :pymod:`logging` (e.g. 20 for
        ``logging.INFO``).
    text
        The already-formatted level-name to wrap.

    Returns
    -------
    str
        Possibly colourised string ready for concatenation.
    """
    if not sys.stderr.isatty():
        return text
    palette = {
        logging.DEBUG: 37,
        logging.INFO: 36,
        logging.WARNING: 33,
        logging.ERROR: 31,
        logging.CRITICAL: 35,
    }
    code = palette.get(level, 37)
    return f"\x1b[{code}m{text}\x1b[0m"


class _DevFormatter(logging.Formatter):
    r"""
    Colourised, single-line formatter optimised for terminals.

    Features
    --------
    * ANSI colour codes applied to the *level name* for rapid visual scanning.
    * Optional contextual prefix:
      ``[template] → output | `` is injected when the current
      :pyclass:`render_context` provides those values.
    * Compact ``HH:MM:SS`` timestamp keeps log width < 120 chars by default.

    Example
    -------
    ``14:02:31 | \x1b[36mINFO\x1b[0m     | generator:57 | [annual_report]
        → outputs/Acme.docx | Rendering finished``
    """

    def format(self, record: logging.LogRecord) -> str:
        record.levelname = _colour(record.levelno, record.levelname)
        # Display template/output if present
        record.template = (
            f"[{record.template}] " if hasattr(record, "template") else ""
        )
        record.output = (
            f"→ {record.output} | " if hasattr(record, "output") else ""
        )
        return super().format(record)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def setup(level: str | int = "INFO", json_mode: bool | None = None) -> None:
    """Initialise the *root* logger **once**.

    Calling :pyfunc:`setup` in multiple places is safe—the function is
    idempotent and will return immediately on subsequent invocations.

    Parameters
    ----------
    level
        Default log-level for *root* logger.  May be a string ("DEBUG") or the
        corresponding integer constant (e.g. ``logging.DEBUG``).
    json_mode
        When *True*, force JSON formatting; when *False*, force developer
        formatting.  When *None* (default), the value of the environment
        variable :pydata:`SCRIBE_LOG_JSON` determines the mode.

    Notes
    -----
    The function **overwrites** existing handlers on the root logger.  Call
    this early in application start-up.
    """
    if getattr(setup, "_configured", False):  # pragma: no cover
        return
    setup._configured = True  # type: ignore[attr-defined]

    json_mode = (
        json_mode if json_mode is not None else bool(os.getenv(_JSON_ENV))
    )

    handler = logging.StreamHandler()
    handler.setFormatter(
        _JSONFormatter()
        if json_mode
        else _DevFormatter(_DEV_FMT, _DEV_DATEFMT)
    )
    logging.basicConfig(level=level, handlers=[handler])

    # --- Enrich LogRecord globally ---------------------------------------- #
    factory = logging.getLogRecordFactory()

    def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = factory(*args, **kwargs)
        try:
            ctx = _CTX.get()
            record.template = ctx.template
            record.output = ctx.output
        except LookupError:  # no context active
            record.template = None
            record.output = None
        return record

    logging.setLogRecordFactory(record_factory)


# Thread-local context storage ----------------------------------------------
class _Context:
    """
    In-memory container for per-render metadata.

    Attributes
    ----------
    template : str | None
        Logical name of the template currently being rendered, or *None* when
        outside a :pyclass:`render_context` block.
    output : pathlib.Path | None
        Destination path of the file being generated, or *None* when not
        rendering.

    Implementation details
    ----------------------
    The instance is stored in a :pyclass:`contextvars.ContextVar`, which means
    each thread / async task receives a **separate** copy. This guarantees that
    log enrichment is race-free even in highly concurrent scenarios without the
    complexity of thread-locals or explicit locks.
    """

    __slots__ = ("output", "template")
    template: str | None
    output: str | None


_CTX: ContextVar[_Context] = ContextVar("_CTX")


class render_context:
    """Context-manager that enriches logs inside its ``with`` block.

    Parameters
    ----------
    template
        Name or identifier of the template being rendered (e.g.
        ``"annual_report"``).
    output
        Destination path (string) of the file being generated.

    Examples
    --------
    >>> import logging
    >>> from scribe.util.logger import render_context
    >>> with render_context("cover_letter", "outputs/letter.docx"):
    ...     logging.getLogger("scribe").info("Step 1 completed")
    """

    def __init__(self, template: str, output: str) -> None:
        self._ctx = _Context()
        self._ctx.template = template
        self._ctx.output = output
        self._token: Token[_Context] | None = None

    def __enter__(self) -> _Context:
        """
        Activate the render context.

        Returns
        -------
        _Context
            A thread-/task-local singleton whose attributes
            ``template`` and ``output`` have been set to the values
            provided at construction time.  The returned object allows
            read-only inspection inside the ``with`` block, but callers
            should treat its attributes as **read-only**.

        Notes
        -----
        Entering the context enables **automatic log enrichment**:
        every log record emitted while the context is active will
        contain the additional fields ``template`` and ``output``,
        which are consumed by both the development and JSON
        formatters.  This enrichment ceases when :py:meth:`__exit__`
        runs.
        """
        self._token = _CTX.set(self._ctx)
        return self._ctx

    def __exit__(
        self, exc_type: type | None, exc: Exception | None, tb: str | None
    ) -> None:
        """
        Deactivate the render context and clean up state.

        Parameters
        ----------
        exc_type :
            The exception type if an exception was raised inside the
            ``with`` block; otherwise *None*.
        exc :
            The exception instance if an exception was raised inside
            the ``with`` block; otherwise *None*.
        tb :
            The traceback corresponding to *exc*; otherwise *None*.

        Notes
        -----
        All three arguments are unused because the context manager
        does not perform exception handling; it merely resets the
        shared :pydata:`_CTX` object so that subsequent log messages
        are **not** tagged with stale ``template``/``output`` values.
        """
        if self._token is not None:
            _CTX.reset(self._token)
