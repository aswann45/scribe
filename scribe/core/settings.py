"""
Configuration layer for *scribe* built on **pydantic-settings v2**.

The module exposes one public helper - :func:`get_settings` - which returns a
*singleton* instance of :class:`AppSettings`.  All other parts of the codebase
(e.g. CLI, batch jobs, notebooks) **import the helper**, not the class, so that
configuration is parsed exactly once per interpreter session.

Key features
------------
* **Multi-source loading** - YAML → ``.env`` → environment variables →
  explicit kwargs; implemented via
  :meth:`AppSettings.settings_customise_sources`.
* **Caching** - :func:`functools.lru_cache` guarantees a single in-memory copy.
* **Runtime safety** - any validation error is wrapped in
  :class:`scribe.core.exceptions.ConfigError`, giving the CLI a predictable
  exit code.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from scribe.core.exceptions import ConfigError
from scribe.models import TemplateConfig


class AppSettings(BaseSettings):
    """
    Project-wide and per-template configuration.

    Parameters (YAML / env / init kwargs)
    -------------------------------------
    templates : list[TemplateConfig], optional
        Declarative metadata for each DOCX template recognised by the
        pipeline.  Empty list by default so the application can start even
        without a config file.
    output_dir : pathlib.Path, default ``<project>/outputs``
        Directory where rendered documents are written.
    templates_dir : pathlib.Path, default ``<project>/templates``
        Root used by :pyclass:`scribe.util.template_finder.TemplateFinder`
        when scanning for unregistered templates.
    config_dir : pathlib.Path, default ``<project>/config``
        Folder that stores *app.yaml* and any generated snippets.

    Model config
    ------------
    ``model_config = SettingsConfigDict(...)`` sets
    * ``env_prefix="SCRIBE_"`` - environment variables are written in
      screaming-snake case (e.g. ``SCRIBE_OUTPUT_DIR``).
    * ``yaml_file=config_dir / "app.yaml"`` - the first, optional source.
    * ``validate_default=True`` - run field validators on defaults too.

    Notes
    -----
    * The class is **instantiated only via** :func:`get_settings`; direct
      construction elsewhere is discouraged so that all code paths share a
      single cached instance.
    * Paths are **resolved at import time** relative to the package root;
      override them per-environment through matching ``SCRIBE_*`` variables.
    """

    templates: list[TemplateConfig] = Field(default_factory=list)
    output_dir: Path = Path(__file__).parent.parent.parent / "outputs"
    templates_dir: list[Path] = Field(
        default=[Path(__file__).parent.parent.parent / "templates"]
    )
    config_dir: Path = Path(__file__).parent.parent.parent / "config"

    # Tell pydantic-settings to look for a YAML file first, then env vars
    model_config = SettingsConfigDict(
        env_prefix="SCRIBE_",  # e.g. SCRIBE_OUTPUT_DIR
        yaml_file=config_dir / "app.yaml",
        validate_default=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """
        Re-order the default *pydantic-settings* source chain.

        The final precedence becomes (highest → lowest):

        1. **Init settings** - explicit keyword arguments.
        2. **Environment variables** - ``SCRIBE_*``.
        3. **Dotenv file** - ``.env`` in the CWD, if present.
        4. **YAML file** - the path given in ``model_config.yaml_file``.
        5. **File secrets** - Kubernetes-style ``/var/run/secrets`` mounts.

        Returning the tuple in this order allows YAML to act as a *base*
        config while still letting environment variables override values in
        containerised deployments.
        """
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


@lru_cache
def get_settings() -> AppSettings:
    """
    Return a cached :class:`AppSettings` instance.

    Returns
    -------
    AppSettings
        The singleton settings object used across the project.

    Raises
    ------
    ConfigError
        If the underlying YAML/env configuration fails Pydantic validation.

    Notes
    -----
    * The function uses :pyfunc:`functools.lru_cache` with default settings
      (single slot) so repeated imports incur zero overhead.
    * Calling code **should not** catch :class:`pydantic.ValidationError`
      directly - always import and handle :class:`ConfigError` instead.
    """
    try:
        return AppSettings()
    except ValidationError as ve:
        raise ConfigError("Invalid app configuration.") from ve
