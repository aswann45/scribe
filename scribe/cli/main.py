"""Top-level **Typer** application that exposes the command-line interface.

Commands
--------
list-templates
    Print registered templates (from `app.yaml`) or, with the `--all` flag,
    merge them with any `.docx` files discovered on disk via
    :class:`~scribe.core.template_finder.TemplateFinder`.

discover-templates
    Scan the template roots and write a YAML snippet for all *unregistered*
    templates.  The resulting file can be merged back into `app.yaml`.

generate
    Render one or many documents from a data file (`YAML`, `JSON`, `CSV`,
    `Excel`).  Supports bulk CSV/Excel generation, delimiter overrides,
    schema validation, and rich-text styling.

validate
    Schema-validate a data file **without** rendering a document—useful in CI
    pipelines.

Global options
--------------
--log-level
    One of ``DEBUG``, ``INFO`` (*default*), ``WARNING``, ``ERROR``.
--log-json / --no-log-json
    Toggle structured JSON logs (for log aggregation) vs. colourised
    human-readable output.

Environment variables
---------------------
SCRIBE_TEMPLATES_DIR
    `os.pathsep`-separated list of template search roots (overrides
    `AppSettings.templates_dir`).
SCRIBE_LOG_JSON
    Set to `1` to enable JSON logs without passing `--log-json`.

Implementation notes
--------------------
* A **single** :class:`scribe.core.settings.AppSettings` instance is created
  on import (module-level `settings` variable) and reused by every command.
* The decorator :func:`scribe.cli.helpers.scribe_command` wraps each command
  so that any :class:`scribe.core.exceptions.ScribeError` bubbles up to a
  uniform error handler—simplifying the command bodies.
"""

import logging
import os
from pathlib import Path, PurePath
from typing import Annotated, Any, Optional

import typer
import yaml
from pydantic import ValidationError

from scribe.cli.helpers import scribe_command
from scribe.core.context_factory import make_context
from scribe.core.exceptions import (
    ConfigError,
    TemplateNotFoundError,
)
from scribe.core.generator import generate_docx
from scribe.core.settings import get_settings
from scribe.core.template_finder import TemplateFinder
from scribe.core.typings import LogLevel
from scribe.models import BaseDocContext
from scribe.util.loader import DataLoader
from scribe.util.logger import setup as log_setup

app = typer.Typer(no_args_is_help=True)
settings = get_settings()


@app.command()
@scribe_command
def list_templates(
    registered_only: Annotated[
        bool,
        typer.Option(
            "--registered-only/--all",
            help="Show only templates declared in config.",
        ),
    ] = True,
    templates_dir: Annotated[
        Optional[str],
        typer.Argument(
            help="Override template root; same syntax as $SCRIBE_TEMPLATES_DIR"
        ),
    ] = None,
) -> None:
    """List available templates."""
    if templates_dir:
        os.environ["SCRIBE_TEMPLATES_DIR"] = (
            templates_dir  # single-run override
        )

    typer.echo("Available templates:\n")
    finder = TemplateFinder()

    if registered_only:
        tpls = settings.templates
    else:
        known = {t.path.expanduser().resolve(): t for t in settings.templates}
        for t in finder.discover():
            known.setdefault(t.path, t)
        tpls = list(known.values())
    for t in tpls:
        mark = "•" if t in settings.templates else "○"
        typer.echo(f"{mark} {t.name.ljust(20)} {t.path}")


@app.command()
@scribe_command
def discover_templates(
    output_file: Annotated[
        Optional[Path],
        typer.Argument(
            help="Write a YAML snippet you can merge into app.yaml."
        ),
    ] = None,
) -> None:
    """Scan template roots for *unregistered* ``.docx`` files and emit YAML."""
    if output_file is None:
        output_file = settings.config_dir / "discovered_templates.yaml"
    registered = {t.path for t in settings.templates}
    new_tpls = [
        t for t in TemplateFinder().discover() if t.path not in registered
    ]

    if not new_tpls:
        typer.echo("✓ No new templates found.")
        raise typer.Exit()

    def _path_representer(dumper: Any, data: Any) -> Any:
        return dumper.represent_scalar("tag:yaml.org,2002:str", str(data))

    yaml.add_multi_representer(PurePath, _path_representer)

    snippet = yaml.dump({"templates": [t.model_dump() for t in new_tpls]})

    output_file.parent.mkdir(exist_ok=True, parents=True)
    output_file.write_text(snippet)
    typer.echo(
        f"✓ {len(new_tpls)} template(s) written to {output_file}\n"
        f"   → Review & merge into config/app.yaml when ready."
    )


