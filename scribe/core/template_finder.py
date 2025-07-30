"""Search utilities for locating ``*.docx`` templates on disk.

The class :class:`TemplateFinder` supports three main workflows:

1.  **Discovery** - enumerate every template file under one or more *roots*,
    applying ignore patterns for lock-files or hidden directories.
2.  **Path-only view** - return a sorted list of :class:`pathlib.Path`
    objects for quick checks (``discover_paths``).
3.  **Metadata view** - return fully populated
    :class:`~scribe.core.settings.TemplateConfig` objects so higher-level
    code can merge *discovered* templates with those registered in YAML.

Environment variable ``SCRIBE_TEMPLATES_DIR`` (colon- or semicolon-separated)
gets first priority, followed by ``templates_dir`` from
:class:`~scribe.core.settings.AppSettings`.

Examples
--------
>>> finder = TemplateFinder()
>>> for cfg in finder.discover():
...     print(cfg.name, cfg.path)
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Sequence
from pathlib import Path

from scribe.core.settings import TemplateConfig, get_settings
from scribe.models import TemplateOption

settings = get_settings()

_DEFAULT_IGNORE = [
    re.compile(r"~\$.*\.docx$"),  # Office tmp files
    re.compile(r".*[/\\]\..+[/\\].*"),  # hidden dirs like .git/.DS_Store
]


class TemplateFinder:
    """
    Locate ``*.docx`` templates across one or more directory roots.

    Parameters
    ----------
    roots : Iterable[pathlib.Path] | None, optional
        One or more root directories to scan.  *None* (default) triggers the
        precedence chain:

        1. ``SCRIBE_TEMPLATES_DIR`` - split on ``os.pathsep``.
        2. :pyattr:`scribe.core.settings.AppSettings.templates_dir`.

        Each path is ``~``-expanded and resolved to an absolute path.
    ignore : Sequence[re.Pattern] | None, optional
        Regex patterns; if *any* matches the candidate path's **full POSIX
        string**, that file is skipped.  Defaults to:

        * ``~$*.docx`` - Office lock files
        * anything under a hidden directory (``.git/``, ``.idea/`` …)

    Notes
    -----
    * All returned paths are **deduplicated** and sorted
      case-insensitively for stable output across platforms.
    * Additional ignore rules can be supplied at runtime, e.g. to skip an
      ``archive`` folder: ::

          rx_archive = re.compile(r"/archive/")
          finder = TemplateFinder(ignore=_DEFAULT_IGNORE + [rx_archive])
    """

    def __init__(
        self,
        roots: Iterable[Path] | None = None,
        ignore: Sequence[re.Pattern[str]] | None = None,
    ) -> None:
        self._roots: set[Path] = self._resolve_roots(roots)
        self._ignore: Sequence[re.Pattern[str]] = ignore or _DEFAULT_IGNORE

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    def discover(self) -> list[TemplateConfig]:
        """
        Return complete :class:`TemplateConfig` objects for **all** templates.

        Every path returned by :meth:`discover_paths` is wrapped in a
        ``TemplateConfig`` with:

        * ``name`` - stem of the filename
        * ``output_naming`` - ``"<stem>.docx"`` sensible default
        * ``options`` - empty :class:`scribe.models.TemplateOption`

        Returns
        -------
        list[TemplateConfig]
            Deterministically ordered list (by absolute path).
        """
        return [
            TemplateConfig(
                name=path.stem,
                path=path,
                output_naming=f"{path.stem}.docx",
                options=TemplateOption(),
            )
            for path in self.discover_paths()
        ]

    def discover_paths(self) -> list[Path]:
        """
        Return only the file paths of discovered templates.

        The method walks each root with :pyfunc:`pathlib.Path.rglob`,
        filters via :meth:`_is_ignored`, deduplicates, and sorts.

        Returns
        -------
        list[pathlib.Path]
            Sorted, absolute, lower-cased order for cross-platform parity.
        """
        files: set[Path] = set()
        for root in self._roots:
            if not root.is_dir():
                continue
            for path in root.rglob("*.docx"):
                if self._is_ignored(path):
                    continue
                files.add(path.resolve())
        # Stable deterministic ordering
        return sorted(files, key=lambda p: p.as_posix().lower())

    @staticmethod
    def _resolve_roots(roots: Iterable[Path] | None) -> set[Path]:
        """
        Combine constructor roots, env var, and YAML settings into a set.

        Parameters
        ----------
        roots :
            Explicit roots passed to :class:`TemplateFinder`.

        Returns
        -------
        set[pathlib.Path]
            Normalised, absolute root directories to be scanned.
        """
        if roots is None:
            # ← 1️⃣  check env var; fallback to AppSettings
            env = os.getenv("SCRIBE_TEMPLATES_DIR")
            if env:
                roots = (Path(p) for p in env.split(os.pathsep) if p.strip())
            else:
                roots = settings.templates_dir
        return {Path(r).expanduser().resolve() for r in roots}

    def _is_ignored(self, path: Path) -> bool:
        """
        Check whether *path* should be skipped based on ignore patterns.

        Parameters
        ----------
        path : pathlib.Path
            Candidate template file.

        Returns
        -------
        bool
            ``True`` if any regex in ``self._ignore`` matches the POSIX path,
            ``False`` otherwise.
        """
        rel = path.as_posix()
        return any(rx.search(rel) for rx in self._ignore)
