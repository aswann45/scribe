"""TemplateFinder multi-root + ignore patterns."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from scribe.core.settings import AppSettings
from scribe.core.template_finder import TemplateFinder


def test_discovery_with_ignore(tmp_path: Path) -> None:
    """Hidden .git dir and Office ~$ lock file are skipped."""
    root1 = tmp_path / "r1"
    root1.mkdir()
    root2 = tmp_path / "r2"
    root2.mkdir()
    (root1 / "ok.docx").touch()
    (root2 / "~$bad.docx").touch()
    (root2 / ".git").mkdir()
    (root2 / ".git" / "hidden.docx").touch()

    finder = TemplateFinder(roots=[root1, root2])
    paths = finder.discover_paths()
    assert len(paths) == 1 and paths[0].name == "ok.docx"


def _touch_docx(path: Path) -> None:
    """Create an empty, valid ZIP header so the file looks like a docx."""
    path.write_bytes(b"PK\x05\x06" + b"\x00" * 18)


def test_env_var_multiple_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    SCRIBE_TEMPLATES_DIR env-var overrides settings and is split on os.pathsep.

    Hits TemplateFinder._resolve_roots branch (lines ≈101).
    """
    r1, r2 = tmp_path / "r1", tmp_path / "r2"
    r1.mkdir()
    r2.mkdir()
    _touch_docx(r1 / "a.docx")
    _touch_docx(r2 / "b.docx")

    sep = os.pathsep
    monkeypatch.setenv("SCRIBE_TEMPLATES_DIR", f"{r1}{sep}{r2}")

    paths = TemplateFinder().discover_paths()
    configs = TemplateFinder().discover()
    assert {p.parent for p in paths} == {r1, r2}
    assert {c.name for c in configs} == {"a", "b"}


def test_ignore_and_not_ignore(tmp_path: Path) -> None:
    """
    Verify that default ignore patterns skip Office lock files AND allow normal files.

    Exercises _is_ignored True/False paths (≈151-155).
    """
    # create files
    good = tmp_path / "ok.docx"
    bad = tmp_path / "~$lock.docx"
    _touch_docx(good)
    _touch_docx(bad)

    finder = TemplateFinder(roots=[tmp_path])

    ignored: set[str] = {
        p.name for p in finder._roots.pop().iterdir() if finder._is_ignored(p)
    }  # type: ignore[attr-defined]  # private access only in test
    assert "~$lock.docx" in ignored
    assert "ok.docx" not in ignored


def test_non_directory_root(tmp_path: Path) -> None:
    """
    If a supplied *root* path is a **file**, discover_paths should silently skip it.

    Triggers line ≈126 (continue on non-dir).
    """
    file_root = tmp_path / "not_a_dir"
    file_root.touch()  # create a file, not a directory
    good_dir = tmp_path / "dir"
    good_dir.mkdir()
    _touch_docx(good_dir / "x.docx")

    finder = TemplateFinder(roots=[file_root, good_dir])
    paths = finder.discover_paths()
    assert len(paths) == 1 and paths[0].name == "x.docx"


def test_no_provided_root(tmp_path: Path) -> None:
    """Test TemplateFinder picks up AppSettings root if none is set in env."""
    finder = TemplateFinder()
    paths = finder.discover_paths()
    settings = AppSettings()
    assert len(paths) == 1 and paths[0].parent == settings.templates_dir[0]
