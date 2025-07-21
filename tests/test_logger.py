"""Logger enrichment and JSON formatting."""

from __future__ import annotations

import io
import json
import logging

import pytest

from scribe.util.logger import (
    _CTX,
    _colour,
    _DevFormatter,
    _JSONFormatter,  # private import OK for tests
    render_context,
)
from scribe.util.logger import (
    setup as log_setup,
)

log_setup(level="INFO", json_mode=True)


def test_json_formatter_enriched() -> None:
    """A log inside render_context is JSON-formatted & enriched."""
    logger = logging.getLogger("scribe.test")
    logger.setLevel(logging.INFO)  # <- ensure INFO reaches handler

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(_JSONFormatter())
    logger.addHandler(handler)

    with render_context("tpl", "out.docx"):
        logger.info("hello")

    handler.flush()  # make sure buffer is written
    logger.removeHandler(handler)  # cleanup

    payload = json.loads(stream.getvalue().strip())
    assert payload["template"] == "tpl"
    assert payload["output"] == "out.docx"


def test_setup_selects_correct_formatter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SCRIBE_LOG_JSON env-var drives formatter choice."""
    orig_basic = logging.basicConfig

    def basic_force(*args, **kwargs):  # noqa: D401 ANN001
        kwargs["force"] = True
        return orig_basic(*args, **kwargs)

    monkeypatch.setattr(logging, "basicConfig", basic_force)

    # --- JSON mode via env var -------------------------------------
    monkeypatch.setenv("SCRIBE_LOG_JSON", "1")
    # reset state flags and handlers
    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)
    if hasattr(log_setup, "_configured"):
        delattr(log_setup, "_configured")

    log_setup(level="INFO")  # json_mode is None so env wins
    assert isinstance(logging.root.handlers[0].formatter, _JSONFormatter)

    # --- Developer mode via explicit arg ---------------------------
    monkeypatch.setenv("SCRIBE_LOG_JSON", "")
    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)
    delattr(log_setup, "_configured")  # reset idempotent guard

    log_setup(level="INFO", json_mode=False)
    assert isinstance(logging.root.handlers[0].formatter, _DevFormatter)


# ------------------------------------------------------------------ #
# 2) nested render_context + ContextVar reset (156-164, 216-218)
# ------------------------------------------------------------------ #
def test_nested_render_context_resets() -> None:
    """
    Nested contexts update and then restore _Context values.

    After the outer ``with`` block exits both ``template`` and ``output``
    must be **None**, proving that lines 216-218 executed.
    """
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(_JSONFormatter())
    logger = logging.getLogger("scribe.nested")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    with render_context("outer", "outer.docx"):
        logger.info("1st")
        with render_context("inner", "inner.docx"):
            logger.info("2nd")
        # back to outer here
        logger.info("3rd")

    handler.flush()
    logger.removeHandler(handler)
    records = [json.loads(line) for line in stream.getvalue().splitlines()]

    # ensure correct template/output at each nesting level
    tpl_out_pairs = [(r["template"], r["output"]) for r in records]
    assert tpl_out_pairs == [
        ("outer", "outer.docx"),
        ("inner", "inner.docx"),
        ("outer", "outer.docx"),
    ]

    # after both contexts exit, _Context should be cleared
    assert _CTX.get(None) is None


def test_setup_idempotent() -> None:
    """
    Calling log_setup twice should early-exit on the second call.

    This hits the `_configured` guard (lines 126-134) without altering the
    handler count or formatter type.
    """
    # wipe existing handlers, then configure fresh
    logging.root.handlers.clear()
    if hasattr(log_setup, "_configured"):
        delattr(log_setup, "_configured")

    log_setup(level="INFO", json_mode=True)
    first_handler = logging.root.handlers[0]

    log_setup(level="DEBUG", json_mode=False)  # params shouldn’t matter
    assert logging.root.handlers[0] is first_handler  # no new handler added
    assert isinstance(first_handler.formatter, _JSONFormatter)


@pytest.mark.parametrize(
    "level,expected_code",
    [
        (logging.DEBUG, 37),
        (logging.INFO, 36),
        (logging.WARNING, 33),
        (logging.ERROR, 31),
        (logging.CRITICAL, 35),
        (99_999, 37),  # default branch: unknown level → code 37
    ],
)
def test_colour_palette(level: int, expected_code: int, monkeypatch) -> None:
    """
    Ensure _colour() wraps text with the palette-selected ANSI code.

    The test disables TTY detection so the function *always* emits colour
    codes, independent of the host environment.
    """
    # Pretend stderr is a TTY to force colouring path.
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)

    txt = "X"
    coloured = _colour(level, txt)
    prefix, rest = coloured.split("m", 1)

    assert prefix == f"\x1b[{expected_code}"
    assert rest == f"{txt}\x1b[0m"


def test_record_factory_no_active_context(monkeypatch) -> None:
    """When *no* render_context is active the LogRecord must be empty."""
    # --- Ensure clean logging root + force re-configure -------------
    logging.root.handlers.clear()
    if hasattr(log_setup, "_configured"):
        delattr(log_setup, "_configured")

    # patch basicConfig to always reconfigure (force=True)
    orig_basic = logging.basicConfig

    def basic_force(*args, **kwargs):  # noqa: ANN001 D401
        kwargs["force"] = True
        return orig_basic(*args, **kwargs)

    monkeypatch.setattr(logging, "basicConfig", basic_force)

    # --- Set up JSON logging ---------------------------------------
    log_setup(level="INFO", json_mode=True)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(_JSONFormatter())
    logging.getLogger("scribe.noctx").addHandler(handler)

    # Emit a log OUTSIDE any render_context
    logging.getLogger("scribe.noctx").info("outside")

    handler.flush()
    payload = json.loads(stream.getvalue().strip())

    assert payload["template"] is None and payload["output"] is None
