"""
Generate Docx rendered templates.

High-level “orchestrator” that turns a fully-validated context plus a
:class:`~scribe.core.settings.TemplateConfig` object into a finished **DOCX**
file.  The steps are:

1.  **Schema validation** - :func:`scribe.core.context_factory.make_context`
    enforces (or bypasses) a side-car YAML schema.
2.  **Rich-text post-processing** - :func:`_apply_richtext` converts selected
    placeholder values into ``docxtpl.RichText`` objects according to the
    declarative rules stored in ``TemplateConfig.options.richtext``.
3.  **Rendering** - Feed the context to *docxtpl*, save the file, and emit
    structured log messages via :pyfunc:`scribe.util.logger.render_context`.

Any template-specific logic (uppercase flags, conditional styling, etc.)
belongs **here** so that the CLI, notebooks, and any future HTTP server can
share the exact same implementation.
"""

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate, RichText  # type: ignore[import-untyped]
from pydantic import BaseModel

from scribe.core.context_factory import make_context
from scribe.core.exceptions import RenderError
from scribe.core.settings import TemplateConfig
from scribe.core.typings import TRichTextOptionMap
from scribe.models import RichTextStyle
from scribe.util.logger import render_context

logger = logging.getLogger(__name__)


def _style_for_value(
    placeholder: str,
    value: Any,
    opt_map: TRichTextOptionMap,
) -> RichTextStyle | None:
    """
    Determine whether *value* should be formatted and, if so, return a style.

    The lookup algorithm:

    1. If *placeholder* **not** in *opt_map* → *None* (no styling).
    2. If the mapped entry is a single :class:`RichTextStyle`
       (unconditional) → return it.
    3. If the entry is a ``list[ConditionalRichText]`` iterate in
       declaration order; the **first** predicate that matches *value*
       wins.  If none match → *None*.

    Parameters
    ----------
    placeholder :
        The Jinja variable name being processed.
    value :
        The current value that will appear in the template.
    opt_map :
        The ``richtext`` mapping from :class:`TemplateOption`.

    Returns
    -------
    RichTextStyle | None
        The style to apply, or ``None`` if no rule matched.
    """
    try:
        rule_set = opt_map[placeholder]
    except KeyError:
        return None

    # Unconditional single style
    if isinstance(rule_set, RichTextStyle):
        return rule_set

    # Iterate over conditional list - first match wins
    for rule in rule_set:
        if rule.when.matches(value):
            return rule.style

    return None


def _apply_richtext(ctx: dict[str, Any], cfg: TemplateConfig) -> None:
    """
    Mutate *ctx* **in-place** to inject ``RichText`` objects.

    For each key/value pair in *ctx*:

    * Call :func:`_style_for_value`; if it returns a style, create a
      :class:`docxtpl.RichText` instance with that style and store it under
      ``"richtext_<placeholder>"``.  The original plain value is left
      untouched so templates can opt-in by referencing the prefixed
      variable.

    Parameters
    ----------
    ctx :
        The *render context* dictionary that will be passed to
        :pymeth:`docxtpl.DocxTemplate.render`.
    cfg :
        The template configuration providing the rich-text style map.

    Notes
    -----
    * Using a **prefixed** key avoids collision with the original plain
      value and keeps templates backward-compatible.
    * The helper is intentionally side-effectful (mutates *ctx*) to avoid
      the overhead of dictionary copies during bulk generation.
    """
    for name, val in list(ctx.items()):
        style = _style_for_value(name, val, cfg.options.richtext)
        if style is None:
            continue

        rt = RichText(str(val), **style.model_dump(exclude_none=True))
        ctx[f"richtext_{name}"] = rt


def generate_docx(
    context: BaseModel | Mapping[str, Any],
    config: TemplateConfig,
    output_dir: Path,
) -> Path:
    """
    Render a Word document from *context* and *config*.

    Parameters
    ----------
    context :
        Either a Pydantic model **or** a plain mapping produced by
        :pymod:`scribe.util.loader`.  If a schema file exists for
        *config.path*, the payload is re-validated via
        :func:`scribe.core.context_factory.make_context`.
    config :
        Metadata object containing template path, output-naming rule,
        and rich-text options.
    output_dir :
        Directory where the rendered file will be saved.

    Returns
    -------
    pathlib.Path
        Absolute path to the generated ``.docx``.

    Raises
    ------
    RenderError
        Wraps any exception raised by *docxtpl* so that callers (CLI, API)
        can map it to a consistent exit code / HTTP status.

    Side Effects
    ------------
    * Creates or overwrites a file on disk.
    * Emits two structured log lines (“Rendering started/finished”) with
      ``template`` and ``output`` enrichment provided by
      :pyclass:`scribe.util.logger.render_context`.

    Example
    -------
    >>> ctx = DataLoader.load(Path("data/annual_report.yaml"))
    >>> tpl_cfg = settings.templates[0]
    >>> generate_docx(ctx, tpl_cfg, Path("outputs"))
    PosixPath('outputs/AcmeCorp_20250716_report.docx')
    """
    tpl = DocxTemplate(config.path)
    ctx_obj = make_context(config.path, context)

    ctx: dict[str, Any]
    if isinstance(ctx_obj, BaseModel):
        ctx = ctx_obj.model_dump()
    else:
        ctx = dict(context)

    _apply_richtext(ctx, config)

    out_name = config.output_naming.format(**ctx)
    out_path = output_dir / out_name
    with render_context(config.name, str(out_path)):
        logger.info("Rendering started")
        try:
            tpl.render(ctx)
            tpl.save(out_path)
        except Exception as ex:  # pragma: no cover
            logger.error("Rendering failed", exc_info=ex)
            raise RenderError(f"While rendering {config.name!r}") from ex
        logger.info("Rendering finished")
    return out_path
