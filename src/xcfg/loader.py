"""Layered configuration loading.

Resolution order for the base config:

1. an explicit path (argument, or the spec's ``*_CONFIG`` env var)
2. a named env config (argument, or the spec's ``*_ENV`` env var)
3. the packaged ``config.default.yml``

Layers merged over it, later winning:

4. user config at ``${XDG_CONFIG_HOME}/<app_name>/config.yml``
5. project config at ``<project_dir>/config.yml``, nearest walking up
6. environment variables ``<PREFIX><SECTION>__<KEY>``
7. explicit dotted-path overrides

Profiled sections may be given as a name instead of a mapping; see
:class:`xcfg.ConfigSpec`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from .errors import ConfigError
from .spec import ENV_CONFIG_PREFIX, ConfigSpec, RawConfig

TSettings = TypeVar("TSettings", bound=BaseModel)


class ConfigLoader:
    """Loads one application's configuration, as described by its spec."""

    def __init__(self, spec: ConfigSpec, model: type[BaseModel]) -> None:
        self.spec = spec
        self.model = model

    # -- loading ---------------------------------------------------------

    def load(
        self,
        *,
        config_path: Path | None = None,
        env_name: str | None = None,
        overrides: Mapping[str, str] | None = None,
        start_dir: Path | None = None,
        environ: Mapping[str, str] | None = None,
        source: Path | None = None,
        project_path: Path | None = None,
        base_config: RawConfig | None = None,
    ) -> Any:
        """Compose and validate settings. Returns an instance of `model`."""
        merged = self.load_raw(
            config_path=config_path,
            env_name=env_name,
            overrides=overrides,
            start_dir=start_dir,
            environ=environ,
            source=source,
            project_path=project_path,
            base_config=base_config,
        )
        try:
            return self.model(**merged)
        except ValidationError as exc:
            raise ConfigError(f"invalid configuration: {_first_error(exc)}") from exc

    def load_raw(
        self,
        *,
        config_path: Path | None = None,
        env_name: str | None = None,
        overrides: Mapping[str, str] | None = None,
        start_dir: Path | None = None,
        environ: Mapping[str, str] | None = None,
        source: Path | None = None,
        project_path: Path | None = None,
        base_config: RawConfig | None = None,
    ) -> RawConfig:
        """The merged mapping, before validation. Useful for diagnostics.

        `project_path` names the project layer directly, for applications that
        resolve their project root themselves instead of walking up from the
        working directory. `base_config` supplies the base layer as an
        already-loaded mapping, for defaults that live somewhere other than a
        readable file -- packaged resources reached through the application's
        own loader, for instance.
        """
        env = dict(environ if environ is not None else os.environ)
        if base_config is None:
            base_config = self._base_layer(config_path, env_name, env)

        merged = self._expand_profiles(base_config)
        project = self._project_layer(start_dir or Path.cwd(), project_path)
        for layer in (self._user_layer(env), project):
            if layer is not None:
                merged = deep_merge(merged, self._expand_profiles(layer))

        transform = self.spec.file_layer_transform
        if transform is not None:
            merged = transform(merged)

        merged = deep_merge(merged, self._env_layer(env))
        merged = self._apply_source_rules(merged, source)

        for key, value in (overrides or {}).items():
            set_dotted(merged, key, coerce_scalar(value))
        for key in self.spec.reserved_keys:
            merged.pop(key, None)
        return merged

    # -- discovery -------------------------------------------------------

    def available_envs(self) -> tuple[str, ...]:
        root = self.spec.config_root
        if not root.is_dir():
            return ()
        pattern = f"{ENV_CONFIG_PREFIX}*{self.spec.default_config_path.suffix}"
        return tuple(sorted(p.stem.removeprefix(ENV_CONFIG_PREFIX) for p in root.glob(pattern)))

    def available_profiles(self, section: str) -> tuple[str, ...]:
        directory = self.spec.config_root / section
        if not directory.is_dir():
            return ()
        suffix = self.spec.default_config_path.suffix
        return tuple(sorted(p.stem for p in directory.glob(f"*{suffix}")))

    def matching_source_rules(
        self,
        source: Path,
        *,
        config_path: Path | None = None,
        env_name: str | None = None,
        start_dir: Path | None = None,
        environ: Mapping[str, str] | None = None,
        project_path: Path | None = None,
    ) -> tuple[str, ...]:
        """Patterns from the source-rules key that apply to this source."""
        if not self.spec.source_rules_key:
            return ()
        env = dict(environ if environ is not None else os.environ)
        merged = self._expand_profiles(read_yaml(self._base_path(config_path, env_name, env)))
        project = self._project_layer(start_dir or Path.cwd(), project_path)
        for layer in (self._user_layer(env), project):
            if layer is not None:
                merged = deep_merge(merged, layer)
        rules = merged.get(self.spec.source_rules_key)
        if not isinstance(rules, Mapping):
            return ()
        return tuple(str(p) for p in rules if matches_source(source, str(p)))

    # -- layers ----------------------------------------------------------

    def _base_layer(
        self, config_path: Path | None, env_name: str | None, env: Mapping[str, str]
    ) -> RawConfig:
        """The base mapping, optionally layering a named env over the default."""
        path = self._base_path(config_path, env_name, env)
        if not self.spec.env_extends_default or path == self.spec.default_config_path:
            return read_yaml(path)
        default = self.spec.default_config_path
        base = read_yaml(default) if default.is_file() else {}
        return deep_merge(self._expand_profiles(base), read_yaml(path))

    def _base_path(
        self, config_path: Path | None, env_name: str | None, env: Mapping[str, str]
    ) -> Path:
        var = self.spec.explicit_config_var
        explicit = config_path or (Path(env[var]) if var and env.get(var) else None)
        if explicit is not None:
            path = explicit.expanduser()
            if not path.is_file():
                raise ConfigError(f"config file not found: {path}")
            return path

        selector = self.spec.env_selector_var
        name = env_name or (env.get(selector) if selector else None)
        if not name:
            return self.spec.default_config_path

        path = self.spec.env_config_path(name)
        if not path.is_file():
            known = ", ".join(self.available_envs()) or "none"
            raise ConfigError(f"unknown config env '{name}' (available: {known})")
        return path

    def _user_layer(self, env: Mapping[str, str]) -> RawConfig | None:
        explicit = self.spec.user_config_dir
        if explicit is not None:
            path = explicit / self.spec.config_name
            return read_yaml(path) if path.is_file() else None
        if not self.spec.app_name:
            return None
        base = env.get("XDG_CONFIG_HOME")
        root = Path(base).expanduser() if base else Path.home() / ".config"
        path = root / self.spec.app_name / self.spec.config_name
        return read_yaml(path) if path.is_file() else None

    def _project_layer(self, start: Path, explicit: Path | None = None) -> RawConfig | None:
        if explicit is not None:
            return read_yaml(explicit) if explicit.is_file() else None
        if not self.spec.project_dir:
            return None
        current = start.resolve()
        for directory in (current, *current.parents):
            path = directory / self.spec.project_dir / self.spec.config_name
            if path.is_file():
                return read_yaml(path)
        return None

    def _env_layer(self, env: Mapping[str, str]) -> RawConfig:
        prefix = self.spec.env_prefix
        if not prefix:
            return {}
        delimiter = self.spec.env_nested_delimiter
        reserved = {self.spec.explicit_config_var, self.spec.env_selector_var}
        layer: RawConfig = {}
        for raw_key, raw_value in env.items():
            if not raw_key.startswith(prefix) or raw_key in reserved:
                continue
            if delimiter not in raw_key:
                continue
            path = raw_key[len(prefix) :].lower().replace(delimiter, ".")
            set_dotted(layer, path, coerce_scalar(raw_value))
        return layer

    def _expand_profiles(self, layer: RawConfig) -> RawConfig:
        """Turn `section: name` into the contents of `<section>/<name>.yml`."""
        resolved = dict(layer)
        for section in self.spec.profiled_sections:
            value = resolved.get(section)
            if not isinstance(value, str):
                continue
            path = self.spec.profile_path(section, value)
            if not path.is_file():
                known = ", ".join(self.available_profiles(section)) or "none"
                raise ConfigError(f"unknown {section} profile '{value}' (available: {known})")
            resolved[section] = read_yaml(path)
        return resolved

    def _apply_source_rules(self, merged: RawConfig, source: Path | None) -> RawConfig:
        key = self.spec.source_rules_key
        if not key:
            return merged
        rules = merged.get(key)
        if source is None or not isinstance(rules, Mapping):
            return merged
        for pattern, overlay in rules.items():
            if not matches_source(source, str(pattern)):
                continue
            if not isinstance(overlay, Mapping):
                raise ConfigError(f"source rule '{pattern}' must be a mapping")
            merged = deep_merge(merged, self._expand_profiles(dict(overlay)))
        return merged


# -- helpers -------------------------------------------------------------


def read_yaml(path: Path) -> RawConfig:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"cannot parse {path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ConfigError(f"config must be a mapping: {path}")
    return loaded


def deep_merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> RawConfig:
    merged = dict(base)
    for key, value in overlay.items():
        existing = merged.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def set_dotted(target: RawConfig, dotted: str, value: Any) -> None:
    keys = dotted.split(".")
    cursor = target
    for key in keys[:-1]:
        nested = cursor.get(key)
        if not isinstance(nested, dict):
            nested = {}
            cursor[key] = nested
        cursor = nested
    cursor[keys[-1]] = value


def coerce_scalar(raw: str) -> Any:
    """Parse an override the way YAML would, so `x.y=3` becomes an int."""
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError:
        return raw


def matches_source(source: Path, pattern: str) -> bool:
    """Glob against the full path and the bare filename, so both forms work."""
    return fnmatch(str(source), pattern) or fnmatch(source.name, pattern)


def _first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    location = ".".join(str(part) for part in error["loc"])
    return f"{location}: {error['msg']}"


__all__ = [
    "ConfigLoader",
    "RawConfig",
    "coerce_scalar",
    "deep_merge",
    "matches_source",
    "read_yaml",
    "set_dotted",
]