@app.command()
@scribe_command
def generate(
    template_name: Annotated[
        str,
        typer.Argument(
            help=(
                "Name of the template to render "
                "(do not include file extension)."
            )
        ),
    ],
    data_file: Annotated[
        Path, typer.Argument(help="Path to data file with template context.")
    ],
    output_dir: Annotated[
        Path,
        typer.Option(help="Path to directory to save rendered templates to."),
    ] = settings.output_dir,
    delimiter: Annotated[
        str, typer.Option(help="CSV delimiter (ignored for YAML/JSON/Excel)..")
    ] = ",",
    strict_schema: Annotated[
        bool,
        typer.Option(
            help="Fail if the schema file exists but data has extra keys."
        ),
    ] = False,
) -> None:
    """Render <data_file> with the template named <template_name>."""
    t_cfg = next(
        (t for t in settings.templates if t.name == template_name), None
    )
    if not t_cfg:
        raise TemplateNotFoundError(template_name)

    ctx_raw = DataLoader.load(data_file, as_records=True, delimiter=delimiter)

    output_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(ctx_raw, list):
        for c in ctx_raw:
            try:
                ctx = make_context(t_cfg.path, c)
            except ConfigError as ex:
                if strict_schema:
                    raise
                typer.echo(f"Warning: {ex}", err=True)
                ctx = c
            try:
                doc_path = generate_docx(
                    BaseDocContext.model_validate(ctx),  # quick validation
                    t_cfg,
                    output_dir,
                )
                typer.echo(f"Generated → {doc_path}")
            except ValidationError as ve:
                raise typer.Exit(1) from ve
    else:
        try:
            ctx = make_context(t_cfg.path, ctx_raw)
        except ConfigError as ex:
            if strict_schema:
                raise
            typer.echo(f"Warning: {ex}", err=True)
            ctx = ctx_raw
        try:
            doc_path = generate_docx(
                BaseDocContext.model_validate(ctx),  # quick validation
                t_cfg,
                output_dir,
            )
            typer.echo(f"Generated → {doc_path}")
        except ValidationError as ve:
            raise typer.Exit(1) from ve


@app.command()
@scribe_command
def validate(
    data_file: Annotated[
        Path, typer.Argument(help="Path to data file to validate.")
    ],
    delimiter: Annotated[
        str, typer.Option(help="CSV delimiter (ignored for YAML/JSON/Excel)..")
    ] = ",",
) -> None:
    """Validate data against the schema."""
    ctx = DataLoader.load(data_file, as_records=True, delimiter=delimiter)
    if isinstance(ctx, list):
        for c in ctx:
            try:
                BaseDocContext.model_validate(c)
            except ValidationError as e:
                typer.echo(f"Validation failed: {e}")
        typer.echo("Validation successful.")
    else:
        try:
            BaseDocContext.model_validate(ctx)
            typer.echo("Validation successful.")
        except ValidationError as e:
            typer.echo(f"Validation failed: {e}")
            raise typer.Exit(1) from e


@app.callback(invoke_without_command=True)
@scribe_command
def _init(
    log_level: Annotated[
        LogLevel,
        typer.Option(
            help="Logging verbosity.",
        ),
    ] = LogLevel.info,
    log_json: Annotated[
        bool, typer.Option(help="Emit one-line JSON logs.")
    ] = False,
) -> None:
    """Global initialization for the CLI."""
    log_setup(level=log_level.upper(), json_mode=log_json)
    logging.getLogger("scribe").debug("Logger initialized.")
