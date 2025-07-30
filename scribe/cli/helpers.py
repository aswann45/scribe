"""
Utilities shared by all Typer CLI commands.

* **`_handle_error`** - Centralised mapping from
  :class:`scribe.core.exceptions.ScribeError` sub-classes → numeric exit
  codes.  Emits a structured log line **and** a user-facing message before
  delegating to :class:`typer.Exit`.

* **`scribe_command`** - Decorator that wraps any CLI function, guaranteeing
  that unhandled *ScribeError*s are caught by :func:`_handle_error`.  Keeps
  individual command bodies free from repetitive ``try/except`` boiler-plate.

Other modules should import **only** the decorator:

```python
from scribe.cli.helpers import scribe_command
```
"""

import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

import typer

from scribe.core.exceptions import (
    ConfigError,
    DataLoadError,
    RenderError,
    ScribeError,
    TemplateNotFoundError,
)

EXIT_CODES = {
    ConfigError: 2,
    TemplateNotFoundError: 3,
    DataLoadError: 4,
    RenderError: 5,
}


def _handle_error(exc: ScribeError) -> None:
    """
    Log *exc*, show concise message, and abort with a deterministic exit code.

    Parameters
    ----------
    exc :
        Any subclass of :class:`~scribe.core.exceptions.ScribeError`.

    Side Effects
    ------------
    * Writes one structured log line at ``ERROR`` level.
    * Prints a short human-readable message to *stderr* via
      :func:`typer.echo`.
    * Terminates the current Typer command by raising :class:`typer.Exit`
      with the code looked-up in :data:`EXIT_CODES`.

    Notes
    -----
    Unknown subclasses (edge-cases) default to exit-code ``1`` - matching
    conventional *Unix* “generic error” semantics.
    """
    code = EXIT_CODES.get(type(exc), 1)
    logging.getLogger("scribe").error(str(exc))
    typer.echo(f"Error: {exc}", err=True)
    raise typer.Exit(code)


F = TypeVar("F", bound=Callable[..., object])


# Decorator helper
def scribe_command(fn: F) -> F:
    """
    Wrap *fn* so that **all** :class:`ScribeError`s are handled uniformly.

    The decorator is intended for Typer command functions and callbacks:

    ```python
    @app.command()
    @scribe_command
    def generate(...):
        ...
    ```

    Parameters
    ----------
    fn : Callable
        The original command function.

    Returns
    -------
    Callable
        A thin wrapper that executes *fn* inside a ``try/except`` block
        calling :func:`_handle_error` on failure.

    Raises
    ------
    typer.Exit
        Re-raises whatever :func:`_handle_error` produced so the surrounding
        Typer framework terminates with the appropriate code.

    Implementation Detail
    ---------------------
    :func:`functools.wraps` preserves the wrapped function's signature and
    docstring so that ``--help`` output remains accurate.
    """

    @functools.wraps(fn)
    def _wrapper(*args: Any, **kwargs: Any) -> object:
        try:
            return fn(*args, **kwargs)
        except ScribeError as exc:
            code = EXIT_CODES.get(type(exc), 1)
            logging.getLogger("scribe").error(str(exc))
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code) from exc

    return _wrapper  # type: ignore[return-value]
