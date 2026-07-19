"""How an application describes its configuration setup.

One inert value object. Everything the loader needs to know about *this*
application — where its packaged config lives, what its env prefix is, which
sections may be given as a profile name — is stated here rather than baked into
the loader.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: A configuration mapping before validation.
RawConfig = dict[str, Any]

#: Default filename for the packaged base config and for user/project configs.
DEFAULT_CONFIG_NAME = "config.yml"

#: Packaged env configs are `config.<name>.yml`.
ENV_CONFIG_PREFIX = "config."


@dataclass(frozen=True)
class ConfigSpec:
    """The shape of one application's configuration.

    Every layer is optional. An app with a single config file sets only
    `config_root`; an app with the full stack sets `app_name` and `project_dir`
    as well.
    """

    #: Directory holding `config.default.yml`, `config.<env>.yml`, and profile
    #: directories. Usually shipped inside the package.
    config_root: Path

    #: Prefix for environment overrides, e.g. `"CXTK_"` -> `CXTK_SECTION__KEY`.
    #: Empty disables environment overrides.
    env_prefix: str = ""

    #: Sections whose value may be a bare profile name resolving to
    #: `<config_root>/<section>/<name>.yml`, instead of an inline mapping.
    profiled_sections: tuple[str, ...] = ()

    #: XDG application name for the user layer (`~/.config/<app_name>/config.yml`).
    #: Empty disables the user layer.
    app_name: str = ""

    #: Project directory searched for by walking up from the working directory,
    #: e.g. `".cxtk"`. Empty disables the project layer.
    project_dir: str = ""

    #: Env var naming an explicit config file, e.g. `"CXTK_CONFIG"`.
    #: Defaults to `<ENV_PREFIX>CONFIG` when a prefix is set.
    config_env_var: str = ""

    #: Env var naming a packaged env config, e.g. `"CXTK_ENV"`.
    #: Defaults to `<ENV_PREFIX>ENV` when a prefix is set.
    env_name_var: str = ""

    #: Separator between section and key in environment overrides.
    env_nested_delimiter: str = "__"

    #: Filename used for user and project configs.
    config_name: str = DEFAULT_CONFIG_NAME

    #: Key holding per-source glob rules, if the application uses them.
    #: Empty disables source rules.
    source_rules_key: str = ""

    #: Extra keys stripped before validation, for loader-only machinery.
    non_settings_keys: tuple[str, ...] = field(default_factory=tuple)

    #: Explicit directory for the user layer, overriding the XDG derivation.
    #: Applications using platformdirs pass its result here, so migrating to
    #: xcfg never silently moves where a user's config is read from.
    user_config_dir: Path | None = None

    #: Explicit base-config path, when it is not `<config_root>/config.default.yml`.
    #: Applications that ship defaults under a different name set this.
    default_config: Path | None = None

    #: Applied to the merged file layers before environment overrides are
    #: merged in. The hook for placeholder resolution such as `${VAR}`, which
    #: should apply to file-sourced values but not re-apply to env values.
    file_layer_transform: Callable[[RawConfig], RawConfig] | None = None

    def __post_init__(self) -> None:
        if not self.config_root:
            raise ValueError("ConfigSpec requires a config_root")

    @property
    def explicit_config_var(self) -> str:
        if self.config_env_var:
            return self.config_env_var
        return f"{self.env_prefix}CONFIG" if self.env_prefix else ""

    @property
    def env_selector_var(self) -> str:
        if self.env_name_var:
            return self.env_name_var
        return f"{self.env_prefix}ENV" if self.env_prefix else ""

    @property
    def default_config_path(self) -> Path:
        if self.default_config is not None:
            return self.default_config
        return self.config_root / f"{ENV_CONFIG_PREFIX}default{_suffix(self.config_name)}"

    def env_config_path(self, name: str) -> Path:
        return self.config_root / f"{ENV_CONFIG_PREFIX}{name}{_suffix(self.config_name)}"

    def profile_path(self, section: str, name: str) -> Path:
        return self.config_root / section / f"{name}{_suffix(self.config_name)}"

    @property
    def reserved_keys(self) -> tuple[str, ...]:
        """Keys the loader consumes and must strip before validation."""
        extra = (self.source_rules_key,) if self.source_rules_key else ()
        return self.non_settings_keys + extra


def _suffix(config_name: str) -> str:
    """`.yml` from `config.yml`, so profiles match the app's chosen extension."""
    return Path(config_name).suffix or ".yml"


__all__ = ["DEFAULT_CONFIG_NAME", "ENV_CONFIG_PREFIX", "ConfigSpec", "RawConfig"]
