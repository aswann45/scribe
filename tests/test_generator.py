"""generate_docx end-to-end with rich-text predicate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from docxtpl import DocxTemplate

from scribe.core import RenderError
from scribe.core.generator import generate_docx
from scribe.models import BaseDocContext, TemplateConfig, TemplateOption
from scribe.models.templates import (
    ConditionalRichText,
    RichTextPredicate,
    RichTextStyle,
)


def test_richtext_application(tmp_path: Path) -> None:
    """ConditionalRichText converts placeholder into shiny RichText."""
    sample_template = Path("tests/templates/tpl.docx").resolve()
    cfg = TemplateConfig(
        name="test",
        path=sample_template,
        output_naming="test.docx",
        options=TemplateOption(
            richtext={
                "status": [
                    ConditionalRichText(
                        when=RichTextPredicate(equals="OK"),
                        style=RichTextStyle(color="008000"),
                    )
                ],
            }
        ),
    )
    ctx = BaseDocContext(status="OK")
    out = generate_docx(ctx, cfg, tmp_path)
    assert out.exists()


def _dummy_docx(path: Path) -> None:
    """Write an empty ZIP file so DocxTemplate accepts the path."""
    path.write_bytes(b"PK\x05\x06" + b"\x00" * 18)


def test_generate_docx_with_mapping(tmp_path: Path) -> None:
    """Dict payload returns a file path."""
    tpl = tmp_path / "map.docx"
    _dummy_docx(tpl)

    cfg = TemplateConfig(
        name="map",
        path=tpl,
        output_naming="map.docx",
        options=TemplateOption(
            richtext={
                "status": RichTextStyle(color="008000"),  # unconditional style
            }
        ),
    )

    # Monkey-patch render/save so we don't depend on real Word XML
    def noop_render(self: DocxTemplate, ctx: dict[str, Any]) -> None: ...

    def noop_save(self: DocxTemplate, where: Path | str) -> None: ...

    DocxTemplate.render, DocxTemplate.save = noop_render, noop_save  # type: ignore[assignment]

    out = generate_docx({"status": "OK"}, cfg, tmp_path)
    assert out.name == "map.docx" and out.exists()


def test_generate_docx_raises_render_error(tmp_path: Path) -> None:
    """Force an exception inside DocxTemplate.render."""
    tpl = tmp_path / "boom.docx"
    _dummy_docx(tpl)

    cfg = TemplateConfig(name="boom", path=tpl, output_naming="boom.docx")

    # Patch render to raise; save is never reached
    def boom(self: DocxTemplate, ctx):  # noqa: ANN001
        raise RuntimeError("💥")

    DocxTemplate.render = boom  # type: ignore[assignment]

    with pytest.raises(RenderError):
        generate_docx({"x": 1}, cfg, tmp_path)
