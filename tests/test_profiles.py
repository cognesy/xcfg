"""The string-or-mapping profile rule."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import LoaderFactory
from xcfg import ConfigError, ConfigLoader


def test_string_value_resolves_to_a_profile_file(loader: ConfigLoader) -> None:
    settings = loader.load(environ={})
    assert settings.database.driver == "sqlite"
    assert settings.database.pool_size == 1, "profile file, not the model default"


def test_mapping_value_is_used_inline(loader: ConfigLoader, tmp_path: Path) -> None:
    path = tmp_path / "inline.yml"
    path.write_text("database:\n  driver: mysql\n  pool_size: 7\n")
    settings = loader.load(config_path=path, environ={})
    assert (settings.database.driver, settings.database.pool_size) == ("mysql", 7)


def test_profiles_stay_independent_across_sections(loader: ConfigLoader) -> None:
    """N + M profile files, never N x M combined ones."""
    assert loader.available_profiles("database") == ("postgres", "sqlite")


def test_unknown_profile_names_the_alternatives(loader: ConfigLoader, tmp_path: Path) -> None:
    path = tmp_path / "bad.yml"
    path.write_text("database: nope\n")
    with pytest.raises(ConfigError, match="available: postgres, sqlite"):
        loader.load(config_path=path, environ={})


def test_unprofiled_sections_are_left_alone(make_loader: LoaderFactory, tmp_path: Path) -> None:
    """A string in a section that is not profiled is a plain value."""
    loader = make_loader(profiled_sections=())
    path = tmp_path / "x.yml"
    path.write_text("output:\n  directory: plain\n")
    assert loader.load(config_path=path, environ={}).output.directory == "plain"


def test_profiles_in_a_project_layer_are_expanded(loader: ConfigLoader, tmp_path: Path) -> None:
    work = tmp_path / "work"
    (work / ".myapp").mkdir(parents=True)
    (work / ".myapp" / "config.yml").write_text("database: postgres\n")
    assert loader.load(start_dir=work, environ={}).database.pool_size == 20


def test_available_envs_lists_packaged_configs(loader: ConfigLoader) -> None:
    assert loader.available_envs() == ("default", "staging")


def test_available_profiles_is_empty_for_unknown_sections(loader: ConfigLoader) -> None:
    assert loader.available_profiles("nosuch") == ()


def test_every_shipped_profile_loads(loader: ConfigLoader, tmp_path: Path) -> None:
    """A broken packaged profile should fail here, not in a user's terminal."""
    for name in loader.available_profiles("database"):
        path = tmp_path / f"sel-{name}.yml"
        path.write_text(f"database: {name}\n")
        assert loader.load(config_path=path, environ={}) is not None
