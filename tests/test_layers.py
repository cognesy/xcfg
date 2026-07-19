"""Layer composition and precedence."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import LoaderFactory
from xcfg import ConfigError, ConfigLoader


def test_defaults_load_with_no_files_or_env(loader: ConfigLoader) -> None:
    settings = loader.load(environ={})
    assert settings.database.driver == "sqlite"
    assert settings.output.directory == "out"


def test_named_env_selects_a_different_profile(loader: ConfigLoader) -> None:
    assert loader.load(env_name="staging", environ={}).database.driver == "postgres"


def test_env_name_can_come_from_the_environment(loader: ConfigLoader) -> None:
    assert loader.load(environ={"MYAPP_ENV": "staging"}).database.driver == "postgres"


def test_explicit_path_beats_env_name(loader: ConfigLoader, tmp_path: Path) -> None:
    path = tmp_path / "explicit.yml"
    path.write_text("database:\n  driver: mysql\n")
    settings = loader.load(config_path=path, env_name="staging", environ={})
    assert settings.database.driver == "mysql"


def test_explicit_path_can_come_from_the_environment(loader: ConfigLoader, tmp_path: Path) -> None:
    path = tmp_path / "explicit.yml"
    path.write_text("database:\n  driver: mysql\n")
    assert loader.load(environ={"MYAPP_CONFIG": str(path)}).database.driver == "mysql"


def test_user_layer_overrides_packaged_defaults(loader: ConfigLoader, tmp_path: Path) -> None:
    (tmp_path / "myapp").mkdir()
    (tmp_path / "myapp" / "config.yml").write_text("output:\n  verbose: true\n")
    settings = loader.load(environ={"XDG_CONFIG_HOME": str(tmp_path)}, start_dir=tmp_path)
    assert settings.output.verbose is True


def test_project_layer_is_found_by_walking_up(loader: ConfigLoader, tmp_path: Path) -> None:
    nested = tmp_path / "work" / "deep" / "nested"
    nested.mkdir(parents=True)
    (tmp_path / "work" / ".myapp").mkdir()
    (tmp_path / "work" / ".myapp" / "config.yml").write_text("output:\n  directory: proj\n")
    assert loader.load(start_dir=nested, environ={}).output.directory == "proj"


def test_project_layer_beats_user_layer(loader: ConfigLoader, tmp_path: Path) -> None:
    (tmp_path / "myapp").mkdir()
    (tmp_path / "myapp" / "config.yml").write_text("output:\n  directory: user\n")
    work = tmp_path / "work"
    (work / ".myapp").mkdir(parents=True)
    (work / ".myapp" / "config.yml").write_text("output:\n  directory: project\n")
    settings = loader.load(environ={"XDG_CONFIG_HOME": str(tmp_path)}, start_dir=work)
    assert settings.output.directory == "project"


def test_environment_beats_files(loader: ConfigLoader, tmp_path: Path) -> None:
    work = tmp_path / "work"
    (work / ".myapp").mkdir(parents=True)
    (work / ".myapp" / "config.yml").write_text("output:\n  directory: project\n")
    settings = loader.load(environ={"MYAPP_OUTPUT__DIRECTORY": "fromenv"}, start_dir=work)
    assert settings.output.directory == "fromenv"


def test_overrides_beat_environment(loader: ConfigLoader) -> None:
    settings = loader.load(
        environ={"MYAPP_OUTPUT__DIRECTORY": "fromenv"},
        overrides={"output.directory": "explicit"},
    )
    assert settings.output.directory == "explicit"


def test_merge_is_deep_so_untouched_siblings_survive(loader: ConfigLoader, tmp_path: Path) -> None:
    path = tmp_path / "partial.yml"
    path.write_text("output:\n  verbose: true\n")
    settings = loader.load(config_path=path, environ={})
    assert settings.output.verbose is True
    assert settings.output.directory == "out", "sibling key must keep its default"


def test_scalars_are_coerced_not_left_as_strings(loader: ConfigLoader) -> None:
    settings = loader.load(overrides={"database.pool_size": "12"}, environ={})
    assert settings.database.pool_size == 12


def test_booleans_from_environment_are_coerced(loader: ConfigLoader) -> None:
    assert loader.load(environ={"MYAPP_OUTPUT__VERBOSE": "true"}).output.verbose is True


def test_selector_variables_are_not_treated_as_overrides(loader: ConfigLoader) -> None:
    """MYAPP_ENV selects a config; it is not a setting named `env`."""
    assert loader.load(environ={"MYAPP_ENV": "staging"}).database.driver == "postgres"


def test_env_layer_ignores_variables_without_the_delimiter(loader: ConfigLoader) -> None:
    assert loader.load(environ={"MYAPP_SOMETHING": "x"}).database.driver == "sqlite"


def test_disabled_layers_are_skipped(make_loader: LoaderFactory, tmp_path: Path) -> None:
    """An app with a single config file sets neither app_name nor project_dir."""
    (tmp_path / "myapp").mkdir()
    (tmp_path / "myapp" / "config.yml").write_text("output:\n  directory: user\n")
    loader = make_loader(app_name="", project_dir="")
    settings = loader.load(environ={"XDG_CONFIG_HOME": str(tmp_path)}, start_dir=tmp_path)
    assert settings.output.directory == "out"


def test_no_env_prefix_disables_environment_overrides(make_loader: LoaderFactory) -> None:
    loader = make_loader(env_prefix="")
    assert loader.load(environ={"MYAPP_OUTPUT__DIRECTORY": "x"}).output.directory == "out"


def test_missing_explicit_file_is_reported(loader: ConfigLoader, tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="config file not found"):
        loader.load(config_path=tmp_path / "absent.yml", environ={})


def test_unknown_env_names_the_alternatives(loader: ConfigLoader) -> None:
    with pytest.raises(ConfigError, match="available: default, staging"):
        loader.load(env_name="nope", environ={})


def test_empty_config_file_is_valid(loader: ConfigLoader, tmp_path: Path) -> None:
    path = tmp_path / "empty.yml"
    path.write_text("")
    assert loader.load(config_path=path, environ={}).database.driver == "sqlite"


def test_non_mapping_config_is_rejected(loader: ConfigLoader, tmp_path: Path) -> None:
    path = tmp_path / "list.yml"
    path.write_text("- one\n- two\n")
    with pytest.raises(ConfigError, match="must be a mapping"):
        loader.load(config_path=path, environ={})


def test_malformed_yaml_is_reported(loader: ConfigLoader, tmp_path: Path) -> None:
    path = tmp_path / "bad.yml"
    path.write_text("a: [1, 2\n")
    with pytest.raises(ConfigError, match="cannot parse"):
        loader.load(config_path=path, environ={})
